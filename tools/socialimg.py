#!/usr/bin/env python3
"""socialimg — build the square favicons and the 1200x630 share card.

Both of these are composites: a photograph or a flat brand colour, with the
wordmark laid over it. There is no Pillow or ImageMagick in this sandbox and
no registry access to install them, so the browser composes them — the same
approach imgfix and vidposter already use, and the one piece of tooling in
this repo that genuinely needs layout rather than pixel maths, which is what a
browser is for.

Why each file exists:

  icon-512 / icon-180 / icon-32
      The favicon was brand/logo/logo-primary.png at 1554x460. A favicon is
      drawn into a square, so a 3.4:1 wordmark arrived in the tab as an
      illegible smear. These carry the mark alone, centred on the brand brown,
      at the three sizes that matter: 512 for Android and high-DPI tabs, 180
      for the iOS home screen, 32 for the classic tab slot.

  share-card.jpg (1200x630)
      og:image was a relative path, so WhatsApp showed no image at all. Making
      it absolute was half the fix; the other half is the ratio. Every
      platform centre-crops to its own frame, and cropping the 4:3 shopfront
      photograph cut the lit sign — the one thing worth seeing — out of shot.
      1200x630 is the ratio Open Graph and Twitter both target, so nothing is
      cropped.

Usage:
    python3 tools/socialimg.py            # build everything
    python3 tools/socialimg.py icons      # just the favicons
    python3 tools/socialimg.py card       # just the share card
"""
import http.server
import os
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse

SESSION = "socialimg"
LIMIT = 2000  # .kiro/steering/image-safety.md

BROWN_DARK = "#2A1C0C"

# The mark, not the full lockup. The lockup's hairline Latin row disappears
# below roughly 200px, and at 32px even the Arabic needs all the room there is.
MARK = "/assets/img/mark-cream.png"

# The shopfront at Gulf Mall: the lit sign reads at a glance, which is what a
# share card has to do in a chat thread.
CARD_PHOTO = "/media/photos/gulf-mall/deco-02.jpeg"


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
            target = os.path.normpath(os.path.join(root, name))
            if not target.startswith(os.path.abspath(root)):
                self.send_error(403)
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
const JOBS = __JOBS__, LIMIT = __LIMIT__;

const load = (src) => new Promise((res, rej) => {
  const im = new Image();
  im.onload = () => res(im);
  im.onerror = () => rej(new Error('load failed: ' + src));
  im.src = src;
});

// Draw `im` scaled to fit inside w x h without distortion, centred.
// `cover` fills the box and crops the overflow; otherwise it is letterboxed.
function fit(ctx, im, w, h, cover) {
  const s = cover ? Math.max(w / im.width, h / im.height)
                  : Math.min(w / im.width, h / im.height);
  const dw = im.width * s, dh = im.height * s;
  ctx.drawImage(im, (w - dw) / 2, (h - dh) / 2, dw, dh);
}

