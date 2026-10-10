#!/usr/bin/env python3
"""vidposter — export a JPEG poster frame out of an MP4, with no ffmpeg.

`media/video/README.md` used to state that poster frames could not be produced
in this sandbox because there is no ffmpeg and no way to install it. That is
true of ffmpeg and false of the problem: the headless browser already in use
for `imgfix` decodes H.264, honours `currentTime`, and will draw a seeked
`<video>` into a canvas. So the poster is a seek, a `drawImage` and a
`toBlob` — the same three steps `imgfix` uses on stills.

Why posters matter enough to build this: `<video preload="none">` paints a flat
black rectangle until the first frame is decoded, and app.js deliberately does
not preload the reels row. Without `poster=` the row opens as six black holes
on a page whose whole argument is atmosphere.

Usage:
  python3 tools/vidposter.py <file.mp4>[@seconds] ...

  @seconds picks the frame; it defaults to 1.0s, or to the midpoint when the
  clip is shorter than 2s. Several clips open on black or on a title card, so
  the in-point is worth choosing per clip rather than trusting frame zero.

Output: media/photos/<stem>-poster.jpg, the name media/video/README.md asks
for. Dimensions are the clip's own, capped at 1280 on the long edge — a poster
only has to look right until the video takes over.
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

SESSION = "vidposter"
MAX_EDGE = 1280
LIMIT = 2000  # .kiro/steering/image-safety.md — nothing written may exceed it


def make_server(root, outbox):
    """Serve the repo and accept the finished JPEGs back over POST.

    Same approach as imgfix: reading a multi-hundred-KB data URL back through
    the CLI's `eval` truncates, so the page posts each blob to the server that
    served it. Same origin, loopback only, no size ceiling to worry about.
    """
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root, **kw)

        def log_message(self, *a, **kw):
            pass

        def do_GET(self):
            """GET with byte-range support, which seeking genuinely requires.

            SimpleHTTPRequestHandler ignores `Range` and answers 200 with the
            whole file. A browser reads that as "this source is not seekable",
            so `currentTime = 1.0` is dropped and every poster silently comes
            out as frame zero — the first version of this tool did exactly
            that while reporting a seek. Serving 206 with `Content-Range` is
            what makes the seek real.
            """
            rng = self.headers.get("Range")
            path = self.translate_path(self.path)
            if not rng or not os.path.isfile(path):
                return super().do_GET()

            size = os.path.getsize(path)
            try:
                units, _, spec = rng.partition("=")
                if units.strip().lower() != "bytes":
                    raise ValueError(rng)
                first, _, last = spec.partition("-")
                if first:
                    start = int(first)
                    end = int(last) if last else size - 1
                else:  # suffix form: "bytes=-500" = the final 500 bytes
                    start, end = max(0, size - int(last)), size - 1
            except ValueError:
                return super().do_GET()

            if start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return

            end = min(end, size - 1)
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            with open(path, "rb") as fh:
                fh.seek(start)
                self.wfile.write(fh.read(end - start + 1))

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/__save":
                self.send_error(404)
                return
            name = urllib.parse.parse_qs(parsed.query).get("name", [""])[0]
            target = os.path.normpath(os.path.join(root, name))
            if not target.startswith(os.path.abspath(root)):
                self.send_error(403)  # never write outside the repo
                return
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
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
const JOBS = %s, MAX = %d, LIMIT = %d;

// Resolve once the frame for `at` is actually decoded and paintable.
// `seeked` fires when the seek completes, which is not the same instant the
// frame is ready to composite, so a rAF is awaited behind it.
const frameAt = (src, at) => new Promise((res, rej) => {
  const v = document.createElement('video');
  v.muted = true; v.preload = 'auto'; v.playsInline = true;
  v.onerror = () => rej(new Error('decode failed'));
  v.onloadeddata = () => {
    const t = at > 0 ? Math.min(at, Math.max(0, v.duration - 0.05))
                     : v.duration / 2;
    v.onseeked = () => requestAnimationFrame(() => res(v));
    v.currentTime = t;
  };
  v.src = src;
});

(async () => {
  const log = [];
  for (const job of JOBS) {
    try {
      const v = await frameAt('/' + job.in, job.at);
      const scale = Math.min(1, MAX / Math.max(v.videoWidth, v.videoHeight));
      const w = Math.round(v.videoWidth * scale);
      const h = Math.round(v.videoHeight * scale);
      if (Math.max(w, h) > LIMIT) throw new Error('over the px limit');

      const c = document.createElement('canvas');
      c.width = w; c.height = h;
      c.getContext('2d').drawImage(v, 0, 0, w, h);

      const blob = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.82));
      await fetch('/__save?name=' + encodeURIComponent(job.out),
                  { method: 'POST', body: blob });
      log.push(job.out + ' ' + w + 'x' + h + ' @' + v.currentTime.toFixed(2) + 's');
    } catch (e) {
      log.push('FAILED ' + job.in + ': ' + e.message);
    }
  }
  window.__done = log.join(' | ');
})();
</script></body>"""


def run(*args):
    return subprocess.run(["agent-browser", *args, "--session", SESSION],
                          capture_output=True, text=True, timeout=300)


def parse(spec):
    """"clip.mp4@2.5" -> job dict. Bare "clip.mp4" defaults to 1.0s."""
    path, _, at = spec.partition("@")
    stem = os.path.splitext(os.path.basename(path))[0]
    return {
        "in": path,
        "out": f"media/photos/{stem}-poster.jpg",
        "at": float(at) if at else 1.0,
    }


def main(argv):
    if not argv:
        print(__doc__)
        return 2

    jobs = [parse(a) for a in argv]
    for job in jobs:
        if not os.path.exists(job["in"]):
            print(f"missing input: {job['in']}", file=sys.stderr)
            return 2

    root = os.path.abspath(os.getcwd())
    outbox = []
    httpd = make_server(root, outbox)
    port = httpd.server_address[1]

    page = os.path.join(root, ".vidposter.html")
    with open(page, "w") as fh:
        fh.write(PAGE % (json.dumps(jobs), MAX_EDGE, LIMIT))

    try:
        run("set", "viewport", "800", "600")
        run("open", f"http://127.0.0.1:{port}/.vidposter.html")
        for _ in range(60):
            time.sleep(1.5)
            res = run("eval", "window.__done || ''")
            out = res.stdout.strip().strip('"')
            if out:
                print(out.replace(" | ", "\n"))
                break
    finally:
        run("close")
        httpd.shutdown()
        os.remove(page)

    print()
    for name, size in outbox:
        print(f"  wrote {name}  ({size // 1024}KB)")
    print(f"\n{len(outbox)}/{len(jobs)} posters written", file=sys.stderr)
    return 0 if len(outbox) == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
