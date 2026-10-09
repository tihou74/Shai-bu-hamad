# Image handling — the 2000px rule

Reading an image whose width **or** height exceeds 2000px makes the request fail
with `At least one of the image dimensions exceed max allowed size for
many-image requests: 2000 pixels`. The failure arrives *after* all the work is
finished, so the entire session and its credits are lost.

**Never read an image without probing it first.** Single chokepoint:

```bash
python3 tools/imgguard.py probe <file...>     # exit 2 = do not read
python3 tools/imgguard.py safe  <file>        # prints a <=1600px copy to read
python3 tools/imgguard.py dpi   4.0 12.0      # max safe DPI for a print layout
```

Rules that follow from it:

- Probe every image of unknown origin (user uploads, downloads, generated art).
- Print layouts: max DPI = `2000 / longest_edge_inches`. A 4×12in page caps at
  166 DPI, not 300.
- Figma `get_screenshot`: always pass `maxDimension` of 1600 or less.
- Browser captures: never use `--full`; set an explicit viewport instead.
- This sandbox has no Pillow, no ImageMagick and no PyPI/npm access, so
  `imgguard safe` downscales through a headless browser viewport. Don't reach
  for `pip install pillow` — it is blocked.
