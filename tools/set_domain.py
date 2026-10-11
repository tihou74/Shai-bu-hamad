#!/usr/bin/env python3
"""set_domain — change the site's canonical host everywhere, in one go.

The host is not written in one place. It appears in index.html (og:url,
og:image, canonical, twitter:image), in the JSON-LD block (url, logo, image
for the organisation and both branches), in sitemap.xml, in robots.txt, and in
the www redirect in .htaccess. Twenty-odd occurrences across five files.

Editing them by hand is how a site ends up with a canonical tag pointing at a
URL the server redirects away from — a contradiction crawlers resolve by
trusting neither, and one that produces no error anywhere. So this exists to
make the change atomic and checkable instead.

Usage:
    python3 tools/set_domain.py                      # report current state
    python3 tools/set_domain.py www.example.com      # switch to that host
    python3 tools/set_domain.py example.com          # switch to the apex

Pass the host exactly as it should be canonical, with or without www. The
scheme is always https; there is no reason to offer plain http as an option.

What it does NOT do: flip the www redirect direction in .htaccess. That is a
RewriteRule, not a string, and silently rewriting rewrite rules is how you
break a site at 2am. The script tells you when the direction no longer matches
the host you chose, and you change those four lines yourself.
"""
import os
import re
import sys

FILES = ["index.html", "404.html", "sitemap.xml", "robots.txt", ".htaccess"]
HOST_RE = re.compile(r"https://((?:[a-z0-9-]+\.)+[a-z]{2,})(?=[/\"'<\s]|$)", re.I)

# Hosts that belong to someone else and must never be rewritten: the menu
# platform, the fonts CDN, the social accounts, the schema vocabulary.
FOREIGN = (
    "yallaqrcodes.com", "fonts.googleapis.com", "fonts.gstatic.com",
    "schema.org", "instagram.com", "tiktok.com", "facebook.com",
    "snapchat.com", "docs.github.com", "github.com", "gandi.net",
    "aeserver.com", "qhost.qa", "domains.qa", "search.google.com",
)


def is_ours(host):
    return not any(host == f or host.endswith("." + f) for f in FOREIGN)


def current_hosts():
    found = {}
    for path in FILES:
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        for host in HOST_RE.findall(text):
            if is_ours(host):
                found.setdefault(host, []).append(path)
    return found


def report():
    found = current_hosts()
    if not found:
        print("no own-domain URLs found yet")
        return 0
    for host, files in sorted(found.items()):
        print(f"{host}")
        for path in sorted(set(files)):
            n = sum(1 for h in HOST_RE.findall(open(path, encoding='utf-8').read())
                    if h == host)
            print(f"    {path}  x{n}")
    if len(found) > 1:
        print("\nWARNING: more than one own host is in use. "
              "That is the inconsistency this script exists to prevent.",
              file=sys.stderr)
        return 1
    return 0


def apply(new_host):
    found = current_hosts()
    if not found:
        print("nothing to replace — no own-domain URLs present", file=sys.stderr)
        return 2
    if len(found) > 1:
        print(f"refusing: {len(found)} different own hosts present "
              f"({', '.join(sorted(found))}). Fix that first.", file=sys.stderr)
        return 2

    old_host = next(iter(found))
    if old_host == new_host:
        print(f"already {new_host}; nothing to do")
        return 0

    total = 0
    for path in FILES:
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        new_text, n = re.subn(
            r"https://" + re.escape(old_host) + r"(?=[/\"'<\s]|$)",
            "https://" + new_host, text)
        # Bare hostname mentions outside a URL — robots.txt comments, the
        # Sitemap: line, prose in .htaccess comments.
        new_text, n2 = re.subn(r"(?<![\w.-])" + re.escape(old_host)
                               + r"(?![\w.-])", new_host, new_text)
        if n + n2:
            open(path, "w", encoding="utf-8").write(new_text)
            print(f"  {path}: {n + n2} replaced")
            total += n + n2

    print(f"\n{old_host} -> {new_host}  ({total} occurrences)")

    wants_www = new_host.startswith("www.")
    if os.path.exists(".htaccess"):
        rules = open(".htaccess", encoding="utf-8").read()
        forces_www = "RewriteRule ^ https://www.%{HTTP_HOST}" in rules
        if wants_www != forces_www:
            print("\n*** ACTION NEEDED ***", file=sys.stderr)
            print(f"The canonical host is now {new_host}, but .htaccess still "
                  f"redirects to the {'apex' if forces_www else 'www'} form.",
                  file=sys.stderr)
            print("Reverse the www block in .htaccess by hand, or the "
                  "canonical tag will point at a URL that 301s away from it.",
                  file=sys.stderr)
            return 1

    print("www redirect direction matches the canonical host")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(report())
    host = args[0].strip().lower()
    host = re.sub(r"^https?://", "", host).rstrip("/")
    if not re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z]{2,}", host):
        print(f"not a hostname: {host}", file=sys.stderr)
        sys.exit(2)
    sys.exit(apply(host))
