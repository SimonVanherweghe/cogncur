"""Add new letters with the same join behaviour as an existing base letter.

Upstream builds accented letters as base + combining mark, placed on anchors
(verified: oacute, ecaron, s1caron, ntilde, ... match to the unit). Anchors
are stored unslanted, so a mark lifted by dy is also shifted by dy*tan(7.5).

For each new letter X with base B we:
  1. collect every glyph that "carries" B: B itself, its single-substitution
     variants (s -> s1) and the entry-stroke ligatures that contain it
     (csn n -> csn_n), recursively;
  2. create a copy of each carrier: carrier + mark as components (accented
     letters), or entry stroke + a newly drawn letter (ð þ Þ ẞ);
  3. duplicate every feature statement that mentions a carrier with the
     names replaced (join rules, variants, ligatures, kerning, GDEF classes);
  4. write a manifest used by tests/check_composites.py.

Positions on letters the designer never accented are inferred or proposed;
they are listed as 'inferred' for review and sources/anchors.yaml overrides them.
"""
import json
import math
import re
from pathlib import Path

import yaml
from fontTools.pens.boundsPen import BoundsPen
from ufoLib2.objects import Anchor, Component

from anchor_rule import XH, CAP, infer_topmid

TAN = math.tan(math.radians(7.5))
ROOT = Path(__file__).resolve().parent.parent
OVERRIDES = ROOT / "sources" / "anchors.yaml"

MARKS = {  # accent key -> (mark glyph, anchor name, glyph-name suffix)
    "acute": ("acutecomb", "topleft", "acute"),
    "grave": ("gravecomb", "topright", "grave"),
    "circumflex": ("uni0302", "topmid", "circumflex"),
    "tilde": ("tildecomb", "topmid", "tilde"),
    "macron": ("uni0304", "topmid", "macron"),
    "breve": ("uni0306", "topmid", "breve"),
    "dieresis": ("uni0308", "topmid", "dieresis"),
    "caron": ("uni030C", "topmid", "caron"),
    "cedilla": ("uni0327", "bottom", "cedilla"),
    # new marks, drawn in scripts/new_glyphs_ff.py (drafts)
    "dotaccent": ("uni0307", "topmid", "dotaccent"),
    "hungarumlaut": ("uni030B", "topmid", "hungarumlaut"),
    "commaaccent": ("uni0326", "bottom", "commaaccent"),
    "commaabove": ("uni0312", "topmid", "commaaccent"),
    "ogonek": ("uni0328", "ogonek", "ogonek"),
    "caronvert": ("caronvert", "caronvert", "caron"),
    "bar": ("barcomb", "bar", "bar"),
    "slash": ("slashcomb", "slash", "slash"),
}

# anchors of the new mark glyphs (unslanted, like the designer's marks for 'o')
NEW_MARKS = {
    "uni0307": ("_topmid", 487, 648, 0x0307),
    "uni030B": ("_topmid", 487, 648, 0x030B),
    "uni0312": ("_topmid", 487, 648, 0x0312),
    "uni0326": ("_bottom", 487, 34, 0x0326),
    "uni0328": ("_ogonek", 487, 34, 0x0328),
    "caronvert": ("_caronvert", 0, 1330, None),
    "barcomb": ("_bar", 0, 0, None),
    "slashcomb": ("_slash", 0, 0, None),
}

# Proposed attachment points where the designer has no anchor (unslanted,
# read from her skeletons; see docs/new-glyphs.md). All are flagged for review.
PROPOSED = {
    "a.ogonek": (685, 34), "e.ogonek": (470, 34), "i.ogonek": (320, 34), "u.ogonek": (741, 34),
    "A.ogonek": (1073, 34), "A2.ogonek": (922, 34), "E.ogonek": (400, 34), "I.ogonek": (330, 34),
    "U.ogonek": (728, 34),
    "d.caronvert": (685, 1330), "l.caronvert": (521, 1330), "t.caronvert": (560, 1137),
    "t1.caronvert": (321, 909), "L.caronvert": (994, 1330), "L1.caronvert": (1079, 1330),
    "d1.caronvert": (685, 1137),
    "D.bar": (432, 682), "d.bar": (685, 1050), "d1.bar": (685, 940), "H.bar": (372, 1050), "h.bar": (320, 960),
    "L.slash": (422, 640), "L1.slash": (424, 640), "l.slash": (320, 820),
    "l.topleft": (262, 1330),  # l-acute: acute centred over the loop, like on capitals
}

