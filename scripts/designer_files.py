"""Editable vector files (SVG + EPS) for the designer, one folder per issue.

    python scripts/designer_files.py            # all designer issues -> docs/ontwerper/
    python scripts/designer_files.py schets-eth # only these issue ids

Per new glyph (unslanted, font units, origin = glyph origin, UPM 2048):
  <code>-<name>.svg  layers: hulplijnen, omtrek (outline, unslanted, for reference),
                     middenlijn (centre line = her 'Skeleton' layer),
                     vlakken (filled shapes such as dots = her 'Extra' layer)
  <code>-<name>.eps  only middenlijn + vlakken, for File > Import onto the Skeleton
                     layer in FontForge (open centre lines stay open, 1:1).
Per issue:
  overzicht.svg/.eps the issue's sample lines as set by the font (slanted 7.5°,
                     with joins), outline + centre line on writing lines.

Centre lines come from the 'skeleton' layer of the UFO (which export_ufo.py
stores slanted); accented letters are resolved through their components.
"""
import math
import sys
from pathlib import Path

import ufoLib2
from fontTools.misc.transform import Transform
from fontTools.pens.basePen import BasePen
from fontTools.pens.transformPen import TransformPen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from compare import Font  # noqa: E402

UFO = ROOT / "sources" / "Vtex-Regular.ufo"
TTF = ROOT / "fonts" / "ttf" / "Vtex-Regular.ttf"
OUT = ROOT / "docs" / "ontwerper"
TAN = math.tan(math.radians(7.5))
UNSLANT = Transform(1, 0, -TAN, 1, 0, 0)
GUIDES = [(-682, "onderlijn"), (0, "basislijn"), (682, "x-hoogte"), (1364, "bovenlijn")]
PEN = 68  # her round pen; used as margin around the EPS bounding box

INK, CENTRE, GUIDE, GUIDE_STRONG = "#1e1e1e", "#d0312d", "#a9c3e8", "#6f93c9"


# ------------------------------------------------------------- geometry
class Collect(BasePen):
    """Collects contours as (closed, [(op, pts)]); quadratics become cubics."""

    def __init__(self, glyphset=None):
        super().__init__(glyphset)
        self.contours, self.cur = [], None

    def _moveTo(self, p):
        self.cur = [("M", [p])]

    def _lineTo(self, p):
        self.cur.append(("L", [p]))

    def _curveToOne(self, p1, p2, p3):
        self.cur.append(("C", [p1, p2, p3]))

    def _closePath(self):
        self.contours.append((True, self.cur))

    def _endPath(self):
        self.contours.append((False, self.cur))


def draw_outline(font, name, pen):
    g = font[name]
    for c in g.contours:
        c.draw(pen)
    for comp in g.components:
        draw_outline(font, comp.baseGlyph, TransformPen(pen, comp.transformation))


def draw_layer(font, layer, name, pen):
    """A UFO layer ('skeleton' = centre lines, 'extra' = filled shapes); components
    (accented letters) are followed through the main layer."""
    lay = font.layers[layer]
    if name in lay:
        for c in lay[name].contours:
            c.draw(pen)
    for comp in font[name].components:
        draw_layer(font, layer, comp.baseGlyph, TransformPen(pen, comp.transformation))


def collect(font, name, which, transform=Transform()):
    pen = TransformPen(Collect(), transform)
    if which == "outline":
        draw_outline(font, name, pen)
    else:
        draw_layer(font, which, name, pen)
    return pen._outPen.contours


