"""Images for the tracking issues (label `taak`) -> docs/img/taak-*.png.

    .venv/bin/python scripts/render_tasks.py

Samples use render_sample.render_lines (same shaping/rendering as the test bank).
The spur images (#18) draw glyph outlines large with skia, the spot from fontbakery
circled and a zoomed inset. Commit and push docs/img/ before linking them in issues.
"""
import json
import sys
from pathlib import Path

import skia
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from compare import Font  # noqa: E402
from render_sample import PAPER, render_lines  # noqa: E402

FONT = ROOT / "fonts" / "ttf" / "Cogncur-Regular.ttf"
IMG = ROOT / "docs" / "img"
INK = "1E4FB8"
RED = "C8102E"
LABEL_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"

# fontbakery "jaggy segments" spots (font units): glyph -> (x, y)
SPURS = {"W": (737, 327), "W1": (953, 342), "ccgt": (-308, -398)}


def labelled(img, text):
    """Image with a small caption above it."""
    f = ImageFont.truetype(LABEL_FONT, 26)
    out = Image.new("RGB", (max(img.width, int(f.getlength(text)) + 32), img.height + 44), PAPER)
    ImageDraw.Draw(out).text((16, 10), text, font=f, fill=(60, 60, 60))
    out.paste(img, (0, 44))
    return out


def stack(*imgs):
    w = max(i.width for i in imgs)
    out = Image.new("RGB", (w, sum(i.height for i in imgs)), PAPER)
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.height
    return out


def save(img, name):
    p = IMG / f"taak-{name}.png"
    img.save(p, optimize=True)
    print(p.relative_to(ROOT), img.size)


class SkiaPen(BasePen):
    def __init__(self, gs):
        super().__init__(gs)
        self.path = skia.Path()

    def _moveTo(self, p): self.path.moveTo(*p)
    def _lineTo(self, p): self.path.lineTo(*p)
    def _qCurveToOne(self, p1, p2): self.path.quadTo(*p1, *p2)
    def _curveToOne(self, p1, p2, p3): self.path.cubicTo(*p1, *p2, *p3)
    def _closePath(self): self.path.close()


def outline_image(tt, glyph, spot, title):
    gs = tt.getGlyphSet()
    pen = SkiaPen(gs)
    gs[glyph].draw(pen)
    path = pen.path
    b = path.computeTightBounds()
    s, pad = 0.42, 60
    w = int((b.width()) * s) + 2 * pad
    h = int((b.height()) * s) + 2 * pad
    zoom, zw = 7.0, 300                              # inset: 7x around the spot
    W, H = w + zw + 3 * pad, max(h, zw + 2 * pad)
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.clear(skia.Color(*PAPER))
    fill = skia.Paint(Color=skia.Color(0x1E, 0x4F, 0xB8, 70), AntiAlias=True)
    line = skia.Paint(Color=skia.Color(0x1E, 0x4F, 0xB8), AntiAlias=True, Style=skia.Paint.kStroke_Style)
    red = skia.Paint(Color=skia.Color(0xC8, 0x10, 0x2E), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=3)

    def place(sc, ox, oy, x0, y0):
        c.save()
        c.translate(ox, oy)
        c.scale(sc, -sc)
        c.translate(-x0, -y0)

    # whole glyph (y up -> flip)
    place(s, pad, pad + h - 2 * pad, b.left(), b.top())
    c.drawPath(path, fill)
    line.setStrokeWidth(1.5 / s)
    c.drawPath(path, line)
    c.restore()
    sx = pad + (spot[0] - b.left()) * s
    sy = pad + h - 2 * pad - (spot[1] - b.top()) * s
    c.drawCircle(sx, sy, 22, red)
    # inset
    ix, iy = w + 2 * pad, pad
    c.save()
    c.clipRect(skia.Rect.MakeXYWH(ix, iy, zw, zw))
    place(zoom, ix + zw / 2, iy + zw / 2, spot[0], spot[1])
    c.drawPath(path, fill)
    line.setStrokeWidth(2 / zoom)
    c.drawPath(path, line)
    c.restore()
    c.drawRect(skia.Rect.MakeXYWH(ix, iy, zw, zw), red)
    c.drawLine(sx + 22, sy, ix, iy + zw / 2, red)
    img = Image.fromarray(surf.makeImageSnapshot().toarray()[:, :, :3])
    return labelled(img, title)


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    font = Font(FONT)
    tt = TTFont(FONT)

    # 14: ľ with and without ss01 (Slovak words starting with ľ)
    words = ["ľad ľavý"]
    save(stack(labelled(render_lines(font, words, 200, {}, INK), "Standaard"),
               labelled(render_lines(font, words, 200, {"ss01": True}, INK), "Met ss01: de instreek raakt de haček")),
         "lcaron-ss01")

    # 15: Dutch stressed ij at the end of a word vs inside
    save(stack(labelled(render_lines(font, ["zíj́ wíj́ bíj́"], 110, {}, INK), "Klemtoon op ij aan het einde van een woord"),
               labelled(render_lines(font, ["zíj́n bíj́na"], 110, {}, INK), "Binnen een woord")),
         "ij-accent")

    # 16: Ģ next to ģ, in Latvian names
    save(render_lines(font, ["Ģ ģ G g", "Ģirts Ģederts ģimene"], 110, {}, INK), "G-komma")

    # 17: missing signs: Cogncur shows an empty box; reference shapes in Georgia
    ref = Image.new("RGB", (900, 230), PAPER)
    d = ImageDraw.Draw(ref)
    d.text((40, 20), "¶   ™", font=ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia.ttf", 160),
           fill=tuple(int(INK[i:i + 2], 16) for i in (0, 2, 4)))
    save(stack(labelled(render_lines(font, ["¶ Cogncur™"], 110, {}, INK), "Cogncur nu: de tekens ontbreken (leeg vakje)"),
               labelled(ref, "Zo zien de tekens eruit (voorbeeld in een gewoon lettertype)")),
         "pilcrow-tm")

    # 18: spurs, outlines with the spot circled + zoom
    for g, spot in SPURS.items():
        what = {"W": "W", "W1": "W1 (variant van W)", "ccgt": "ccgt (verbinding)"}[g]
        save(outline_image(tt, g, spot, f"{what}: uitstekend puntje (rood omcirkeld, rechts 7x vergroot)"),
             f"spur-{g}")

    # 19: letters with an inferred accent position
    comp = json.loads((ROOT / "build" / "composites.json").read_text())
    chars = [e["char"] for e in comp if e.get("inferred")]
    lower = [c for c in chars if c == c.lower()]
    upper = [c for c in chars if c != c.lower()]
    rows = [" ".join(lower[i:i + 14]) for i in range(0, len(lower), 14)] + \
           [" ".join(upper[i:i + 14]) for i in range(0, len(upper), 14)]
    save(render_lines(font, rows, 90, {}, INK), "geschatte-accenten")


if __name__ == "__main__":
    main()
