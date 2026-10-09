#!/usr/bin/env python3
"""shots — capture the site from the headless browser for visual review.

Two things make naive screenshotting useless in this sandbox:

1. There is no Arabic font installed (`fc-list | grep -c arab` returns 0), so
   Arabic renders as empty boxes. A screenshot of the real page therefore says
   nothing about whether the layout reads — and must never be sent to the
   client as evidence. `--latinize` swaps Arabic runs for Latin filler of
   similar length so spacing, wrapping, contrast and rhythm can be judged.

2. Full-page capture can exceed the 2000px read limit. Captures here are
   always viewport-sized at explicit scroll offsets instead.

Usage:
  python3 tools/shots.py [page] [--latinize] [--size WxH] [--offsets 0,900,...]
"""
import functools
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time

SESSION = "shots"
LIMIT = 2000

# Replaces Arabic text in place, keeping element structure untouched, so the
# capture shows the real layout with legible glyphs.
LATINIZE = r"""
(() => {
  const WORDS = ('qahwa karak majlis sadu dallah thobe souq doha waab gharrafa '
    + 'hospitality heritage saffron cardamom gathering warmth aroma tradition '
    + 'modern elegance crafted blend evening terrace lantern woven').split(' ');
  let seed = 7;
  const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
  const filler = (n) => {
    let out = [];
    let len = 0;
    while (len < n) {
      const w = WORDS[Math.floor(rnd() * WORDS.length)];
      out.push(w);
      len += w.length + 1;
    }
    return out.join(' ').slice(0, Math.max(n, 2));
  };
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const hits = [];
  while (walker.nextNode()) {
    const t = walker.currentNode;
    if (/[\u0600-\u06FF]/.test(t.nodeValue)) hits.push(t);
  }
  hits.forEach(t => {
    const raw = t.nodeValue.trim();
    t.nodeValue = filler(raw.length);
  });
  document.documentElement.setAttribute('lang', 'en');
  return hits.length;
})()
"""


def serve(root):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=root)

    class Quiet(socketserver.TCPServer):
        allow_reuse_address = True

    httpd = Quiet(("127.0.0.1", 0), handler)
    httpd.RequestHandlerClass.log_message = lambda *a, **k: None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1], httpd.shutdown


def run(*args):
    return subprocess.run(["agent-browser", *args, "--session", SESSION],
                          capture_output=True, text=True, timeout=240)


def main(argv):
    latinize = "--latinize" in argv
    argv = [a for a in argv if a != "--latinize"]

    vw, vh = 1400, 900
    if "--size" in argv:
        i = argv.index("--size")
        vw, vh = (int(x) for x in argv[i + 1].lower().split("x"))
        del argv[i:i + 2]
    if max(vw, vh) > LIMIT:
        print(f"refusing {vw}x{vh}: over the {LIMIT}px read limit", file=sys.stderr)
        return 2

    offsets = [0, 820, 1640, 2460, 3280, 4100]
    if "--offsets" in argv:
        i = argv.index("--offsets")
        offsets = [int(x) for x in argv[i + 1].split(",")]
        del argv[i:i + 2]

    page = argv[0] if argv else "index.html"
    root = os.getcwd()
    outdir = os.path.join(".preview", "shots")
    os.makedirs(outdir, exist_ok=True)

    port, shutdown = serve(root)
    try:
        run("set", "viewport", str(vw), str(vh))
        run("open", f"http://127.0.0.1:{port}/{page}")
        time.sleep(2.5)

        if latinize:
            res = run("eval", LATINIZE)
            print(f"latinised text nodes: {res.stdout.strip()}")

        # Reveal animations are driven by IntersectionObserver; force every
        # [data-reveal] visible so a static capture is not full of blanks.
        run("eval", "document.querySelectorAll('[data-reveal]')"
                    ".forEach(e=>e.classList.add('is-visible')); 'ok'")
        time.sleep(0.6)

        tag = "latin" if latinize else "ar"
        written = []
        for off in offsets:
            run("eval", f"window.scrollTo(0,{off}); '{off}'")
            time.sleep(1.0)
            out = os.path.abspath(os.path.join(outdir, f"{tag}-{off:05d}.png"))
            run("screenshot", out)
            if os.path.exists(out):
                written.append(out)
                print(os.path.relpath(out, root))
    finally:
        run("close")
        shutdown()

    print(f"\n{len(written)} captures at {vw}x{vh}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