def bounds(contour_sets):
    pts = [p for cs in contour_sets for _closed, segs in cs for _op, ps in segs for p in ps]
    if not pts:
        return 0, 0, 0, 0
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def n(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


# ------------------------------------------------------------------ SVG
def svg_path(contours):
    out = []
    for closed, segs in contours:
        for op, ps in segs:
            out.append(op + " ".join(f"{n(x)} {n(y)}" for x, y in ps))
        if closed:
            out.append("Z")
    return " ".join(out)


def svg_doc(view, layers, title):
    """view = (xmin, ymin, xmax, ymax) in font units (y up); layers = [(label, svg body)]."""
    x0, y0, x1, y1 = view
    w, h = x1 - x0, y1 - y0
    body = "\n".join(
        f'  <g id="{label}" inkscape:groupmode="layer" inkscape:label="{label}">\n{content}\n  </g>'
        for label, content in layers)
    # y-flip: font units are y-up, SVG is y-down; the group keeps coordinates in font units
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="{n(w)}" height="{n(h)}" viewBox="0 0 {n(w)} {n(h)}">
<title>{title}</title>
<g transform="matrix(1 0 0 -1 {n(-x0)} {n(y1)})">
{body}
</g>
</svg>
"""


def svg_guides(x0, x1, advances=()):
    lines = [f'    <line x1="{n(x0)}" y1="{y}" x2="{n(x1)}" y2="{y}" stroke="{GUIDE_STRONG if y == 0 else GUIDE}" '
             f'stroke-width="{4 if y == 0 else 2}"{" stroke-dasharray=\"20 20\"" if y == -682 else ""}/>'
             for y, _label in GUIDES]
    for x, (lo, hi) in advances:
        lines.append(f'    <line x1="{n(x)}" y1="{n(lo)}" x2="{n(x)}" y2="{n(hi)}" stroke="{GUIDE}" stroke-width="2" '
                     f'stroke-dasharray="8 12"/>')
    return "\n".join(lines)


def svg_layers(outline, skel, extra, guides):
    return [
        ("hulplijnen", guides),
        ("omtrek", f'    <path d="{svg_path(outline)}" fill="{INK}" fill-opacity="0.18" fill-rule="nonzero"/>'),
        ("middenlijn", f'    <path d="{svg_path(skel)}" fill="none" stroke="{CENTRE}" stroke-width="6" '
                       f'stroke-linecap="round" stroke-linejoin="round"/>' if skel else ""),
        ("vlakken", f'    <path d="{svg_path(extra)}" fill="{CENTRE}" fill-opacity="0.6"/>' if extra else ""),
    ]


# ------------------------------------------------------------------ EPS
def eps_path(contours):
    out = []
    for closed, segs in contours:
        for op, ps in segs:
            args = " ".join(f"{n(x)} {n(y)}" for x, y in ps)
            out.append(f"{args} {dict(M='moveto', L='lineto', C='curveto')[op]}")
        if closed:
            out.append("closepath")
    return "\n".join(out)


def eps_doc(bbox, parts, title):
    """parts: [(comment, ps code)] in font units (PostScript is y-up like fonts)."""
    x0, y0, x1, y1 = (math.floor(bbox[0]), math.floor(bbox[1]), math.ceil(bbox[2]), math.ceil(bbox[3]))
    body = "\n".join(f"% --- {c}\n{code}" for c, code in parts if code)
    return f"""%!PS-Adobe-3.0 EPSF-3.0
%%BoundingBox: {x0} {y0} {x1} {y1}
%%Title: {title}
%%Creator: cogncur scripts/designer_files.py
%%EndComments
{body}
showpage
%%EOF
"""


def rgb(hexcol):
    return " ".join(n(int(hexcol[i:i + 2], 16) / 255) for i in (1, 3, 5)) + " setrgbcolor"


# ------------------------------------------------------------- per glyph
def glyph_files(font, name, uni, dest):
    outline = collect(font, name, "outline", UNSLANT)
    skel = collect(font, name, "skeleton", UNSLANT)
    extra = collect(font, name, "extra", UNSLANT)
    if not skel and not extra:
        print(f"  warning: {name} has no centre line")
    adv = font[name].width
    bx0, by0, bx1, by1 = bounds([outline, skel, extra])
    pad = 120
    view = (min(0, bx0) - pad, min(-682, by0) - pad, max(adv, bx1) + pad, max(1364, by1) + pad)
    guides = svg_guides(view[0], view[2], [(0, (view[1], view[3])), (adv, (view[1], view[3]))])
    stem = f"{uni:04X}-{name}"
    (dest / f"{stem}.svg").write_text(svg_doc(view, svg_layers(outline, skel, extra, guides), f"{chr(uni)} {name}"))
    # EPS: only what goes onto her Skeleton/Extra layers. The centre line is painted
    # with 'fill', not 'stroke': FontForge expands stroked paths into outlines on
    # import (and has no flag to prevent it), but keeps filled open paths open, 1:1.
    parts = [("middenlijn (Skeleton) - open paden; 'fill' zodat FontForge ze open laat",
              f"newpath\n{eps_path(skel)}\n0 0 0 setrgbcolor fill" if skel else ""),
             ("vlakken (Extra)", f"newpath\n{eps_path(extra)}\n0 0 0 setrgbcolor fill" if extra else "")]
    sb = bounds([skel, extra])
    (dest / f"{stem}.eps").write_text(eps_doc((sb[0] - PEN, sb[1] - PEN, sb[2] + PEN, sb[3] + PEN), parts,
                                              f"{chr(uni)} {name}"))
    return stem


# -------------------------------------------------------------- overview
def overview(font, shaper, lines, dest, title):
    row_h = 1364 + 682 + 900
    outline, skel, extra, x_max = [], [], [], 0
    for i, text in enumerate(lines):
        base = -i * row_h
        x = 0
        for name, _cl, xa, ya, xo, yo, _gid in shaper.shape(text, {}):
            t = Transform(1, 0, 0, 1, x + xo, base + yo)
            outline += collect(font, name, "outline", t)
            skel += collect(font, name, "skeleton", t)
            extra += collect(font, name, "extra", t)
            x += xa
        x_max = max(x_max, x)
    bx0, by0, bx1, by1 = bounds([outline, skel, extra])
    pad = 200
    view = (min(0, bx0) - pad, min(-(len(lines) - 1) * row_h - 682, by0) - pad, max(x_max, bx1) + pad,
            max(1364, by1) + pad)
    guide_lines = []
    for i in range(len(lines)):
        base = -i * row_h
        for y, _ in GUIDES:
            yy = base + y
            dash = ' stroke-dasharray="20 20"' if y == -682 else ""
            guide_lines.append(f'    <line x1="{n(view[0])}" y1="{yy}" x2="{n(view[2])}" y2="{yy}" '
                               f'stroke="{GUIDE_STRONG if y == 0 else GUIDE}" stroke-width="{4 if y == 0 else 2}"{dash}/>')
    layers = svg_layers(outline, skel, extra, "\n".join(guide_lines))
    layers[1] = ("omtrek", f'    <path d="{svg_path(outline)}" fill="{INK}" fill-rule="nonzero"/>')
    (dest / "overzicht.svg").write_text(svg_doc(view, layers, title))

    ps_guides = []
    for i in range(len(lines)):
        for y, _ in GUIDES:
            yy = -i * row_h + y
            ps_guides.append(f"newpath {n(view[0])} {yy} moveto {n(view[2])} {yy} lineto stroke")
    parts = [("hulplijnen", f"{rgb(GUIDE)} 3 setlinewidth\n" + "\n".join(ps_guides)),
             ("omtrek", f"newpath\n{eps_path(outline)}\n{rgb(INK)} fill"),
             ("middenlijn", f"newpath\n{eps_path(skel)}\n{rgb(CENTRE)} 6 setlinewidth 1 setlinecap 1 setlinejoin "
                            f"stroke" if skel else ""),
             ("vlakken", f"newpath\n{eps_path(extra)}\n{rgb(CENTRE)} fill" if extra else "")]
    (dest / "overzicht.eps").write_text(eps_doc(view, parts, title))


README = """# Bestanden voor de ontwerper

Per vraag (GitHub-issue met label `ontwerper`) staat hier een map met de nieuwe tekens als
bewerkbare vectorbestanden. Ze worden gemaakt door `scripts/designer_files.py` uit het huidige
lettertype; pas ze dus niet hier aan, maar stuur je aanpassing terug (in het issue of als bestand).

## Wat zit er in een map?

| Bestand | Inhoud | Om te gebruiken in |
|---|---|---|
| `<code>-<naam>.svg` | Eén teken, **rechtop** (zonder de helling van 7,5°), in de eenheden van het lettertype (2048 per em, oorsprong = oorsprong van het teken). Lagen: `hulplijnen` (onderlijn −682, basislijn 0, x-hoogte 682, bovenlijn 1364, breedte), `omtrek` (grijs, ter referentie), `middenlijn` (rood, jouw *Skeleton*-laag) en `vlakken` (punten, komma's: jouw *Extra*-laag). | Illustrator, Inkscape, browser |
| `<code>-<naam>.eps` | Alleen de middenlijn en de vlakken, rechtop, 1:1 in eenheden van het lettertype. | FontForge: *File → Import* op de laag **Skeleton** |
| `overzicht.svg` / `.eps` | De voorbeeldregels uit het issue zoals het lettertype ze zet (hellend, met verbindingen), op schrijflijnen, met omtrek en middenlijn. | Om in te schetsen of te annoteren |

`<code>` is de Unicode-code van het teken (bv. `00F0` = ð).

## Goed om te weten

- **FontForge en de EPS**: de middenlijnen zijn *open* paden. Ze staan in de EPS als `fill` in plaats
  van `stroke`, want FontForge zet een `stroke` bij het importeren om in een omtrek. Zo blijven ze
  open, net zoals je ze tekent. In Illustrator zien ze er daardoor uit als gevulde vlakken; gebruik
  daar de SVG.
- De **omtrek** in de SVG per teken is rechtgezet (de helling eruit gehaald), zodat hij over de
  middenlijn valt. In het lettertype helt hij 7,5°.
- Accenttekens (zoals ą) zijn in het lettertype samengesteld uit letter + accent. In de bestanden
  staan ze samengevoegd.
"""


# ------------------------------------------------------------------ main
def main(only=()):
    import issues
    font = ufoLib2.Font.open(UFO)
    shaper = Font(TTF)
    cmap = {u: g.name for g in font for u in g.unicodes}
    done = []
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "README.md").write_text(README)
    for d in issues.DECISIONS:
        if "ontwerper" not in d["labels"] or (only and d["id"] not in only):
            continue
        dest = OUT / issues.slug(d)
        dest.mkdir(parents=True, exist_ok=True)
        for old in list(dest.glob("*.svg")) + list(dest.glob("*.eps")):
            old.unlink()
        stems = [glyph_files(font, cmap[ord(ch)], ord(ch), dest) for ch in d["bestanden"]]
        overview(font, shaper, d["glyphs"] + d["words"], dest, d["titel"])
        done.append((d["id"], stems))
        print(f"{dest.relative_to(ROOT)}: {len(stems)} glyphs + overzicht")
    return done


if __name__ == "__main__":
    main(tuple(sys.argv[1:]))