(async () => {
  const log = [];
  for (const job of JOBS) {
    try {
      if (Math.max(job.w, job.h) > LIMIT) throw new Error('over the px limit');
      const c = document.createElement('canvas');
      c.width = job.w; c.height = job.h;
      const ctx = c.getContext('2d');

      if (job.kind === 'icon') {
        ctx.fillStyle = job.bg;
        ctx.fillRect(0, 0, job.w, job.h);
        const mark = await load(job.mark);
        // Inset by a touch over a tenth each side, so the mark has air
        // around it. A favicon that runs to its own edges reads as a smudge
        // once the browser rounds the corners.
        const pad = job.w * 0.12;
        ctx.save();
        ctx.translate(pad, 0);
        fit(ctx, mark, job.w - pad * 2, job.h, false);
        ctx.restore();
      } else {
        const photo = await load(job.photo);
        fit(ctx, photo, job.w, job.h, true);

        // A solid band, not a gradient.
        //
        // The first version faded the bottom to 88% brown and put the cream
        // wordmark on it. In review the mark landed over the pale floor and
        // tables of this particular photograph and all but vanished — a
        // gradient is at the mercy of whatever is underneath it, and a share
        // card is judged as a thumbnail in a chat thread where there is no
        // second look.
        //
        // A band is deterministic: the mark always sits on the same colour at
        // the same contrast no matter which photograph is swapped in behind
        // it. The short fade above it keeps the edge from reading as a
        // sticker laid on top of the image.
        const band = Math.round(job.h * 0.26);
        const fade = ctx.createLinearGradient(0, job.h - band - job.h * 0.14,
                                              0, job.h - band);
        fade.addColorStop(0, 'rgba(26,17,7,0)');
        fade.addColorStop(1, 'rgba(26,17,7,0.96)');
        ctx.fillStyle = fade;
        ctx.fillRect(0, job.h - band - job.h * 0.14, job.w, job.h * 0.14);

        ctx.fillStyle = 'rgba(26,17,7,0.96)';
        ctx.fillRect(0, job.h - band, job.w, band);

        // The hairline under the mark on the opening curtain, carried over so
        // the card belongs to the same set as the site.
        ctx.fillStyle = 'rgba(214,204,184,0.34)';
        ctx.fillRect(job.w * 0.30, job.h - band, job.w * 0.40, 1);

        const mark = await load(job.mark);
        const mw = job.w * 0.30;
        const mh = mark.height * (mw / mark.width);
        ctx.drawImage(mark, (job.w - mw) / 2,
                      job.h - band / 2 - mh / 2, mw, mh);
      }

      const png = /\\.png$/i.test(job.out);
      const blob = await new Promise(r => png
        ? c.toBlob(r, 'image/png')
        : c.toBlob(r, 'image/jpeg', 0.88));
      await fetch('/__save?name=' + encodeURIComponent(job.out),
                  { method: 'POST', body: blob });
      log.push(job.out + ' ' + job.w + 'x' + job.h);
    } catch (e) {
      log.push('FAILED ' + job.out + ': ' + e.message);
    }
  }
  window.__done = log.join(' | ');
})();
</script></body>"""


def jobs_for(what):
    jobs = []
    if what in ("all", "icons"):
        for size in (512, 180, 32):
            jobs.append({"kind": "icon", "w": size, "h": size,
                         "bg": BROWN_DARK, "mark": MARK,
                         "out": f"assets/img/icon-{size}.png"})
    if what in ("all", "card"):
        jobs.append({"kind": "card", "w": 1200, "h": 630,
                     "photo": CARD_PHOTO, "mark": MARK,
                     "out": "assets/img/share-card.jpg"})
    return jobs


def run(*args):
    return subprocess.run(["agent-browser", *args, "--session", SESSION],
                          capture_output=True, text=True, timeout=300)


def main(argv):
    what = argv[0] if argv else "all"
    if what not in ("all", "icons", "card"):
        print(__doc__)
        return 2

    jobs = jobs_for(what)
    root = os.path.abspath(os.getcwd())
    for job in jobs:
        for key in ("mark", "photo"):
            if key in job and not os.path.exists(job[key].lstrip("/")):
                print(f"missing input: {job[key]}", file=sys.stderr)
                return 2

    outbox = []
    httpd = make_server(root, outbox)
    port = httpd.server_address[1]

    import json
    page = os.path.join(root, ".socialimg.html")
    # Token replacement rather than %-formatting: the page body is JavaScript
    # and CSS-ish text that legitimately contains % signs, and one of them in
    # a comment was enough to make %-formatting raise.
    body = (PAGE
            .replace("__JOBS__", json.dumps(jobs))
            .replace("__LIMIT__", str(LIMIT)))
    with open(page, "w") as fh:
        fh.write(body)

    try:
        run("set", "viewport", "900", "600")
        run("open", f"http://127.0.0.1:{port}/.socialimg.html")
        for _ in range(40):
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
    print(f"\n{len(outbox)}/{len(jobs)} written", file=sys.stderr)
    return 0 if len(outbox) == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
