"""Export one style of upstream Cogncur.sfd to UFO, reproducing the manual
build procedure from upstream/sources/howto.txt ("BUILDING THE FONTS FOR
MULTIPLE SUBSTITUTION") in a scripted, repeatable way.

Run with FontForge's Python:
    fontforge -lang=py -script scripts/export_ufo.py <in.sfd> <layer> <out.ufo> [<skeleton_out.ufo> [<extra_out.ufo>]]

The .sfd is opened read-only in memory and never saved.
The 'space' placeholder fix (howto step 9) is done afterwards on the
feature file by postprocess_ufo.py, because FontForge's Python API does not
expose contextual-chaining rules.
"""
import math
import sys

import fontforge
import psMat

src, layer, out = sys.argv[1:4]
skeleton_out = sys.argv[4] if len(sys.argv) > 4 else None
extra_out = sys.argv[5] if len(sys.argv) > 5 else None

f = fontforge.open(src)

# howto step 3: drop single-substitution variants of the calt machinery (if any)
for lk in list(f.gsub_lookups):
    if lk.startswith("ss-"):
        f.removeLookup(lk)
# howto step 4: helper lookup for deriving glyphs, not for OpenType use
if "ligatures-connected" in f.gsub_lookups:
    f.removeLookup("ligatures-connected")
# howto step 5: ms-calt must be attached to calt
info = f.getLookupInfo("ms-calt - connections between letters")
assert any(feat[0] == "calt" for feat in info[2]), "ms-calt is not attached to calt"
# howto step 6: helper ligatures from U+E900 onwards are not part of the font
for g in list(f.glyphs()):
    if g.unicode >= 0xE900:
        f.removeGlyph(g)

# New glyphs (drafts), drawn on the Skeleton/Extra layers and derived with
# the same recipe as derive-layers.py; see scripts/new_glyphs_ff.py.
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import new_glyphs_ff  # noqa: E402
print("new glyphs:", " ".join(new_glyphs_ff.build(f, layer)))

# FontForge ignores generate(layer=...) for UFO output, so copy the derived
# style layer into the foreground explicitly.
empty = []
for g in f.glyphs():
    g.layers["Fore"] = g.layers[layer]
    if len(g.layers["Fore"]) == 0 and g.width > 0 and g.unicode not in (0x20, 0xA0):
        empty.append(g.glyphname)
f.generate(out)
print(f"exported {layer} -> {out}  ({len(empty)} non-space glyphs without outline)")
if empty:
    print("  empty:", " ".join(empty[:40]))

if skeleton_out:
    # Single-stroke (centre-line) version for a later pen-plotter export, and
    # the designer's 'Extra' layer (dots, commas: filled shapes) separately, so
    # closed centre lines (o, e, rings) can be told apart from filled shapes.
    # Same skew as the Regular style (7.5 deg, see derive-layers.py).
    skew = psMat.skew(7.5 * math.pi / 180.0)
    noskew = {"asciitilde", "underscore", "uni203E"}
    extra = {}
    for g in f.glyphs():
        sk = g.layers["Skeleton"]
        ex = g.layers["Extra"]
        if g.glyphname not in noskew:
            sk.transform(skew)
            ex.transform(skew)
        g.layers["Fore"] = sk
        extra[g.glyphname] = ex
    f.generate(skeleton_out, layer="Fore")
    print(f"exported skeleton -> {skeleton_out}")
    if extra_out:
        for g in f.glyphs():
            g.layers["Fore"] = extra[g.glyphname]
        f.generate(extra_out, layer="Fore")
        print(f"exported extra -> {extra_out}")
