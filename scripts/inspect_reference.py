"""Dump the structure of a reference TTF: features, lookup types, metrics, names."""
import sys
from collections import Counter
from fontTools.ttLib import TTFont

LOOKUP_NAMES = {
    "GSUB": {1: "single", 2: "multiple", 3: "alternate", 4: "ligature", 5: "context",
             6: "chaining-context", 7: "extension", 8: "reverse-chaining"},
    "GPOS": {1: "single", 2: "pair", 3: "cursive", 4: "mark-base", 5: "mark-lig",
             6: "mark-mark", 7: "context", 8: "chaining-context", 9: "extension"},
}

def lookup_type(lk):
    t = lk.LookupType
    if (lk.__class__.__name__ == "Lookup") and t in (7, 9) and lk.SubTable:
        return f"ext->{lk.SubTable[0].ExtensionLookupType}"
    return str(t)

def main(path):
    f = TTFont(path)
    print("file:", path)
    print("glyphs:", len(f.getGlyphOrder()), " cmap entries:", len(f.getBestCmap()))
    for nid in (1, 2, 3, 4, 5, 6, 0):
        n = f["name"].getName(nid, 3, 1, 0x409)
        print(f"  name {nid}: {n}")
    os2, hhea, head = f["OS/2"], f["hhea"], f["head"]
    print("UPM", head.unitsPerEm, " typo", os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap,
          " win", os2.usWinAscent, os2.usWinDescent, " hhea", hhea.ascent, hhea.descent, hhea.lineGap,
          " fsType", os2.fsType, " fsSelection", bin(os2.fsSelection))
    for tag in ("GSUB", "GPOS"):
        if tag not in f:
            print(tag, "absent"); continue
        t = f[tag].table
        print(f"\n{tag}: {len(t.LookupList.Lookup)} lookups")
        feats = Counter(fr.FeatureTag for fr in t.FeatureList.FeatureRecord)
        print("  features:", dict(feats))
        for fr in t.FeatureList.FeatureRecord:
            print(f"  {fr.FeatureTag}: lookups {fr.Feature.LookupListIndex}")
        for i, lk in enumerate(t.LookupList.Lookup):
            n_rules = sum(len(getattr(st, "ChainSubRuleSet", []) or getattr(st, "ChainPosRuleSet", []) or []) for st in lk.SubTable)
            print(f"  L{i}: type {lookup_type(lk)} subtables {len(lk.SubTable)}")

if __name__ == "__main__":
    main(sys.argv[1])
