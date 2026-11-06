"""Turn FontForge's raw UFO export into a Google-Fonts-ready source UFO.

    python scripts/postprocess_ufo.py <raw.ufo> <out.ufo> [--skeleton <skeleton.ufo>]

1. Feature fix (howto.txt, step 9): the 4 'start' rules in the calt lookup use a
   backtrack class that contains only 'space' as a development placeholder. In
   the shipped font that backtrack is removed so the rules also fire at line
   start / after punctuation. We remove it here.
2. Metadata: family name, GF copyright/license strings, version, fsType,
   vertical metrics.
3. Optionally store the single-stroke skeleton as an extra UFO layer
   ('skeleton') for a later pen-plotter export. Not built into the font.
"""
import argparse
import re
import shutil

import ufoLib2

import config

PLACEHOLDER_CLASS = re.compile(r"^\s*@(\w+)\s*=\s*\[\\space\s*\];\s*$", re.M)


def fix_space_placeholder(fea: str) -> str:
    classes = PLACEHOLDER_CLASS.findall(fea)
    assert len(classes) == 1, f"expected one [space] placeholder class, found {classes}"
    cls = classes[0]
    rule = re.compile(rf"(\bsub\s+)@{cls}\s+(@\w+'lookup\s+msstart)")
    fea, n = rule.subn(r"\1\2", fea)
    assert n == 4, f"expected 4 start rules with placeholder backtrack, fixed {n}"
    assert f"@{cls} " not in fea.split(f"@{cls} =", 1)[1], "placeholder class still in use"
    fea = PLACEHOLDER_CLASS.sub("", fea)
    return fea


GLYPH = re.compile(r"\\([A-Za-z0-9_.]+)")
SINGLE_SUB = re.compile(r"^\s*sub\s+\\([A-Za-z0-9_.]+)\s+by\s+\\([A-Za-z0-9_.]+)\s*;\s*$")
CLASS_DEF = re.compile(r"^(\s*@\w+\s*=\s*\[)(.*?)(\];)", re.S)


def prune_missing_glyphs(fea: str, glyphs: set) -> tuple[str, dict]:
    """Remove references to glyphs that no longer exist in the .sfd.

    The .sfd's ss01/ss02/ss09/ss12 and kern lookups still mention ~6000
    precomposed glyphs from the old single-substitution build, which were
    deleted from the source. FontForge's own TTF output silently skips them;
    feaLib (correctly) refuses them. Only two statement shapes contain such
    references: single substitutions and class definitions.
    """
    stats = {"single_sub_dropped": 0, "class_members_dropped": 0, "empty_classes": []}
    out_lines = []
    lines = fea.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = SINGLE_SUB.match(line)
        if m:
            if m.group(1) not in glyphs or m.group(2) not in glyphs:
                stats["single_sub_dropped"] += 1
                i += 1
                continue
            out_lines.append(line)
            i += 1
            continue
        if re.match(r"^\s*@\w+\s*=\s*\[", line):
            # gather the (possibly multi-line) class definition
            block = line
            while "];" not in block:
                i += 1
                block += "\n" + lines[i]
            cm = CLASS_DEF.match(block)
            members = GLYPH.findall(cm.group(2))
            if members and not re.search(r"@\w+", cm.group(2)):
                kept = [g for g in members if g in glyphs]
                stats["class_members_dropped"] += len(members) - len(kept)
                if not kept:
                    stats["empty_classes"].append(cm.group(1).strip())
                block = cm.group(1) + " ".join("\\" + g for g in kept) + " " + cm.group(3) + block[cm.end():]
            out_lines.append(block)
            i += 1
            continue
        out_lines.append(line)
        i += 1
    fea = "\n".join(out_lines)
    leftover = {g for g in GLYPH.findall(fea) if g not in glyphs}
    assert not leftover, f"unhandled missing glyph references: {sorted(leftover)[:10]}"
    assert not stats["empty_classes"], f"classes became empty: {stats['empty_classes']}"
    return fea, stats


