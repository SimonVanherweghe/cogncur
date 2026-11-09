# New glyphs: what they are made of

These are drafts for review. Nothing here was drawn by the original designer,
but every glyph is built from her shapes or with her pen. Her pen is a round
nib of 68 units on a centre line, slanted 7.5° (see `upstream/sources/derive-layers.py`).

| Glyph(s) | Built from | Where |
|---|---|---|
| ć č ě ğ ń ň ŕ ř ś ş ź ŵ ẁ ẃ ẅ, Ć Č Ď Ě Ğ Ĺ Ń Ň Ŕ Ř Ś Ş Ť Ź Ŵ Ẁ Ẃ Ẅ Ỳ Ĩ Ǎ Ǐ Ǒ Ǔ Ȳ Ẽ Ỹ | her letter + her accent, on her anchors (inferred on letters she never accented) | `scripts/composites.py` |
| ˙ (dot above) → ċ ė ġ ż Ċ Ė Ġ Ż İ | the exact dot of her `i` | `scripts/new_glyphs_ff.py` |
| ˝ (double acute) → ő ű Ő Ű | two of her acute strokes, narrowed to 80 % | idem |
| ̦ (comma below) → ș ț Ș Ț ķ ļ ņ Ķ Ļ Ņ Ģ | her comma at 80 % | idem |
| ̒ (turned comma above) → ģ | her comma, rotated 180° | idem |
| ˛ (ogonek) → ą ę į ų Ą Ę Į Ų | new centre line, stroked with her pen | idem |
| apostrophe-caron → ď ľ ť Ľ | her right single quote, right of the ascender | idem |
| bar → Đ Ð đ Ħ ħ, slash → Ł ł | straight centre lines, stroked with her pen | idem |
| ð | her `d` bowl + a stem bending left + a slash | idem |
| þ | her `b` ascender loop + her `p` descender and bowl | idem |
| Þ | her `P` with the bowl lowered to the middle | idem |
| ẞ | her `B` stem and lower bowl + a flat top and a diagonal | idem |
| − | the horizontal stroke of her `+` | idem |
| ¯ ˆ ˇ ˘ ˙ ˚ ˛ ˜ ˝ (spacing accents) | her combining accents with period-like side bearings | `scripts/composites.py` |
| … | three of her periods | idem |

The joins of every new letter are copied from a base letter: ð joins like d, þ like p, Þ like P and ẞ like B.
`tests/check_composites.py` proves they shape exactly like that base letter. Under stylistic sets
that swap the base for a variant (ss03 d→d1, ss15/16 p→p1…p7), ð and þ keep their own shape and
connectors.

To move an accent, add a line to `sources/anchors.yaml`, e.g. `l.caronvert: [540, 1330]`.
Coordinates are unslanted font units, like the designer's anchors.

## Checklist: the designer's own principles

Her documentation, [Typeface Features](https://cogncur.com/documentation/typeface-features)
(also in `upstream/documentation/typeface-features.html`), describes the rules her letters follow.
`make principles` measures the new letters against them, on the centre lines, and compares every
number with her own letters (report: `tests/report/principles.html`). The results below are
measurements, not decisions: whether a new letter should follow a rule is for the designer.

| Principle (her documentation) | How it is measured | ð | þ | Þ | ẞ |
|---|---|---|---|---|---|
| Straight downstrokes lean 7.5° and are parallel ("Loops and sticks", "Implied slant") | slant of every straight run ≥ 250 units | ✅ 7.50° up to y 728; above that the stem bends left (new) | ✅ 7.50° | ✅ her P stem | ✅ her B stem |
| Tall loops (b h k l) cross themselves exactly on the waist line | crossings in shaped text, because the upstroke belongs to the connector (`ub` crosses at y 648) | – | ❓ **no loop**: þ joins like p (`ccni`), so the ascender is a stick with b's hook on top | – | – |
| d and p have a stick, not a loop | – | ✅ like d | ❓ follows p (stick); a loop would be b-like | – | – |
| Arches and counters branch out/in halfway up the x-height | where the line leaves or joins the stem (her p 0.55, d 0.45) | ✅ 0.45, same as d | ✅ 0.55, same as p | – | – |
| Teardrop counters start on the waist line; c, e, o share one ellipse (ratio 1.618) | origin check: the bowl is hers, unchanged | ✅ d's bowl | ✅ p's bowl | – | – |
| Capitals look like print capitals and are initials, joined to the next lowercase letter (P and B with a pen lift) | joins copied from the base letter (`tests/check_composites.py`) | – | – | ✅ like P | ✅ like B |
| Width based on the golden rectangle | advance width | = d (786) | = p (766) | = P (563) | = B (805) |

What is new, and so not covered by any of her shapes (red in the report):

- **ð**: the top of the stem bending left (483 units of line) and the slash, which crosses the stem at y 1036.
- **þ**: nothing; it is b's ascender + p. The open question is the loop above.
- **Þ**: nothing; it is her P with the bowl moved down 300 units.
- **ẞ**: the top arch, the diagonal and the curve into the lower bowl (1516 units); the stem and the lower bowl are B's.

Her documentation has no rule for ð's bent stem and slash, or for the top of ẞ. Those are design choices for her.
