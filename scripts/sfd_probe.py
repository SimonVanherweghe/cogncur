import fontforge, sys
f = fontforge.open(sys.argv[1])
names = [g.glyphname for g in f.glyphs()]
open("build/sfd_glyphs.txt","w").write("\n".join(names))
hi = [g for g in f.glyphs() if g.unicode >= 0xE900]
print("glyphs", len(names), "worthoutputting", sum(1 for g in f.glyphs() if g.isWorthOutputting()), ">=E900:", len(hi))
f.generateFeatureFile("build/sfd_all.fea")