def set_metadata(font: ufoLib2.Font, style: str) -> None:
    info = font.info
    info.familyName = config.FAMILY
    info.styleName = style
    info.styleMapFamilyName = config.FAMILY
    info.styleMapStyleName = style.lower()
    info.openTypeNamePreferredFamilyName = None
    info.openTypeNamePreferredSubfamilyName = None
    info.postscriptFontName = f"{config.FAMILY.replace(' ', '')}-{style}"
    info.postscriptFullName = f"{config.FAMILY} {style}"
    info.openTypeNameUniqueID = None
    info.openTypeNameCompatibleFullName = None
    info.versionMajor, info.versionMinor = config.VERSION
    info.openTypeNameVersion = None
    info.copyright = config.COPYRIGHT
    info.trademark = None
    info.openTypeNameLicense = config.LICENSE
    info.openTypeNameLicenseURL = config.LICENSE_URL
    info.openTypeNameDesigner = config.DESIGNER
    info.openTypeNameDesignerURL = config.DESIGNER_URL
    info.openTypeNameManufacturer = None
    info.openTypeNameManufacturerURL = config.REPO_URL
    info.openTypeOS2VendorID = config.VENDOR_ID
    info.openTypeOS2Type = []  # fsType 0 = installable embedding
    info.note = None
    # Vertical metrics: GF wants typo == hhea and USE_TYPO_METRICS on.
    # We keep the reference font's hhea values (what macOS/browsers used), so
    # line spacing there does not change.
    # FontForge's UFO export leaves these unset (ufo2ft then guesses 1024/1434);
    # restore the reference font's OS/2 values.
    info.xHeight = config.X_HEIGHT
    info.capHeight = config.CAP_HEIGHT
    asc, desc = config.LINE_ASCENT, config.LINE_DESCENT
    info.openTypeOS2TypoAscender, info.openTypeOS2TypoDescender, info.openTypeOS2TypoLineGap = asc, desc, 0
    info.openTypeHheaAscender, info.openTypeHheaDescender, info.openTypeHheaLineGap = asc, desc, 0
    sel = set(info.openTypeOS2Selection or [])
    sel.add(7)  # USE_TYPO_METRICS
    info.openTypeOS2Selection = sorted(sel)
    # win metrics must cover the bbox (fontbakery); keep the reference values.
    info.openTypeOS2WinAscent = config.WIN_ASCENT
    info.openTypeOS2WinDescent = config.WIN_DESCENT


def fix_glyphs(font: ufoLib2.Font) -> list:
    """Small technical glyph fixes required by Google Fonts. Every change here
    must also be listed under intentional_changes in tests/thresholds.yaml."""
    changes = []
    # U+00A0 NO-BREAK SPACE is required whitespace (fontbakery whitespace_glyphs)
    if "uni00A0" not in font and "nbspace" not in font:
        g = font.newGlyph("uni00A0")
        g.width = font["space"].width
        g.unicodes = [0x00A0]
        changes.append("added uni00A0 (no-break space, width of space)")
    # U+2010 HYPHEN is empty upstream; make it a copy of the hyphen-minus
    g = font["uni2010"]
    if not g.contours and not g.components:
        g.components = []
        g.width = font["hyphen"].width
        from ufoLib2.objects import Component
        g.components.append(Component(baseGlyph="hyphen"))
        changes.append("uni2010 (hyphen) was empty: now a component of 'hyphen'")
    return changes


def _rdp(points, tol):
    """Ramer-Douglas-Peucker on a list of (x, y); returns indices to keep."""
    import math
    if len(points) < 3:
        return list(range(len(points)))
    (x0, y0), (x1, y1) = points[0], points[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy)
    best, idx = -1.0, 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        d = (abs(dy * px - dx * py + x1 * y0 - y1 * x0) / norm) if norm else math.hypot(px - x0, py - y0)
        if d > best:
            best, idx = d, i
    if best <= tol:
        return [0, len(points) - 1]
    left = _rdp(points[: idx + 1], tol)
    right = _rdp(points[idx:], tol)
    return left[:-1] + [i + idx for i in right]


def _rotate_to_curve(pts):
    """Start the contour at the end point of a curve segment, so runs of
    'line' points never wrap around index 0."""
    for i, p in enumerate(pts):
        if p.type in ("qcurve", "curve"):
            return pts[i:] + pts[:i]
    return pts


def _segments(pts):
    """Split a closed contour (starting on an on-curve point) into segments:
    lists [start_oncurve, offcurves..., end_oncurve]."""
    segs, cur = [], [pts[0]]
    for p in pts[1:] + pts[:1]:
        cur.append(p)
        if p.type is not None:
            segs.append(cur)
            cur = [p]
    return segs


def _dist(a, b):
    import math
    return math.hypot(a.x - b.x, a.y - b.y)


def _line_dev(p, a, b):
    """Distance of p from the line through a and b, and whether p lies between them."""
    import math
    dx, dy = b.x - a.x, b.y - a.y
    n = math.hypot(dx, dy)
    if not n:
        return _dist(p, a), False
    t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / (n * n)
    return abs(dy * p.x - dx * p.y + b.x * a.y - b.y * a.x) / n, 0 < t < 1