# (char, base, accent key, glyph name or None = base + suffix)
NEW_LETTERS = [
    # accent already in the font (round 1)
    ("ć", "c", "acute", None), ("č", "c", "caron", None), ("ě", "e", "caron", None),
    ("ğ", "g", "breve", None), ("ń", "n", "acute", None), ("ň", "n", "caron", None),
    ("ŕ", "r", "acute", None), ("ř", "r", "caron", None), ("ś", "s", "acute", None),
    ("ş", "s", "cedilla", None), ("ź", "z", "acute", None),
    ("ŵ", "w", "circumflex", None), ("ẁ", "w", "grave", None), ("ẃ", "w", "acute", None),
    ("ẅ", "w", "dieresis", None),
    ("Ć", "C", "acute", None), ("Č", "C", "caron", None), ("Ď", "D", "caron", None),
    ("Ě", "E", "caron", None), ("Ğ", "G", "breve", None), ("Ĺ", "L", "acute", None),
    ("Ń", "N", "acute", None), ("Ň", "N", "caron", None), ("Ŕ", "R", "acute", None),
    ("Ř", "R", "caron", None), ("Ś", "S", "acute", None), ("Ş", "S", "cedilla", None),
    ("Ť", "T", "caron", None), ("Ź", "Z", "acute", None), ("Ŵ", "W", "circumflex", None),
    ("Ẁ", "W", "grave", None), ("Ẃ", "W", "acute", None), ("Ẅ", "W", "dieresis", None),
    ("Ỳ", "Y", "grave", None),
    ("Ĩ", "I", "tilde", None), ("Ǎ", "A", "caron", None), ("Ǐ", "I", "caron", None),
    ("Ǒ", "O", "caron", None), ("Ǔ", "U", "caron", None), ("Ȳ", "Y", "macron", None),
    ("Ẽ", "E", "tilde", None), ("Ỹ", "Y", "tilde", None),
    # new accents (round 2, drafts)
    ("ą", "a", "ogonek", None), ("ę", "e", "ogonek", None), ("į", "i", "ogonek", None),
    ("ų", "u", "ogonek", None), ("Ą", "A", "ogonek", None), ("Ę", "E", "ogonek", None),
    ("Į", "I", "ogonek", None), ("Ų", "U", "ogonek", None),
    ("ċ", "c", "dotaccent", None), ("ė", "e", "dotaccent", None), ("ġ", "g", "dotaccent", None),
    ("ż", "z", "dotaccent", None), ("Ċ", "C", "dotaccent", None), ("Ė", "E", "dotaccent", None),
    ("Ġ", "G", "dotaccent", None), ("Ż", "Z", "dotaccent", None), ("İ", "I", "dotaccent", None),
    ("ő", "o", "hungarumlaut", None), ("ű", "u", "hungarumlaut", None),
    ("Ő", "O", "hungarumlaut", None), ("Ű", "U", "hungarumlaut", None),
    ("ș", "s", "commaaccent", "uni0219"), ("ț", "t", "commaaccent", "uni021B"),
    ("Ș", "S", "commaaccent", "uni0218"), ("Ț", "T", "commaaccent", "uni021A"),
    ("ķ", "k", "commaaccent", None), ("ļ", "l", "commaaccent", None), ("ņ", "n", "commaaccent", None),
    ("Ķ", "K", "commaaccent", None), ("Ļ", "L", "commaaccent", None), ("Ņ", "N", "commaaccent", None),
    ("Ģ", "G", "commaaccent", None), ("ģ", "g", "commaabove", "gcommaaccent"),
    ("ď", "d", "caronvert", None), ("ľ", "l", "caronvert", None), ("ť", "t", "caronvert", None),
    ("Ľ", "L", "caronvert", None), ("ĺ", "l", "acute", None),
    # letter + bar/slash (drafts)
    ("Đ", "D", "bar", "Dcroat"), ("Ð", "D", "bar", "Eth"), ("đ", "d", "bar", "dcroat"),
    ("Ħ", "H", "bar", "Hbar"), ("ħ", "h", "bar", "hbar"),
    ("Ł", "L", "slash", "Lslash"), ("ł", "l", "slash", "lslash"),
]

# newly drawn letters that join exactly like an existing letter (drafts)
REPLACEMENTS = [("ð", "eth", "d"), ("þ", "thorn", "p"), ("Þ", "Thorn", "P"), ("ẞ", "uni1E9E", "B")]

