#!/usr/bin/env python3
"""pdfimages — pull the embedded raster images out of a PDF at full resolution.

Screenshotting a PDF page gives you a re-compressed, viewer-scaled copy. The
images inside the file are the originals, and a PDF stores each one as an
XObject stream whose bytes are usually a plain JPEG (`/DCTDecode`) or a
zlib-compressed bitmap (`/FlateDecode`). Both can be recovered without poppler
or Pillow, neither of which exists in this sandbox.

Usage:
  python3 tools/pdfimages.py <file.pdf> [outdir] [--min-px 500]

Writes JPEGs straight out, and converts Flate RGB/grey bitmaps to PNG by
re-deflating the raw samples with a hand-built PNG header.
"""
import os
import re
import struct
import sys
import zlib

DEFAULT_MIN = 500          # skip icons, rules and other furniture


def read_dict(raw, start):
    """Return the bytes of the dictionary that begins at `start`."""
    depth = 0
    i = start
    while i < len(raw) - 1:
        pair = raw[i:i + 2]
        if pair == b"<<":
            depth += 1
            i += 2
            continue
        if pair == b">>":
            depth -= 1
            i += 2
            if depth == 0:
                return raw[start:i]
            continue
        i += 1
    return b""


def num(d, key, default=0):
    m = re.search(rb"/" + key + rb"\s+(\d+)", d)
    return int(m.group(1)) if m else default


def write_png(path, width, height, channels, samples, bitdepth=8):
    """Assemble a PNG from raw, unfiltered samples."""
    color_type = {1: 0, 3: 2, 4: 6}.get(channels)
    if color_type is None:
        return False
    stride = width * channels * bitdepth // 8
    if len(samples) < stride * height:
        return False

    rows = bytearray()
    for y in range(height):
        rows.append(0)                                  # filter type: none
        rows += samples[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height,
                                        bitdepth, color_type, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)
    return True


def main(argv):
    if not argv:
        print(__doc__)
        return 2

    pdf = argv[0]
    outdir = argv[1] if len(argv) > 1 and not argv[1].startswith("--") \
        else "media/extracted"
    min_px = DEFAULT_MIN
    if "--min-px" in argv:
        min_px = int(argv[argv.index("--min-px") + 1])

    raw = open(pdf, "rb").read()
    os.makedirs(outdir, exist_ok=True)

    found = kept = 0
    for m in re.finditer(rb"/Subtype\s*/Image", raw):
        # Walk back to the dictionary this entry belongs to.
        dict_start = raw.rfind(b"<<", max(0, m.start() - 3000), m.start())
        if dict_start == -1:
            continue
        d = read_dict(raw, dict_start)
        if not d:
            continue

        s = raw.find(b"stream", dict_start + len(d) - 2)
        if s == -1 or s - dict_start > len(d) + 40:
            continue
        s += len("stream")
        while raw[s:s + 1] in (b"\r", b"\n"):
            s += 1
        e = raw.find(b"endstream", s)
        if e == -1:
            continue
        payload = raw[s:e]

        w, h = num(d, b"Width"), num(d, b"Height")
        bpc = num(d, b"BitsPerComponent", 8)
        found += 1
        if w < min_px or h < min_px:
            continue

        base = os.path.join(outdir, f"img-{kept + 1:02d}-{w}x{h}")

        # Filters can be chained, e.g. /Filter [/FlateDecode /DCTDecode],
        # and they apply in order. Writing the raw stream out as .jpg when a
        # Flate layer sits on top produces a file that starts with 78 9c and
        # opens in nothing — inflate first, then look at what emerged.
        if b"/FlateDecode" in d:
            try:
                payload = zlib.decompress(payload)
            except Exception:
                continue

        if b"/JPXDecode" in d:
            continue                      # JPEG 2000: nothing here can decode it

        if payload[:2] == b"\xff\xd8":    # trust the magic, not the dictionary
            with open(base + ".jpg", "wb") as fh:
                fh.write(payload)
            print(f"  {base}.jpg   {w}x{h}  (jpeg, {len(payload) // 1024}KB)")
            kept += 1
            continue

        if b"/DCTDecode" not in d:
            channels = 3 if (b"/DeviceRGB" in d or b"/ICCBased" in d) else \
                       1 if b"/DeviceGray" in d else 0
            if channels and write_png(base + ".png", w, h, channels,
                                      payload, bpc):
                print(f"  {base}.png   {w}x{h}  ({channels}ch flate)")
                kept += 1
            continue

    print(f"\n{found} image objects in the PDF, {kept} written "
          f"(>= {min_px}px) to {outdir}/", file=sys.stderr)
    print("Now run:  python3 tools/imgguard.py probe "
          f"{outdir}/*", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
