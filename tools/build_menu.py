#!/usr/bin/env python3
"""build_menu — render data/menu.json into index.html.

Why a generator instead of fetching the JSON in the browser: a restaurant menu
is the single most searched part of a restaurant site, so it has to exist in
the HTML that a crawler and a no-JavaScript visitor receive. Keeping the JSON
as the only place prices are edited gives us both — one source of truth, and
static markup.

Run after every edit to data/menu.json:
    python3 tools/build_menu.py
"""
import html
import json
import re
import sys

DATA = "data/menu.json"
PAGE = "index.html"
START = "<!-- MENU:START"
END = "<!-- MENU:END -->"


def esc(s):
    return html.escape(s or "", quote=True)


def render(menu):
    cur = esc(menu.get("currency", ""))
    live = (menu.get("menuUrl") or "").strip()
    out = []

    # The category filters only exist to narrow a long priced list. With the
    # prices living on the QR platform the buttons would filter nine cards
    # that all say the same amount of nothing, so they are not rendered while
    # menuUrl is set. app.js reads `.filter` with querySelectorAll and calls
    # forEach on the result, which is a no-op on an empty NodeList — removing
    # the buttons needs no change there, and was checked rather than assumed.
    if not live:
        out.append('      <div class="filters" role="group" aria-label="تصفية المنيو">')
        out.append('        <button class="filter" type="button" data-filter="all" '
                   'aria-pressed="true">الكل</button>')
        for c in menu["categories"]:
            out.append(f'        <button class="filter" type="button" '
                       f'data-filter="{esc(c["id"])}" aria-pressed="false">'
                       f'{esc(c["ar"])}</button>')
        out.append("      </div>")

    # No item cards at all while the menu is hosted elsewhere — the owner's
    # instruction, and he is right about the thing that matters most: these
    # nine names came out of the 2026 profile PDF, not out of his live menu,
    # and that platform could not be read from here to check them against it.
    # A card is a promise. Nine unverified promises with no prices under them
    # are worse than one link to the menu he actually maintains.
    #
    # The cost, stated plainly so nobody has to rediscover it: a menu is the
    # most searched part of a restaurant site, and the words "كرك" and "قهوة
    # عربية" now live on someone else's domain instead of this page. If the
    # prices ever arrive, fill them into data/menu.json, drop menuUrl, and the
    # cards and their filters come back with their keywords.
    if not live:
        out.append('      <ul class="grid grid--3">')
        for it in menu["items"]:
            price = it.get("price")
            out.append(f'        <li class="card" data-category="{esc(it["category"])}"'
                       f'{" data-featured" if it.get("featured") else ""} data-reveal>')
            out.append(f'          <h3>{esc(it["ar"])}</h3>')
            if it.get("en"):
                out.append(f'          <p class="lat">{esc(it["en"])}</p>')
            if it.get("desc"):
                out.append(f'          <p>{esc(it["desc"])}</p>')
            price_html = ('<span class="todo">السعر في انتظار البيانات</span>'
                          if price is None
                          else f'{esc(str(price))} <span>{cur}</span>')
            out.append(f'          <p class="card__price">{price_html}</p>')
            out.append("        </li>")
        out.append("      </ul>")

    if live:
        # target="_blank" with rel="noopener": the menu is somebody else's
        # domain, and a visitor halfway down a long page should not lose it to
        # a sideways navigation. `noopener` also denies the opened page a
        # handle on this one.
        out.append('')
        out.append('      <aside class="menu-live" data-reveal>')
        out.append('        <div>')
        out.append('          <h3>المنيو الكامل بالأسعار</h3>')
        out.append('          <p>نفس المنيو في الفرعين — West Walk و Gulf Mall.</p>')
        out.append('        </div>')
        out.append(f'        <a class="btn btn--solid menu-live__cta" href="{esc(live)}"'
                   ' target="_blank" rel="noopener">')
        out.append('          افتح المنيو')
        # An inline SVG rather than the character "↗". The glyph is missing
        # from some font stacks and falls back to a tofu box — it rendered as
        # an empty square in review here — and a button that ships a visible
        # placeholder square is worse than a button with no icon. Stroked
        # paths use currentColor, so it follows the button's own colour on
        # hover with nothing extra.
        out.append('          <svg class="menu-live__arrow" viewBox="0 0 16 16" '
                   'width="13" height="13" fill="none" stroke="currentColor" '
                   'stroke-width="1.6" stroke-linecap="round" '
                   'stroke-linejoin="round" aria-hidden="true" focusable="false">')
        out.append('            <path d="M5 11 11 5"/><path d="M6 5h5v5"/>')
        out.append('          </svg>')
        out.append('        </a>')
        out.append('      </aside>')

    return "\n".join(out)


def main():
    with open(DATA, encoding="utf-8") as fh:
        menu = json.load(fh)
    with open(PAGE, encoding="utf-8") as fh:
        page = fh.read()

    pattern = re.compile(
        re.escape(START) + r".*?-->(.*?)" + re.escape(END),
        re.DOTALL,
    )
    if not pattern.search(page):
        print(f"markers {START} ... {END} not found in {PAGE}", file=sys.stderr)
        return 2

    block = render(menu)
    header = (f"{START} — generated by tools/build_menu.py from {DATA}.\n"
              "           Do not hand-edit: edit the JSON and re-run the script. -->")
    page = pattern.sub(lambda m: f"{header}\n{block}\n      {END}", page, count=1)

    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(page)

    live = (menu.get("menuUrl") or "").strip()
    if live:
        print(f"rendered the link-out block only -> {live}")
        print(f"held back: {len(menu['items'])} items and "
              f"{len(menu['categories'])} category filters "
              f"(unset menuUrl to render them again)")
    else:
        print(f"rendered {len(menu['items'])} items "
              f"across {len(menu['categories'])} categories")
        missing = sum(1 for i in menu["items"] if i.get("price") is None)
        if missing:
            print(f"note: {missing} items still have no price", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