# spacing accents: (char, glyph name, mark) and other small additions (drafts for review)
SPACING = [("¯", "macron", "uni0304"), ("ˆ", "circumflex", "uni0302"), ("ˇ", "caron", "uni030C"),
           ("˘", "breve", "uni0306"), ("˙", "dotaccent", "uni0307"), ("˚", "ring", "uni030A"),
           ("˛", "ogonek", "uni0328"), ("˜", "tilde", "tildecomb"), ("˝", "hungarumlaut", "uni030B")]

TOKEN = r"\\{}(?=[\s\];,'])"
LIG_RE = re.compile(r"^\s*sub\s+((?:\\\S+\s+){2,})by\s+\\(\S+)\s*;", re.M)
SINGLE_RE = re.compile(r"^\s*sub\s+\\(\S+)\s+by\s+\\(\S+)\s*;\s*$", re.M)


def _tok(name):
    return re.compile(TOKEN.format(re.escape(name)))


def _statements(fea):
    start = 0
    for m in re.finditer(";", fea):
        yield start, m.end()
        start = m.end()


def carriers(fea, base, follow_single=True):
    """B and every glyph that carries B through single subs and entry-stroke ligatures."""
    found = {base}
    changed = True
    while changed:
        changed = False
        if follow_single:
            for m in SINGLE_RE.finditer(fea):
                if m.group(1) in found and m.group(2) not in found:
                    found.add(m.group(2)); changed = True
        for m in LIG_RE.finditer(fea):
            comps = [c.lstrip("\\") for c in m.group(1).split()]
            # only entry-stroke ligatures (cs*_*), not e.g. the Dutch IJ ligature
            if m.group(2).startswith("cs") and any(c in found for c in comps) and m.group(2) not in found:
                found.add(m.group(2)); changed = True
    return found


def ligature_parts(fea):
    out = {}
    for m in LIG_RE.finditer(fea):
        out[m.group(2)] = [c.lstrip("\\") for c in m.group(1).split()]
    return out


_SHIFT_CACHE = {}


def letter_shift(font, carrier, letter):
    """Where the letter body sits inside an entry-stroke ligature (n inside
    csn_n), found by matching ink (scripts/locate.py). Reproduces every
    upstream precedent exactly (csn_ntilde -103, cse_eacute -242, css_scaron
    -151, css1_s1caron -151, csz1_z1caron -195, cso_ccedilla -242)."""
    key = (carrier, letter)
    if key not in _SHIFT_CACHE:
        from locate import letter_offset
        dx, cov = letter_offset(font, carrier, letter, font[carrier].width - font[letter].width)
        assert cov > 0.95, f"{letter} not found inside {carrier} (coverage {cov:.2f})"
        _SHIFT_CACHE[key] = (dx, 0)
    return _SHIFT_CACHE[key]


def _ink_band(font, g, lo, hi):
    from anchor_rule import _Sampler
    s = _Sampler(font)
    g.draw(s)
    return [(x - y * TAN, y) for x, y in s.pts if lo <= y <= hi]


def resolve_anchor(font, glyph_name, anchor, capital, overrides, inferred):
    g = font[glyph_name]
    a = {x.name: (x.x, x.y) for x in g.anchors}
    key = f"{glyph_name}.{anchor}"
    if key in overrides:
        inferred.append({"glyph": glyph_name, "anchor": anchor, "pos": list(overrides[key]), "how": "override"})
        return tuple(overrides[key])
    if anchor in a:
        return a[anchor]
    if key in PROPOSED:
        inferred.append({"glyph": glyph_name, "anchor": anchor, "pos": list(PROPOSED[key]), "how": "proposed"})
        return PROPOSED[key]
    if anchor in ("topleft", "topright") and "topmid" in a:
        x, y = a["topmid"]
        return (x - 134 if anchor == "topleft" else x + 134, y)
    height = CAP if capital else XH
    if anchor == "bottom":
        band = _ink_band(font, g, 0, height * 0.25)
        x = round((min(p[0] for p in band) + max(p[0] for p in band)) / 2)
        inferred.append({"glyph": glyph_name, "anchor": anchor, "pos": [x, 34], "how": "inferred"})
        return (x, 34)
    if anchor == "ogonek":
        band = _ink_band(font, g, 0, 120)
        x = round(max(p[0] for p in band) - 34)
        inferred.append({"glyph": glyph_name, "anchor": anchor, "pos": [x, 34], "how": "inferred"})
        return (x, 34)
    if anchor in ("caronvert", "bar", "slash"):
        raise KeyError(f"no proposed '{anchor}' anchor for {glyph_name}: add it to PROPOSED or sources/anchors.yaml")
    tm = infer_topmid(g, font, capital)
    y = tm[1]
    x = round(tm[0] - y * TAN)  # anchors are stored unslanted
    if anchor == "topleft":
        x -= 134
    elif anchor == "topright":
        x += 134
    inferred.append({"glyph": glyph_name, "anchor": anchor, "pos": [x, y], "how": "inferred"})
    return (x, y)


