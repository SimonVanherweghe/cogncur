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
