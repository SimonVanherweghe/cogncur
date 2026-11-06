"""New glyphs drawn the way the designer draws: centre lines on the 'Skeleton'
layer (stroked with a round 68-unit pen) and filled shapes on the 'Extra'
layer (dots, commas), in unslanted coordinates. The style layer is derived
with the exact recipe of upstream/sources/derive-layers.py.

Runs inside FontForge (imported by export_ufo.py). Everything here is a
DRAFT for review; see docs/new-glyphs.md for what is derived from what.
"""
import math

import fontforge
import psMat

SKEW = {"GRegOutl": 7.5, "GOutline": 0.0, "GSlOutl": 15.0}
PEN = 68


# ------------------------------------------------------------------ helpers
def _contour(cmds):
    """cmds: ('M', x, y) | ('L', x, y) | ('C', x1, y1, x2, y2, x, y)"""
    c = fontforge.contour()
    for cmd in cmds:
        if cmd[0] == "M":
            c.moveTo(cmd[1], cmd[2])
        elif cmd[0] == "L":
            c.lineTo(cmd[1], cmd[2])
        elif cmd[0] == "C":
            c.cubicTo((cmd[1], cmd[2]), (cmd[3], cmd[4]), (cmd[5], cmd[6]))
    c.closed = False
    return c


def _layer(*contours, quadratic=False):
    l = fontforge.layer()
    l.is_quadratic = quadratic
    for c in contours:
        l += c
    return l


def _copy(font, glyph, layer, index=None, matrix=None):
    """Copy contours of an existing glyph layer (optionally one contour)."""
    src = font[glyph].layers[layer]
    out = fontforge.layer()
    out.is_quadratic = src.is_quadratic
    for i, c in enumerate(src):
        if index is None or i == index:
            out += c.dup()
    if matrix:
        out.transform(matrix)
    return out


def _bbox(layer):
    return layer.boundingBox()  # (xmin, ymin, xmax, ymax)


def _centre(layer):
    x0, y0, x1, y1 = _bbox(layer)
    return (x0 + x1) / 2, (y0 + y1) / 2


def _derive(glyph, style_layer):
    """derive-layers.py: skew Skeleton + Extra, stroke Skeleton with a round pen."""
    angle = SKEW[style_layer]
    m = psMat.skew(angle * math.pi / 180.0)
    sk = glyph.layers["Skeleton"]
    ex = glyph.layers["Extra"]
    sk.transform(m)
    ex.transform(m)
    if len(sk):
        sk.stroke("circular", PEN)
    glyph.layers[style_layer] = sk + ex


def _new(font, name, width, skeleton=None, extra=None):
    if name in font:
        font.removeGlyph(name)
    g = font.createChar(-1, name)
    g.width = width
    g.layers["Skeleton"] = skeleton if skeleton is not None else fontforge.layer()
    g.layers["Extra"] = extra if extra is not None else fontforge.layer()
    return g