def add_gf_extras(font: ufoLib2.Font) -> list:
    """Metadata-only additions requested by fontbakery; existing glyphs are untouched.
    - 'meta' table declaring Latin (googlefonts/meta/script_lang_tags)
    - caret positions for the double-vowel ligatures (ligature_carets)
    - U+25CC DOTTED CIRCLE that accepts the combining accents (dotted_circle)"""
    import math
    from fontTools.pens.pointPen import SegmentToPointPen
    from fontTools.pens.qu2cuPen import Qu2CuPen  # noqa: F401  (ensures fontTools pens available)
    done = []
    font.lib["public.openTypeMeta"] = {"dlng": ["Latn"], "slng": ["Latn"]}
    done.append("meta table: dlng/slng = Latn")

    # ligature carets: these ligatures are exactly two letters wide
    fea = font.features.text
    carets = []
    for lig, base in [("aabreve", "a"), ("aamacron", "a"), ("eebreve", "e"), ("eemacron", "e"),
                      ("oobreve", "o"), ("oomacron", "o"), ("uubreve", "u"), ("uumacron", "u")]:
        if lig in font and f"LigatureCaretByPos \\{lig} " not in fea:
            assert font[lig].width == 2 * font[base].width, f"{lig} is not 2x {base}"
            carets.append(f"  LigatureCaretByPos \\{lig} {font[base].width};")
    if carets:
        assert fea.count("} GDEF;") == 1
        fea = fea.replace("} GDEF;", "\n".join(carets) + "\n} GDEF;")
        done.append(f"ligature carets for {len(carets)} double-vowel ligatures")

    # dotted circle: 12 dots (stroke-width diameter) on a ring the size of 'o',
    # skewed like the Regular style (7.5 deg), with the same accent anchors as 'o'
    if "uni25CC" not in font:
        t = math.tan(math.radians(7.5))
        o = font["o"]
        anchors = {a.name: (a.x, a.y) for a in o.anchors}
        cy, r, dot = 341, 300, 34          # centre at half x-height; dot radius = half stroke width (68)
        cx = anchors["topmid"][0] - (cy + r) * t
        g = font.newGlyph("uni25CC")
        g.unicodes = [0x25CC]
        g.width = o.width
        pen = SegmentToPointPen(g.getPointPen())
        k = 0.5523  # unused for quadratics; circle drawn with 8 quadratic segments
        for i in range(12):
            a = 2 * math.pi * i / 12
            px, py = cx + r * math.cos(a), cy + r * math.sin(a)
            pts = []
            for j in range(8):
                b = 2 * math.pi * j / 8
                on = (px + dot * math.cos(b), py + dot * math.sin(b))
                off = (px + dot / math.cos(math.pi / 8) * math.cos(b + math.pi / 8),
                       py + dot / math.cos(math.pi / 8) * math.sin(b + math.pi / 8))
                pts.append((on, off))
            sk = lambda p: (round(p[0] + p[1] * t), round(p[1]))
            pen.moveTo(sk(pts[0][0]))
            for j in range(8):
                pen.qCurveTo(sk(pts[j][1]), sk(pts[(j + 1) % 8][0]))
            pen.closePath()
        bottom = (round(cx + 34 * t), 34)
        for name, (x, y) in list(anchors.items()) + [("bottom", bottom)]:
            g.appendAnchor({"name": name, "x": x, "y": y})
        stmt = ("  pos base [\\uni25CC ] " + " ".join(
            f"<anchor {x} {y}> mark @{name}" for name, (x, y) in list(anchors.items()) + [("bottom", bottom)]) + ";")
        end = "} markMarktobaseattachmentinLatinlookup;"
        assert fea.count(end) == 1, "mark lookup not found"
        fea = fea.replace(end, stmt + "\n" + end)
        done.append("added uni25CC (dotted circle) with topleft/topmid/topright/bottom accent anchors")
    font.features.text = fea
    return done


def _remove(pts, point):
    """Remove by identity: ufoLib2 points compare by value, so list.remove()
    could delete a different point that happens to have the same coordinates."""
    del pts[next(i for i, q in enumerate(pts) if q is point)]


