#!/usr/bin/env python3
"""imgfix — crop, colour-correct, resize and re-encode images to JPEG.

This sandbox has no Pillow, no ImageMagick, and no registry access to install
either, so the browser does the pixel work: Canvas2D supports `ctx.filter`, so
a crop, a colour transform and a resize all happen in one drawImage, and
`canvas.toBlob` re-encodes to JPEG.

Getting the bytes back out is the interesting part. Reading a large data URL
through the CLI's `eval` truncates, so the page POSTs each finished blob to the
same local HTTP server that is serving it — same origin, no network, no size
limit worth worrying about.

Usage:
  python3 tools/imgfix.py <manifest.json>

Manifest: a list of jobs.
  [
    {
      "in":  "media/extracted/img-13-1754x1062.jpg",
      "out": "assets/img/photo/majlis.jpg",
      "crop": [0, 13, 100, 84],        // x, y, w, h — percentages, optional
      "filter": "invert(1) brightness(.68) contrast(1.45) saturate(1.3)",
      "max": 1600,                      // longest edge; never above 2000
      "quality": 0.86
    }
  ]

Why a filter would be needed at all: five of the images inside the brand
profile are stored in a CMYK colour space with inverted samples (an Adobe
convention). Every decoder here renders them as dark negatives, so they are
inverted back and their exposure rebuilt.
"""
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse

SESSION = "imgfix"
LIMIT = 2000          # the hard read limit; see .kiro/steering/image-safety.md


def make_server(root, outbox):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root, **kw)

        def log_message(self, *a, **kw):
            pass

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/__save":
                self.send_error(404)
                return
            name = urllib.parse.parse_qs(parsed.query).get("name", [""])[0]
            # Keep writes inside the repo no matter what the page asks for.
            target = os.path.normpath(os.path.join(root, name))
            if not target.startswith(os.path.abspath(root)):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as fh:
                fh.write(body)
            outbox.append((name, len(body)))
            self.send_response(204)
            self.end_headers()

    class Quiet(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = Quiet(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


PAGE = """<!doctype html><meta charset="utf-8"><body><script>
const JOBS = %s;
const load = (src) => new Promise((res, rej) => {
  const im = new Image();
  im.onload = () => res(im);
  im.onerror = () => rej(new Error('load failed: ' + src));
  im.src = src;
});
(async () => {
  const log = [];
  for (const job of JOBS) {
    try {
      const im = await load('/' + job.in);
      const c = job.crop || [0, 0, 100, 100];
      const sx = im.width  * c[0] / 100, sy = im.height * c[1] / 100;
      const sw = im.width  * c[2] / 100, sh = im.height * c[3] / 100;
      const max = Math.min(job.max || 1600, %d);
      const scale = Math.min(1, max / Math.max(sw, sh));
      const dw = Math.max(1, Math.round(sw * scale));
      const dh = Math.max(1, Math.round(sh * scale));

      const canvas = document.createElement('canvas');
      canvas.width = dw; canvas.height = dh;
      const ctx = canvas.getContext('2d');
      if (job.filter) ctx.filter = job.filter;
      ctx.drawImage(im, sx, sy, sw, sh, 0, 0, dw, dh);

      // Recolour a transparent logo by filling its alpha channel. This is the
      // honest way to get a white wordmark: `filter: brightness(0) invert(1)`
      // in CSS mangles the antialiased edges of thin monoline letterforms and
      // leaves the hairline Latin row almost invisible.
      if (job.tint) {
        ctx.filter = 'none';
        ctx.globalCompositeOperation = 'source-in';
        ctx.fillStyle = job.tint;
        ctx.fillRect(0, 0, dw, dh);
        ctx.globalCompositeOperation = 'source-over';
      }

      const png = /\.png$/i.test(job.out);      // PNG keeps the alpha channel
      const blob = await new Promise(r => png
        ? canvas.toBlob(r, 'image/png')
        : canvas.toBlob(r, 'image/jpeg', job.quality || 0.86));
      await fetch('/__save?name=' + encodeURIComponent(job.out),
                  { method: 'POST', body: blob });
      log.push(job.out + ' ' + dw + 'x' + dh);
    } catch (e) {
      log.push('FAILED ' + job.in + ': ' + e.message);
    }
  }
  window.__done = log.join(' | ');
  document.title = 'DONE';
})();
</script></body>"""


def run(*args):
    return subprocess.run(["agent-browser", *args, "--session", SESSION],
                           capture_output=True, text=True, timeout=300)


def main(argv):
    if not argv:
        print(__doc__)
        return 2

    with open(argv[0], encoding="utf-8") as fh:
        jobs = json.load(fh)

    for job in jobs:
        if not os.path.exists(job["in"]):
            print(f"missing input: {job['in']}", file=sys.stderr)
            return 2
        if job.get("max", 1600) > LIMIT:
            print(f"refusing max={job['max']}: over the {LIMIT}px limit",
                  file=sys.stderr)
            return 2

    root = os.path.abspath(os.getcwd())
    outbox = []
    httpd = make_server(root, outbox)
    port = httpd.server_address[1]

    page = os.path.join(root, ".imgfix.html")
    with open(page, "w") as fh:
        fh.write(PAGE % (json.dumps(jobs), LIMIT))

    try:
        run("set", "viewport", "900", "600")
        run("open", f"http://127.0.0.1:{port}/.imgfix.html")
        for _ in range(40):
            time.sleep(1.5)
            res = run("eval", "window.__done || ''")
            if res.stdout.strip() not in ('""', "", "''"):
                print(res.stdout.strip().strip('"'))
                break
    finally:
        run("close")
        httpd.shutdown()
        os.remove(page)

    print()
    for name, size in outbox:
        print(f"  wrote {name}  ({size // 1024}KB)")
    print(f"\n{len(outbox)}/{len(jobs)} images written", file=sys.stderr)
    return 0 if len(outbox) == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
