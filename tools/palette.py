#!/usr/bin/env python3
"""palette — extract exact colours from brand assets.

No Pillow / ImageMagick in this sandbox and no package registry access, so the
pixels are read through a headless browser canvas instead of eyeballing a
screenshot. Eyeballing is not good enough for brand colours: JPEG compression
shifts values, and a hex that is one or two steps off shows up as a visible
mismatch between the website, print and signage.

Usage:
  python3 tools/palette.py <image...>

Prints, per image, the dominant opaque colours with hex value and coverage.
"""
import functools
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import uuid

SESSION = "palette"
TOP_N = 10
SAMPLE = 240  # longest edge the image is sampled at; plenty for colour counting


def serve(root):
    """Serve `root` over localhost HTTP and return (port, shutdown).

    Needed because Chromium treats every file:// document as its own opaque
    origin: a canvas that has drawn a file:// image becomes tainted and
    getImageData() raises a SecurityError. Same-origin HTTP avoids that, and
    works fully offline.
    """
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=root)

    class Quiet(socketserver.TCPServer):
        allow_reuse_address = True

        def log_message(self, *a):  # pragma: no cover
            pass

    httpd = Quiet(("127.0.0.1", 0), handler)
    httpd.RequestHandlerClass.log_message = lambda *a, **k: None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1], httpd.shutdown


def build_page(rel_paths):
    srcs = json.dumps(rel_paths)
    return """<!doctype html><meta charset="utf-8"><body><script>
const SRCS = %s, SAMPLE = %d, TOP_N = %d;
function load(src) {
  return new Promise(res => {
    const im = new Image();
    im.onload = () => res(im);
    im.onerror = () => res(null);
    im.src = src;
  });
}
(async () => {
  const out = [];
  for (const src of SRCS) {
    const im = await load(src);
    if (!im) { out.push({src, error: 'load failed'}); continue; }
    const s = Math.min(1, SAMPLE / Math.max(im.width, im.height));
    const w = Math.max(1, Math.round(im.width * s));
    const h = Math.max(1, Math.round(im.height * s));
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d', {willReadFrequently: true});
    ctx.drawImage(im, 0, 0, w, h);
    const px = ctx.getImageData(0, 0, w, h).data;
    const bins = new Map();
    let opaque = 0;
    for (let i = 0; i < px.length; i += 4) {
      if (px[i+3] < 128) continue;          // ignore transparent pixels
      opaque++;
      // quantise to 16 levels per channel so near-identical pixels group up
      const k = ((px[i] >> 4) << 8) | ((px[i+1] >> 4) << 4) | (px[i+2] >> 4);
      const e = bins.get(k);
      if (e) { e.n++; e.r += px[i]; e.g += px[i+1]; e.b += px[i+2]; }
      else bins.set(k, {n: 1, r: px[i], g: px[i+1], b: px[i+2]});
    }
    const top = [...bins.values()]
      .sort((a, b) => b.n - a.n)
      .slice(0, TOP_N)
      .map(e => {
        // average the bin for a truer hex than the quantised bucket centre
        const r = Math.round(e.r / e.n), g = Math.round(e.g / e.n), b = Math.round(e.b / e.n);
        const hex = '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
        return {hex, rgb: [r, g, b], pct: +(100 * e.n / opaque).toFixed(1)};
      });
    out.push({
      src: src.split('/').pop(),
      natural: im.width + 'x' + im.height,
      opaque_pct: +(100 * opaque / (w * h)).toFixed(1),
      top
    });
  }
  window.__out = JSON.stringify(out);
  document.title = 'READY';
})();
</script></body>""" % (srcs, SAMPLE, TOP_N)


def run(*args):
    return subprocess.run(["agent-browser", *args, "--session", SESSION],
                          capture_output=True, text=True, timeout=240)


def main(paths):
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        print("missing: " + ", ".join(missing), file=sys.stderr)
        return 2

    root = os.getcwd()
    rels = [os.path.relpath(os.path.abspath(p), root) for p in paths]
    if any(r.startswith("..") for r in rels):
        print("all images must live under the current directory", file=sys.stderr)
        return 2

    page = os.path.join(root, f".palette-{uuid.uuid4().hex[:8]}.html")
    with open(page, "w") as fh:
        fh.write(build_page(rels))
    port, shutdown = serve(root)
    try:
        run("open", f"http://127.0.0.1:{port}/{os.path.basename(page)}")
        # `eval` prints the value JSON-encoded, so the payload arrives as a
        # JSON string that itself contains JSON — decode twice.
        import time
        data = None
        for _ in range(15):
            res = run("eval", "window.__out || ''")
            try:
                inner = json.loads(res.stdout.strip())
            except json.JSONDecodeError:
                inner = ""
            if isinstance(inner, str) and inner.startswith("["):
                data = json.loads(inner)
                break
            time.sleep(1)
        if data is None:
            print("could not read palette from browser", file=sys.stderr)
            return 2
    finally:
        run("close")
        shutdown()
        os.unlink(page)

    for entry in data:
        print(f"\n=== {entry['src']}  ({entry.get('natural','?')}) ===")
        if entry.get("error"):
            print("  " + entry["error"])
            continue
        print(f"  opaque pixels: {entry['opaque_pct']}%")
        for c in entry["top"]:
            r, g, b = c["rgb"]
            print(f"  {c['hex']}   rgb({r:3d},{g:3d},{b:3d})   {c['pct']:5.1f}%")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--top" in argv:
        i = argv.index("--top")
        TOP_N = int(argv[i + 1])
        del argv[i:i + 2]
    sys.exit(main(argv) if argv else (print(__doc__) or 2))
