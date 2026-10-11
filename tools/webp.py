#!/usr/bin/env python3
"""webp — write a .webp beside every JPEG or PNG the page serves.

Measured on this repo's photographs, WebP at quality 0.82 is 47% smaller than
the JPEGs already committed, and up to 67% on the ones with large flat areas
(the tea pour, the kabsa). Page speed is a stated Google ranking factor, and
on a phone in Doha it is the difference the visitor actually feels.

No encoder in this sandbox and no registry access, so the browser encodes:
`canvas.toBlob(..., 'image/webp')` is the same mechanism imgfix already uses
for JPEG, pointed at a different mime type.

How the files get used — and why the HTML is not touched:

    The obvious approach is <picture> with a WebP <source> and the JPEG as
    fallback. It was rejected. Six CSS rules in this project select images as
    direct children — `.plate > img`, `.pourshot > img`, `.topshot > img`,
    `.mirror > img`, `.cine__media img`, `.branch__media img` — and wrapping
    every image in <picture> makes the img a grandchild, so those rules stop
    matching and the layout silently falls apart. Thirty wrappings plus six
    selector rewrites is a lot of risk for a file-format change.

    The host is Apache/LiteSpeed, so it can do this properly instead:
    .htaccess checks the browser's Accept header and serves the .webp when
    the browser asked for WebP and the file exists, with Vary: Accept so
    caches keep the two apart. Zero HTML change, zero CSS change, exact
    fallback for anything that cannot read WebP.

    That does mean the saving only applies on Hostinger. On GitHub Pages the
    JPEGs are served as before — correct, just not as small.

Usage:
    python3 tools/webp.py                 # every image referenced by index.html
    python3 tools/webp.py path [path...]  # specific files
    python3 tools/webp.py --report        # show what exists and what it saved
"""
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse

SESSION = "webp"
QUALITY = 0.82
PAGES = ("index.html", "404.html")


def referenced():
    """Every raster image the pages actually serve, in repo order."""
    found = []
    for page in PAGES:
        if not os.path.exists(page):
            continue
        text = re.sub(r"<!--.*?-->", "", open(page, encoding="utf-8").read(),
                      flags=re.S)
        for ref in re.findall(r'(?:src|srcset|poster)="([^"?]+\.(?:jpe?g|png))"',
                              text):
            ref = ref.lstrip("/")
            if os.path.exists(ref) and ref not in found:
                found.append(ref)
    return found


def report():
    files = referenced()
    jt = wt = 0
    missing = []
    print(f"{'file':52} {'original':>10} {'webp':>9}  saving")
    for f in files:
        orig = os.path.getsize(f)
        w = os.path.splitext(f)[0] + ".webp"
        jt += orig
        if not os.path.exists(w):
            missing.append(f)
            print(f"{f[:52]:52} {orig // 1024:8d}KB {'—':>9}")
            continue
        ws = os.path.getsize(w)
        wt += ws
        print(f"{f[:52]:52} {orig // 1024:8d}KB {ws // 1024:7d}KB  "
              f"{(1 - ws / orig) * 100:5.1f}%")
    done = jt - sum(os.path.getsize(f) for f in missing)
    if done:
        print(f"\n{done // 1024}KB of images -> {wt // 1024}KB webp "
              f"({(1 - wt / done) * 100:.1f}% smaller)")
    if missing:
        print(f"{len(missing)} not yet converted", file=sys.stderr)
        return 1
    return 0


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
const LIST = __LIST__, Q = __Q__;
const load = (s) => new Promise((res, rej) => {
  const i = new Image();
  i.onload = () => res(i);
  i.onerror = () => rej(new Error('load failed'));
  i.src = s;
});
(async () => {
  const log = [];
  for (const [src, out] of LIST) {
    try {
      const im = await load('/' + src);
      const c = document.createElement('canvas');
      c.width = im.naturalWidth; c.height = im.naturalHeight;
      c.getContext('2d').drawImage(im, 0, 0);
      const blob = await new Promise(r => c.toBlob(r, 'image/webp', Q));
      if (!blob) throw new Error('no webp encoder');
      await fetch('/__save?name=' + encodeURIComponent(out),
                  { method: 'POST', body: blob });
      log.push(out + ' ' + blob.size);
    } catch (e) {
      log.push('FAILED ' + src + ': ' + e.message);
    }
  }
  window.__done = log.join(' | ');
})();
</script></body>"""


def run(*args):
    return subprocess.run(["agent-browser", *args, "--session", SESSION],
                          capture_output=True, text=True, timeout=600)


def convert(files):
    jobs = [[f, os.path.splitext(f)[0] + ".webp"] for f in files]
    root = os.path.abspath(os.getcwd())
    outbox = []
    httpd = make_server(root, outbox)
    port = httpd.server_address[1]
    page = os.path.join(root, ".webp.html")
    with open(page, "w") as fh:
        fh.write(PAGE.replace("__LIST__", json.dumps(jobs))
                     .replace("__Q__", str(QUALITY)))
    try:
        run("set", "viewport", "800", "600")
        run("open", f"http://127.0.0.1:{port}/.webp.html")
        for _ in range(120):
            time.sleep(2)
            out = run("eval", "window.__done || ''").stdout.strip().strip('"')
            if out:
                for line in out.split(" | "):
                    if line.startswith("FAILED"):
                        print(line, file=sys.stderr)
                break
    finally:
        run("close")
        httpd.shutdown()
        os.remove(page)

    # Discard any conversion that is not actually smaller.
    #
    # WebP is not universally better. sadu-textile.jpeg — a close weave of
    # fine repeating thread — came out 18.8% LARGER at this quality, because
    # that is exactly the kind of high-frequency detail its lossy encoder
    # spends bits on. Keeping it would make .htaccess serve the heavier file
    # to the newer browsers: a performance change that silently costs
    # performance, which is worse than doing nothing.
    #
    # So the win is verified per file, not assumed from the format.
    saved = 0
    kept = rejected = 0
    for name, size in outbox:
        src = next((f for f in files
                    if os.path.splitext(f)[0] + ".webp" == name), None)
        if not src:
            continue
        orig = os.path.getsize(src)
        if size >= orig:
            os.remove(name)
            rejected += 1
            print(f"  rejected {name}: {size // 1024}KB vs "
                  f"{orig // 1024}KB original — not a win")
            continue
        saved += orig - size
        kept += 1
    print(f"{kept}/{len(jobs)} kept, {saved // 1024}KB saved"
          + (f", {rejected} rejected as larger" if rejected else ""))
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--report":
        sys.exit(report())
    targets = args or referenced()
    targets = [t for t in targets if os.path.exists(t)]
    if not targets:
        print(__doc__)
        sys.exit(2)
    print(f"converting {len(targets)} images at quality {QUALITY}")
    sys.exit(convert(targets))
