#!/usr/bin/env python3
"""imgguard — the single chokepoint that enforces the 2000px rule.

Every image must pass through here BEFORE it is ever read by the agent.
Reading an image whose width or height exceeds 2000px fails the request
("At least one of the image dimensions exceed max allowed size..."), and the
failure lands only after the work is done — the whole session is lost.

Usage:
  python3 tools/imgguard.py probe  <file...>        # dimensions + verdict
  python3 tools/imgguard.py safe   <file> [out]     # downscale to <=LIMIT, print path
  python3 tools/imgguard.py dpi    <w_in> <h_in>    # max safe DPI for a print layout

Exit codes: 0 = safe, 2 = oversized / unreadable.

No Pillow or ImageMagick in this sandbox and no PyPI access, so dimensions are
parsed straight from file headers and downscaling is done with a headless
browser canvas via the agent-browser CLI.
"""
import os
import struct
import subprocess
import sys
import tempfile

LIMIT = 2000  # hard ceiling on either dimension
TARGET = 1600  # what `safe` downscales to, leaving headroom


# ---------------------------------------------------------------- dimensions
def _png(f):
    f.seek(16)
    return struct.unpack(">II", f.read(8))


def _gif(f):
    f.seek(6)
    return struct.unpack("<HH", f.read(4))


def _bmp(f):
    f.seek(18)
    w, h = struct.unpack("<ii", f.read(8))
    return abs(w), abs(h)


def _jpeg(f):
    f.seek(2)
    while True:
        b = f.read(1)
        if not b:
            raise ValueError("truncated jpeg")
        if b != b"\xff":
            continue
        marker = f.read(1)
        while marker == b"\xff":
            marker = f.read(1)
        m = marker[0]
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            continue
        (seglen,) = struct.unpack(">H", f.read(2))
        if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            f.read(1)
            h, w = struct.unpack(">HH", f.read(4))
            return w, h
        f.seek(seglen - 2, os.SEEK_CUR)


def _webp(f):
    f.seek(12)
    chunk = f.read(4)
    if chunk == b"VP8X":
        f.seek(24)
        d = f.read(6)
        w = (d[0] | d[1] << 8 | d[2] << 16) + 1
        h = (d[3] | d[4] << 8 | d[5] << 16) + 1
        return w, h
    if chunk == b"VP8 ":
        f.seek(26)
        return (struct.unpack("<HH", f.read(4))[0] & 0x3FFF,
                struct.unpack("<H", f.read(2) or b"\0\0")[0] & 0x3FFF)
    if chunk == b"VP8L":
        f.seek(21)
        (bits,) = struct.unpack("<I", f.read(4))
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ValueError("unknown webp variant")


def dimensions(path):
    """Return (width, height) for a raster image, parsed from its header."""
    with open(path, "rb") as f:
        head = f.read(12)
        if head.startswith(b"\x89PNG"):
            return _png(f)
        if head.startswith(b"\xff\xd8"):
            return _jpeg(f)
        if head.startswith((b"GIF87a", b"GIF89a")):
            return _gif(f)
        if head.startswith(b"BM"):
            return _bmp(f)
        if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
            return _webp(f)
    raise ValueError("unsupported or non-raster format")


# -------------------------------------------------------------------- actions
def probe(paths):
    worst = 0
    for p in paths:
        try:
            w, h = dimensions(p)
        except Exception as exc:  # noqa: BLE001 - report, never crash the caller
            print(f"UNREADABLE  {p}  ({exc}) -> DO NOT READ")
            worst = 2
            continue
        if max(w, h) > LIMIT:
            print(f"OVERSIZED   {p}  {w}x{h}  -> DO NOT READ, run `safe` first")
            worst = 2
        else:
            print(f"safe        {p}  {w}x{h}")
    return worst


def safe(path, out=None, target=TARGET):
    """Write a downscaled copy that is guaranteed <= target on its long edge.

    Implemented by sizing a headless viewport to the target dimensions and
    letting the browser rasterise the image into it, because this sandbox has
    no Pillow / ImageMagick and no package-registry access to install them.
    """
    w, h = dimensions(path)
    if max(w, h) <= target:
        print(path)
        return 0
    scale = target / max(w, h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    out = out or f"{os.path.splitext(path)[0]}.safe.png"
    src = "file://" + os.path.abspath(path)

    html = (
        '<!doctype html><meta charset="utf-8">'
        '<style>html,body{margin:0;padding:0;overflow:hidden;background:#fff}'
        'img{display:block;width:100vw;height:100vh;object-fit:fill}</style>'
        f'<img src="{src}">'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
        fh.write(html)
        page = fh.name

    session = "imgguard"

    def run(*a):
        return subprocess.run(
            ["agent-browser", *a, "--session", session],
            capture_output=True, text=True, timeout=240,
        )

    try:
        run("set", "viewport", str(nw), str(nh))
        run("open", "file://" + page)
        run("set", "viewport", str(nw), str(nh))
        res = run("screenshot", out)
        if not os.path.exists(out):
            print(f"FAILED to downscale {path}: "
                  f"{res.stdout[:300]} {res.stderr[:300]}", file=sys.stderr)
            return 2
        ow, oh = dimensions(out)
        if max(ow, oh) > LIMIT:
            print(f"FAILED: result is still {ow}x{oh}", file=sys.stderr)
            return 2
        print(out)
        return 0
    finally:
        run("close")
        os.unlink(page)


def dpi(w_in, h_in):
    longest = max(float(w_in), float(h_in))
    print(f"max safe DPI for {w_in}x{h_in} in = {int(LIMIT // longest)} "
          f"(={LIMIT}/{longest:g})")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, args = argv[1], argv[2:]
    if cmd == "probe" and args:
        return probe(args)
    if cmd == "safe" and args:
        return safe(args[0], args[1] if len(args) > 1 else None)
    if cmd == "dpi" and len(args) == 2:
        return dpi(*args)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