def clean_outlines(font: ufoLib2.Font, tol: float = 1.0) -> dict:
    """FontForge's stroker leaves glitches in some glyphs: long runs of tiny
    straight segments, near-colinear lines, 1-unit curves and 1-unit kinks.
    After rounding to integers fontbakery reports them as overlapping, jaggy
    or colinear segments. All fixes move outlines by at most ~2 font units
    (0.1% of the em); tests/compare.py guards the result."""
    stats = {"glyphs": 0, "points_removed": 0}
    for g in font:
        before = sum(len(c.points) for c in g.contours)
        for c in g.contours:
            if not any(p.type is not None for p in c.points) or c.points[0].type == "move":
                continue  # open paths (rare in this layer) are left untouched
            pts = _rotate_to_curve(list(c.points))
            # 1. RDP on runs of 'line' points (anchored on the previous on-curve point)
            keep = [True] * len(pts)
            i = 1
            while i < len(pts):
                if pts[i].type == "line" and pts[i - 1].type is not None:
                    j = i
                    while j + 1 < len(pts) and pts[j + 1].type == "line":
                        j += 1
                    chain = [(pts[k].x, pts[k].y) for k in range(i - 1, j + 1)]
                    kept = set(_rdp(chain, tol))
                    for n, k in enumerate(range(i - 1, j + 1)):
                        if n not in kept and k not in (i - 1, j):
                            keep[k] = False
                    i = j + 1
                else:
                    i += 1
            pts = [p for p, k in zip(pts, keep) if k]
            for p in pts:
                p.x, p.y = round(p.x), round(p.y)
            # 2. iterate small local fixes until nothing changes
            changed = True
            while changed and len(pts) > 3:
                changed = False
                segs = _segments(pts)
                for si, seg in enumerate(segs):
                    start, end, offs = seg[0], seg[-1], seg[1:-1]
                    # degenerate curve (all points within 1 unit of an endpoint) -> line
                    if offs and _dist(start, end) <= 2 and all(min(_dist(o, start), _dist(o, end)) <= 1 for o in offs):
                        for o in offs:
                            _remove(pts, o)
                        end.type = "line"
                        changed = True
                        break
                    # straight quadratic: one control point on (or within 0.5 of) the chord -> line
                    if len(offs) == 1 and end.type == "qcurve":
                        dev, _ = _line_dev(offs[0], start, end)
                        on_end = min(_dist(offs[0], start), _dist(offs[0], end)) <= 1
                        if on_end or (dev <= 0.5 and _line_dev(offs[0], start, end)[1]):
                            _remove(pts, offs[0])
                            end.type = "line"
                            changed = True
                            break
                    if end.type != "line":
                        continue
                    nxt = segs[(si + 1) % len(segs)]
                    # zero/short line (<= 2 units) -> drop its end point
                    # (the following segment then starts at 'start' instead)
                    if _dist(start, end) <= 2 and len(segs) > 2:
                        _remove(pts, end)
                        changed = True
                        break
                    # colinear line-line: drop the shared point
                    if not nxt[1:-1] and nxt[-1].type == "line" and len(segs) > 3:
                        dev, between = _line_dev(end, start, nxt[-1])
                        if dev <= 0.5 and between:
                            _remove(pts, end)
                            changed = True
                            break
            c.points[:] = pts
        after = sum(len(c.points) for c in g.contours)
        if after != before:
            stats["glyphs"] += 1
            stats["points_removed"] += before - after
    return stats


def add_skeleton_layer(font: ufoLib2.Font, skeleton_path: str) -> None:
    skel = ufoLib2.Font.open(skeleton_path)
    layer = font.newLayer("skeleton") if "skeleton" not in font.layers else font.layers["skeleton"]
    for g in skel:
        if g.name in font:
            ng = layer.newGlyph(g.name)
            ng.width = g.width
            ng.contours = [c for c in g.contours]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("out")
    ap.add_argument("--style", default="Regular")
    ap.add_argument("--skeleton")
    a = ap.parse_args()

    font = ufoLib2.Font.open(a.raw)
    fea = fix_space_placeholder(font.features.text)
    fea, stats = prune_missing_glyphs(fea, set(font.keys()))
    print("pruned:", stats)
    font.features.text = fea
    set_metadata(font, a.style)
    for c in fix_glyphs(font):
        print("glyph fix:", c)
    print("outline cleanup:", clean_outlines(font))
    from composites import add_composites, write_manifest
    manifest = add_composites(font)
    write_manifest(manifest, "build/composites.json")
    n_inf = sum(len(m["inferred"]) for m in manifest)
    print(f"composites: {len(manifest)} new letters, "
          f"{sum(len(m['mapping']) for m in manifest)} glyphs, {n_inf} inferred anchors (see build/composites.json)")
    for c in add_gf_extras(font):
        print("gf extra:", c)
    if a.skeleton:
        add_skeleton_layer(font, a.skeleton)
    shutil.rmtree(a.out, ignore_errors=True)
    font.save(a.out)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