# --------------------------------------------------------------- the glyphs
def build(font, style_layer="GRegOutl"):
    made = []
    T = psMat.translate
    S = psMat.scale
    R = psMat.rotate

    # ---- marks (zero width, unslanted, positioned like her marks for 'o':
    #      topmid anchor (487, 648), bottom anchor (487, 34))
    # dot above: the exact dot of her i, centred on x = 487
    dot = _copy(font, "i", "Extra")
    cx, cy = _centre(dot)
    dot.transform(T(487 - cx, 0))
    made.append(_new(font, "uni0307", 0, extra=dot))

    # double acute: two of her acutes, narrowed to 80 %, side by side
    acute = _copy(font, "acutecomb", "Skeleton")
    if not len(acute):
        acute = _copy(font, "acutecomb", "Extra")
    ax, ay = _centre(acute)
    w = _bbox(acute)[2] - _bbox(acute)[0]
    left = acute.dup()
    left.transform(psMat.compose(T(-ax, -ay), psMat.compose(S(0.8, 1), T(ax - 0.55 * w, ay))))
    right = acute.dup()
    right.transform(psMat.compose(T(-ax, -ay), psMat.compose(S(0.8, 1), T(ax + 0.55 * w, ay))))
    hung_sk = left + right
    made.append(_new(font, "uni030B", 0, skeleton=hung_sk if len(_copy(font, "acutecomb", "Skeleton")) else None,
                     extra=None if len(_copy(font, "acutecomb", "Skeleton")) else hung_sk))

    # comma below: her comma, 80 %, top at y = -40, centred on x = 487
    comma = _copy(font, "comma", "Extra")
    ccx, ccy = _centre(comma)
    comma.transform(psMat.compose(T(-ccx, -ccy), S(0.8)))
    top = _bbox(comma)[3]
    comma.transform(T(487, -40 - top))
    made.append(_new(font, "uni0326", 0, extra=comma))

    # turned comma above (for g-cedilla, Latvian): her comma rotated 180 deg, above x-height
    tc = _copy(font, "comma", "Extra")
    tc.transform(psMat.compose(T(-ccx, -ccy), psMat.compose(S(0.8), R(math.pi))))
    tcx, tcy = _centre(tc)
    tc.transform(T(487 - tcx, 893 - tcy))
    made.append(_new(font, "uni0312", 0, extra=tc))

    # ogonek: new centre line, hanging from the anchor (487, 34) down-left, flicking right
    og = _layer(_contour([("M", 487, 34), ("C", 452, 4, 412, -60, 412, -120),
                          ("C", 412, -185, 462, -222, 540, -212)]))
    made.append(_new(font, "uni0328", 0, skeleton=og))

    # apostrophe-style caron (d l t L): her right single quote, left edge 94 units right
    # of the anchor (0, 1330) = half a pen (34) + 60 gap; top at 1364 like the original
    ap = _copy(font, "quoteright", "Extra")
    ap.transform(T(94 - _bbox(ap)[0], 0))
    made.append(_new(font, "caronvert", 0, extra=ap))

    # bar (D-croat, d-croat, H-bar, h-bar) and slash (L-slash, l-slash): plain pen strokes
    made.append(_new(font, "barcomb", 0, skeleton=_layer(_contour([("M", -115, 0), ("L", 115, 0)]))))
    made.append(_new(font, "slashcomb", 0, skeleton=_layer(_contour([("M", -110, -75), ("L", 110, 75)]))))

    # ---- minus: the horizontal stroke of her plus
    made.append(_new(font, "minus", font["plus"].width, skeleton=_copy(font, "plus", "Skeleton", index=1)))

    # ---- new letterforms (drafts)
    # eth: bowl of her d; the stem curves to the left at the top; a slash crosses it
    eth_sk = _copy(font, "d", "Skeleton", index=1)
    eth_sk += _contour([("M", 760, 34), ("C", 702, 34, 685, 83, 685, 137), ("L", 685, 700),
                        ("C", 685, 1000, 640, 1180, 520, 1290)])
    eth_sk += _contour([("M", 560, 985), ("L", 800, 1115)])
    made.append(_new(font, "eth", font["d"].width, skeleton=eth_sk))

    # thorn: her b's looped ascender continued down as p's descender, plus p's bowl
    th_sk = _copy(font, "p", "Skeleton", index=1)
    th_sk += _contour([("M", 461, 1330), ("C", 350, 1330, 320, 1228, 320, 1105), ("L", 320, -648)])
    made.append(_new(font, "thorn", font["p"].width, skeleton=th_sk))

    # Thorn: her P's stem, with the bowl moved down to the middle
    Th_sk = _copy(font, "P", "Skeleton", index=1)
    Th_sk += _copy(font, "P", "Skeleton", index=0, matrix=T(0, -300))
    made.append(_new(font, "Thorn", font["P"].width, skeleton=Th_sk))

    # capital sharp s: her B's stem and lower bowl, with a flat top and a diagonal
    B_sk = _copy(font, "B", "Skeleton")
    bowl = None
    for c in B_sk:
        pts = [(p.x, p.y) for p in c]
        if any(abs(x - 725) < 2 and abs(y - 423) < 2 for x, y in pts):
            i = next(k for k, (x, y) in enumerate(pts) if abs(x - 725) < 2 and abs(y - 423) < 2)
            bowl = c
            start = i
    ss = _copy(font, "B", "Skeleton", index=1)  # stem
    top = fontforge.contour()
    top.moveTo(222, 1180)
    top.cubicTo((240, 1290), (330, 1330), (440, 1330))
    top.cubicTo((570, 1330), (660, 1290), (695, 1235))
    top.lineTo(450, 800)
    top.cubicTo((610, 790), (725, 640), (725, 423))
    if bowl is not None:
        pts = list(bowl)
        k = start + 1
        while k + 2 < len(pts):
            a, b, c = pts[k], pts[k + 1], pts[k + 2]
            if not a.on_curve and not b.on_curve and c.on_curve:
                top.cubicTo((a.x, a.y), (b.x, b.y), (c.x, c.y))
                k += 3
            elif a.on_curve:
                top.lineTo(a.x, a.y)
                k += 1
            else:
                k += 1
    top.closed = False
    ss += top
    made.append(_new(font, "uni1E9E", font["B"].width, skeleton=ss))

    for g in made:
        _derive(g, style_layer)
    return [g.glyphname for g in made]