def setup_new_marks(font):
    """Anchors, code points and GDEF/mark classes for the drawn marks."""
    fea = font.features.text
    for name, (anchor, x, y, cp) in NEW_MARKS.items():
        if name not in font:
            continue
        g = font[name]
        g.anchors = [Anchor(x=x, y=y, name=anchor)]
        if cp:
            g.unicodes = [cp]
    # combining use: top marks join @topmid, comma below joins @bottom
    top = [n for n in ("uni0307", "uni030B", "uni0312") if n in font]
    fea, n1 = re.subn(r"(markClass \[[^\]]*\\uni0302[^\]]*)\]", lambda m: m.group(1) + " ".join("\\" + t for t in top) + " ]", fea, count=1)
    fea, n2 = re.subn(r"(markClass \[[^\]]*\\uni0327[^\]]*)\]", lambda m: m.group(1) + "\\uni0326 ]", fea, count=1)
    marks = [n for n in NEW_MARKS if n in font]
    # FontForge exported them as simple glyphs; a glyph may be in one GDEF class only
    for cls in ("@GDEF_Simple", "@GDEF_Ligature", "@GDEF_Component"):
        m = re.search(re.escape(cls) + r"\s*=\s*\[([^\]]*)\]", fea)
        if m:
            inner = m.group(1)
            for t in marks:
                inner = _tok(t).sub("", inner)
            fea = fea[:m.start(1)] + inner + fea[m.end(1):]
    fea, n3 = re.subn(r"(@GDEF_Mark\s*=\s*\[[^\]]*)\]", lambda m: m.group(1) + " " + " ".join("\\" + t for t in marks) + " ]", fea, count=1)
    assert n1 == n2 == n3 == 1, (n1, n2, n3)
    font.features.text = fea


def _duplicate_statements(fea, mapping, skip_single_from=()):
    """Collect edits: class additions and duplicated sub/pos statements."""
    toks = {c: _tok(c) for c in mapping}
    statements, classes = [], {}
    for s, e in _statements(fea):
        stmt = fea[s:e]
        body = stmt.strip()
        if not any(t.search(stmt) for t in toks.values()):
            continue
        if re.match(r"(#[^\n]*\n\s*)*@\w+\s*=", body):
            classes.setdefault((s, e), []).extend(mapping[c] for c, t in toks.items() if t.search(stmt))
        elif body.startswith("sub") or (body.startswith("pos") and not body.startswith("pos base")):
            m = SINGLE_RE.match(stmt.strip("\n") + ("" if stmt.endswith(";") else ";"))
            if m and m.group(1) in skip_single_from:
                continue
            new = stmt
            for c, t in sorted(toks.items(), key=lambda kv: -len(kv[0])):
                new = t.sub(lambda _m, c=c: "\\" + mapping[c], new)
            statements.append((e, "\n" + new.strip("\n")))
    return statements, classes


def _apply(fea, statements, classes):
    edits = [(e, e, txt) for e, txt in statements]
    for (s, e), extra in classes.items():
        close = fea.rfind("]", s, e)
        edits.append((close, close, "".join(f" \\{x}" for x in dict.fromkeys(extra)) + " "))
    for start, end, txt in sorted(edits, key=lambda x: -x[0]):
        fea = fea[:start] + txt + fea[end:]
    return fea


