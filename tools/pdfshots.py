#!/usr/bin/env python3
"""pdfshots — render PDF pages to clean PNGs so they can actually be looked at.

This sandbox has no pdftotext, no poppler, no ghostscript and no network to
install any of them. Chromium does ship a PDF renderer, so the PDF is served
over localhost and each page is captured individually through an <embed> with
the viewer chrome switched off (`toolbar=0&navpanes=0`). One page per capture
beats scrolling: PageDown does not reach the PDF plugin reliably.

Every capture is sized to stay well inside the 2000px limit (see
.kiro/steering/image-safety.md) — fixed viewport, and `--full` is never used.

Usage:
  python3 tools/pdfshots.py <file.pdf> [first] [last] [--size WxH]

Examples:
  python3 tools/pdfshots.py content/profile/profile-2026.pdf 1 26
  python3 tools/pdfshots.py doc.pdf 3 3 --size 1200x1600   # portrait page
"""
import functools
import http.server
import os
import socketserver
import subprocess
import sys
import threading
import time

SESSION = "pdfshots"
SETTLE_FIRST = 3.0
SETTLE_PAGE = 1.6
LIMIT = 2000


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
    if not argv:
        print(__doc__)
        return 2

    vw, vh = 1600, 1000
    if "--size" in argv:
        i = argv.index("--size")
        vw, vh = (int(x) for x in argv[i + 1].lower().split("x"))
        del argv[i:i + 2]
    if max(vw, vh) > LIMIT:
        print(f"refusing {vw}x{vh}: exceeds the {LIMIT}px read limit",
              file=sys.stderr)
        return 2

    pdf = argv[0]
    first = int(argv[1]) if len(argv) > 1 else 1
    last = int(argv[2]) if len(argv) > 2 else first + 11

    root = os.getcwd()
    rel = os.path.relpath(os.path.abspath(pdf), root)
    if rel.startswith("..") or not os.path.exists(pdf):
        print(f"not found under cwd: {pdf}", file=sys.stderr)
        return 2

    stem = os.path.splitext(os.path.basename(pdf))[0]
    outdir = os.path.join(".preview", stem)
    os.makedirs(outdir, exist_ok=True)

    port, shutdown = serve(root)
    wrapper = os.path.join(root, ".pdfshot-wrapper.html")
    written = []
    try:
        run("set", "viewport", str(vw), str(vh))
        for n in range(first, last + 1):
            frag = f"#page={n}&toolbar=0&navpanes=0&scrollbar=0&view=Fit"
            with open(wrapper, "w") as fh:
                fh.write(
                    '<!doctype html><meta charset="utf-8">'
                    '<style>html,body{margin:0;padding:0;overflow:hidden;'
                    'background:#fff}embed{display:block;width:100vw;'
                    'height:100vh;border:0}</style>'
                    f'<embed type="application/pdf" '
                    f'src="http://127.0.0.1:{port}/{rel}{frag}">'
                )
            run("open", f"http://127.0.0.1:{port}/.pdfshot-wrapper.html")
            time.sleep(SETTLE_FIRST if n == first else SETTLE_PAGE)
            out = os.path.abspath(os.path.join(outdir, f"page-{n:02d}.png"))
            run("screenshot", out)
            if os.path.exists(out):
                written.append(out)
                print(os.path.relpath(out, root))
            else:
                print(f"page {n}: capture failed", file=sys.stderr)
    finally:
        run("close")
        shutdown()
        if os.path.exists(wrapper):
            os.remove(wrapper)

    print(f"\n{len(written)} pages captured at {vw}x{vh} in {outdir}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
