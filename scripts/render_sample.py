"""Render sample text in a font to a PNG on writing lines (for issues and docs).

    python scripts/render_sample.py <font.ttf> <out.png> "line one" ["line two" ...]
        [--size 72] [--features ss08,ss09] [--ink 1E4FB8]

Uses the same HarfBuzz shaping + FreeType rendering as the test bank, so the
images show exactly what the fonts do. Writing lines follow Cogncur's three
zones: descender -682, baseline 0, x-height 682, ascender 1364 (UPM 2048).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
from compare import Font  # noqa: E402

PAPER = (250, 252, 255)
RULE = (169, 195, 232)
RULE_STRONG = (111, 147, 201)
MARGIN_RED = (232, 131, 143)


def render_lines(font, lines, size, features, ink):
    upem = font.upem
    s = size / upem
    row_h = int((1768 + 703 + 250) * s)          # full font height (hhea) + gap
    base_y = int((1768 + 120) * s)              # baseline inside a row
    pad_l, pad_r = int(size * 0.9), int(size * 0.4)
    shaped = [font.shape(t, features) for t in lines]
    width = max(int(sum(g[2] for g in sh) * s) for sh in shaped) + pad_l + pad_r
    img = Image.new("RGB", (width, row_h * len(lines) + int(size * 0.2)), PAPER)
    draw = ImageDraw.Draw(img)
    rgb = tuple(int(ink[i:i + 2], 16) for i in (0, 2, 4))
    draw.line([(int(size * 0.6), 0), (int(size * 0.6), img.height)], fill=MARGIN_RED, width=2)
    for i, sh in enumerate(shaped):
        top = i * row_h
        for units, col, w, dash in ((-1364, RULE, 1, False), (-682, RULE, 1, True),
                                    (0, RULE_STRONG, 2, False), (682, RULE, 1, False)):
            y = top + base_y + int(units * s)
            if dash:
                for x in range(0, width, 12):
                    draw.line([(x, y), (x + 6, y)], fill=col, width=w)
            else:
                draw.line([(0, y), (width, y)], fill=col, width=w)
        canvas = (width, row_h, base_y)
        g = font.render(sh, size, canvas)
        # font.render starts at 0.5 * size; shift to the page margin
        g = np.roll(g, pad_l - int(size * 0.5), axis=1)
        alpha = Image.fromarray(g)
        layer = Image.new("RGB", (width, row_h), rgb)
        img.paste(layer, (0, top), alpha)
    return img


def render_rows(font, rows, size):
    """rows: [(label, text, features, ink_hex)]; each row gets its own features
    and a label in the margin (e.g. 'zonder' / 'met ss08')."""
    from PIL import ImageFont
    upem = font.upem
    s = size / upem
    row_h = int((1768 + 703 + 250) * s)
    base_y = int((1768 + 120) * s)
    label_font = ImageFont.load_default(size=max(14, int(size * 0.24)))
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    label_w = max(probe.textlength(r[0], font=label_font) for r in rows)
    margin_x = int(label_w + size * 0.35)
    pad_l, pad_r = margin_x + int(size * 0.3), int(size * 0.4)
    shaped = [font.shape(r[1], r[2]) for r in rows]
    width = max(int(sum(g[2] for g in sh) * s) for sh in shaped) + pad_l + pad_r
    img = Image.new("RGB", (width, row_h * len(rows) + int(size * 0.2)), PAPER)
    draw = ImageDraw.Draw(img)
    draw.line([(margin_x, 0), (margin_x, img.height)], fill=MARGIN_RED, width=2)
    for i, ((label, _text, _feats, ink), sh) in enumerate(zip(rows, shaped)):
        top = i * row_h
        for units, col, w, dash in ((-1364, RULE, 1, False), (-682, RULE, 1, True),
                                    (0, RULE_STRONG, 2, False), (682, RULE, 1, False)):
            y = top + base_y + int(units * s)
            if dash:
                for x in range(0, width, 12):
                    draw.line([(x, y), (x + 6, y)], fill=col, width=w)
            else:
                draw.line([(0, y), (width, y)], fill=col, width=w)
        rgb = tuple(int(ink[k:k + 2], 16) for k in (0, 2, 4))
        draw.text((margin_x - size * 0.15, top + base_y - int(341 * s)), label, fill=rgb,
                  font=label_font, anchor="rm")
        g = font.render(sh, size, (width, row_h, base_y))
        g = np.roll(g, pad_l - int(size * 0.5), axis=1)
        img.paste(Image.new("RGB", (width, row_h), rgb), (0, top), Image.fromarray(g))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("font")
    ap.add_argument("out")
    ap.add_argument("lines", nargs="+")
    ap.add_argument("--size", type=int, default=72)
    ap.add_argument("--features", default="")
    ap.add_argument("--ink", default="1E4FB8")
    a = ap.parse_args()
    feats = {f: True for f in a.features.split(",") if f}
    img = render_lines(Font(a.font), a.lines, a.size, feats, a.ink)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    img.save(a.out, optimize=True)
    print(a.out, img.size)


if __name__ == "__main__":
    main()