def add_composites(font):
    overrides = (yaml.safe_load(OVERRIDES.read_text()) if OVERRIDES.exists() else None) or {}
    setup_new_marks(font)
    fea = font.features.text
    ligs = ligature_parts(fea)
    manifest, all_statements, all_classes = [], [], {}

    def existing(cp):
        return any(cp in g.unicodes for g in font)

    for char, base, accent, name in NEW_LETTERS:
        cp = ord(char)
        if existing(cp):
            continue
        capital = base[0].isupper()
        mark, anchor, suffix = MARKS[accent]
        ma = {x.name: (x.x, x.y) for x in font[mark].anchors}["_" + anchor]
        inferred, mapping = [], {}
        for cname in sorted(carriers(fea, base), key=len):
            new_name = (name or base + suffix) if cname == base else cname + suffix
            assert new_name not in font, f"{new_name} already exists"
            if cname in ligs:
                letter = next(c for c in ligs[cname] if c in carriers(fea, base))
                sx, sy = letter_shift(font, cname, letter)
                bx, by = resolve_anchor(font, letter, anchor, capital, overrides, inferred)
                bx, by = bx + sx, by + sy
            else:
                bx, by = resolve_anchor(font, cname, anchor, capital, overrides, inferred)
            dy = by - ma[1]
            dx = bx - ma[0] + dy * TAN
            g = font.newGlyph(new_name)
            g.width = font[cname].width
            g.components = [Component(baseGlyph=cname),
                            Component(baseGlyph=mark, transformation=(1, 0, 0, 1, round(dx), round(dy)))]
            mapping[cname] = new_name
        font[mapping[base]].unicodes = [cp]
        st, cl = _duplicate_statements(fea, mapping)
        all_statements += st
        for k, v in cl.items():
            all_classes.setdefault(k, []).extend(v)
        manifest.append({"kind": "accented", "char": char, "unicode": f"{cp:04X}", "glyph": mapping[base],
                         "base": base, "accent": accent, "mapping": mapping, "inferred": inferred})

    for char, glyph, base in REPLACEMENTS:
        cp = ord(char)
        if existing(cp) or glyph not in font:
            continue
        mapping = {base: glyph}
        for cname in sorted(carriers(fea, base, follow_single=False), key=len):
            if cname == base:
                continue
            entry = ligs[cname][0]
            sx, _ = letter_shift(font, cname, base)
            new_name = cname[: -len(base)] + glyph if cname.endswith(base) else cname + "_" + glyph
            g = font.newGlyph(new_name)
            # advance: keep the designer's relation between ligature and letter widths
            g.width = font[cname].width - font[base].width + font[glyph].width
            g.components = [Component(baseGlyph=entry, transformation=(1, 0, 0, 1, sx, 0)),
                            Component(baseGlyph=glyph, transformation=(1, 0, 0, 1, sx, 0))]
            mapping[cname] = new_name
        # variants of the base (e.g. ss03 d -> d1) are not drawn for the new
        # letter: under those stylistic sets it simply keeps its own shape
        font[glyph].unicodes = [cp]
        st, cl = _duplicate_statements(fea, mapping, skip_single_from={base})
        all_statements += st
        for k, v in cl.items():
            all_classes.setdefault(k, []).extend(v)
        manifest.append({"kind": "drawn", "char": char, "unicode": f"{cp:04X}", "glyph": glyph,
                         "base": base, "accent": None, "mapping": mapping,
                         "inferred": [{"glyph": glyph, "anchor": "shape", "pos": [], "how": "drawn"}]})

    font.features.text = _apply(fea, all_statements, all_classes)

    # spacing accents, ellipsis, minus: standalone glyphs, no join behaviour
    sb = 71  # side bearing of her period
    for char, name, mark in SPACING:
        cp = ord(char)
        if existing(cp) or name in font:
            continue
        bp = BoundsPen(font)
        font[mark].draw(bp)
        x0, _, x1, _ = bp.bounds
        g = font.newGlyph(name)
        g.width = round(x1 - x0 + 2 * sb)
        g.components = [Component(baseGlyph=mark, transformation=(1, 0, 0, 1, round(sb - x0), 0))]
        g.unicodes = [cp]
        manifest.append({"kind": "symbol", "char": char, "unicode": f"{cp:04X}", "glyph": name,
                         "base": mark, "accent": None, "mapping": {}, "inferred": []})
    if not existing(0x2026):
        w = font["period"].width
        g = font.newGlyph("ellipsis")
        g.width = 3 * w
        g.components = [Component(baseGlyph="period", transformation=(1, 0, 0, 1, i * w, 0)) for i in range(3)]
        g.unicodes = [0x2026]
        manifest.append({"kind": "symbol", "char": "…", "unicode": "2026", "glyph": "ellipsis",
                         "base": "period", "accent": None, "mapping": {}, "inferred": []})
    if "minus" in font and not existing(0x2212):
        font["minus"].unicodes = [0x2212]
        manifest.append({"kind": "symbol", "char": "−", "unicode": "2212", "glyph": "minus",
                         "base": "plus", "accent": None, "mapping": {}, "inferred": []})
    return manifest


def write_manifest(manifest, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
