import fontforge, sys
f = fontforge.open(sys.argv[1])
print("layers:", list(f.layers))
print("glyphs:", len(list(f.glyphs())), "em", f.em, "ascent", f.ascent, "descent", f.descent)
for tbl, lks in (("GSUB", f.gsub_lookups), ("GPOS", f.gpos_lookups)):
    print(tbl, len(lks))
    for lk in lks:
        info = f.getLookupInfo(lk)
        print(f"  {lk!r}: type={info[0]} feats={[x[0] for x in info[2]]} subtables={f.getLookupSubtables(lk)}")
