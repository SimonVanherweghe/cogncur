# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@agents.md

## Commands
- `make venv` – create `.venv` (Python 3.13) from `requirements.txt`. FontForge (Homebrew, own Python) and HarfBuzz (`hb-shape`/`hb-view`) are also required. `requirements.txt` is a full `pip freeze` lock on purpose: an unpinned install backtracks to an unbuildable fontbakery 0.8.x (the `[googlefonts]` extra no longer exists). Regenerate it with `.venv/bin/pip freeze`.
- `make upstream` – clone syboor/cogncur into `upstream/` at the commit in `upstream.lock`.
- `make all` – `sources` → `build` → `test` → `qa`.
  - `make sources`: `.sfd` → UFO
  - `make build`: `gftools builder` → `fonts/ttf/`
  - `make test`: the test bank
  - `make qa`: fontbakery + diffenator2, both informational only.
- `make selftest` – reference vs itself; it must PASS with zero differences. Run it after changing `tests/compare.py`.
- `make designer` – `sources` + `build` + `scripts/designer_files.py`. Run it after **any** glyph change, then commit + push `docs/ontwerper/` (the issue comments link to `main`). Remind the user if a glyph changed and this wasn't done.
- `make artifact` – package `tools/live.html` + both fonts into `build/artifact/`. Republish that folder to the private artifact https://claude.ai/artifact/VMeKGZgUarp7qicDM7stXy (the same file path keeps the URL). The tool is in Dutch, with a feature table (designer descriptions) and config codes `vtex: ss03 ss08 -kern`; the link form is `#vtex-ss03-ss08-nokern`, since artifacts only pass plain hash names.
- `make serve` – opens `tools/live.html` at http://127.0.0.1:8765/tools/live.html. It shows the original and new fonts overlaid or on separate lines, with colour, opacity and OpenType toggles. Fonts are loaded by fetch, so file:// won't work. Both fonts get the same ascent/descent overrides so their baselines align.
- `make routes` – (~2.5 min, needs `sources` + `build`) drafts a pen route for every glyph with `scripts/routes.py` → `build/routes.json` + `tests/report/routes.html` (both gitignored). Centre lines come from the UFO `skeleton` layer, cut at junctions into pieces; the stroke order comes from upstream's `webapps/imgen/cogncur_shapes.svg`. A route is runs (pen-down lines) of steps `{p: piece, r: reversed}` / `{f: fill}`. Checks: ink coverage with the 68 pen, every calt join in the corpus × 20 feature configs (gap ≤ 20), and unbroken runs (`mend_runs`). Status: ok / guess (no stroke model) / review / missing / empty.
  - Connectors own the upstroke of l/b/h and the loop of e, while upstream's model puts them in the letter, so `fit_run` trims/turns the main run between the real entry and exit points from shaping.
  - Entry strokes: upstream's n draws "down the stem" in its entry stroke, so entry steps are only dropped when the letter draws that piece in the same direction, or dropping keeps the line unbroken.
  - Glyphs with several exits (B 8, D 9) are not baked in; `entries`/`exits` are stored and the word page walks to the right one.
- `make schrijven` – packages `tools/schrijven.html` (per-letter stroke animation from upstream's model) + a stripped stroke SVG into `build/schrijven/` for the private artifact https://claude.ai/artifact/GHSxAB5F1EdYWaTFFeimVN.
- `make site` – builds the website in `docs/` (served by GitHub Pages from `/docs` on `main`; locally http://127.0.0.1:8765/docs/ via `make serve`). Sources are in `site/` (pages, `style.css`, `nav.css`, `js/vtex.js`); `scripts/build_site.py` adds the header, copies in the tools (`live.html` → `proberen.html`, `woorden.html` → `schrijven.html`, `schrijven.html` → `letters.html`) and writes `docs/data/` (`tekens.json`: every character with its origin and decision issue; `build.json`: version, commit, date) and `docs/fonts/`. Run it after any glyph change (with `make routes` if the routes changed), then commit + push `docs/`.
  - **Feedback button**: on every page. It draws what is on screen to a canvas, copies it as PNG to the clipboard (inside the click: Safari needs that, so no `await` before `clipboard.write`), then a dialog links to `issues/new?template=<form>.yml&<field id>=…`. The issue forms are in `.github/ISSUE_TEMPLATE/` (Dutch); only `input`/`textarea` fields can be prefilled. Labels are set in the form, **never** via the `labels` URL parameter (it gives a 404 to people without triage rights). Text is drawn with harfbuzzjs (canvas `fillText` can't switch ssXX). Tool pages get the button via `site/js/tool-feedback.js`, which reads their DOM/hash, so the tools stay standalone.
  - `docs/img/` and `docs/ontwerper/` are not touched by `make site`. Labels: `python scripts/issues.py --labels`.
- `tools/woorden.html` (via `make serve`, needs `make routes`) – animates typed text as one pen line, connectors included: shapes with harfbuzzjs 1.6.3 in the browser (glyph ids → names via `glyphOrder` in routes.json), chains the glyph routes, and where a route does not end at the next connector it takes the shortest walk over the glyph's centre lines (Dijkstra), else lifts the pen. Dots/accents/crossbars "na het woord" (default) or "na elke letter". `window.schrijfroute.scene` exposes the plan for debugging; reload after edits (the dev server caches).
- To test a single font against the reference: `.venv/bin/python tests/compare.py upstream/fonts/cogncur.ttf <font.ttf> --out <dir>`

## Pipeline (why it looks like this)
- **Source of truth**: `upstream/sources/Cogncur.sfd` (FontForge), which is never modified. Glyphs are drawn as centre lines on the `Skeleton`/`Extra` layers. The style layers (`GRegOutl` = Regular, `GOutline` = Vertical, `GSlOutl` = Oblique, `GEdged`, `GRegEdged`) are pre-stroked copies stored in the sfd.
- **`scripts/export_ufo.py`** runs under FontForge's Python and automates the manual build steps from `upstream/sources/howto.txt`. FontForge ignores `generate(layer=…)` for UFO output, so the script copies the style layer into `Fore` itself. It also exports the skew-matched `Skeleton` (centre lines) and `Extra` (dots, commas) layers as separate UFOs; postprocess stores them as UFO layers `skeleton` and `extra` (not built into the font; for a later pen-plotter export and the designer files). They must stay separate: closed centre lines (o, e, rings) can't be told apart from filled shapes by size.
- **`scripts/postprocess_ufo.py`** makes these changes:
  - removes the `[space]` placeholder backtrack from the 4 `msstart*` calt rules (howto step 9). It matches the class by content, because its name (`@ccNN_back_12`) changes between exports.
  - prunes ~6000 references to deleted single-substitution glyphs (FontForge drops them silently; feaLib errors)
  - sets GF metadata from `scripts/config.py`; the family name `Vtex` is a placeholder (Liesbeth OK'd keeping "Cogncur" + a suffix per variant on 2026-11-07; the exact name, RFN exception/CLA and credits/license files are still open)
  - applies the small glyph fixes in `fix_glyphs()` (U+00A0, empty U+2010)
  - `clean_outlines()`: RDP-simplifies FontForge stroker glitches, turns straight quadratics into lines and drops 1-unit kinks; open contours (`ccq2s`, `tallestglyph`) are skipped
  - `add_gf_extras()`: meta table, ligature carets, dotted circle
  - then runs `composites.add_composites()` and writes `build/composites.json`.
- Outlines are **quadratic**, so `sources/config.yaml` passes `--overlaps-backend pathops`.
- **Joins** are the critical part. They come from `calt`: a chaining lookup that calls ~46 multiple-substitution lookups, each splitting a letter into connector + letter (+ exit stroke), keyed on the previous glyph. Glyph names must stay identical to the reference, because the test bank compares them.

## New glyphs drawn in FontForge (`scripts/new_glyphs_ff.py`)
New marks, bars, ð þ Þ ẞ and − are drawn the way the designer works: centre lines on `Skeleton`, filled shapes (dots, commas) on `Extra`. The style layer is then derived with the `derive-layers.py` recipe (skew + round pen of 68). They are drafts; `docs/new-glyphs.md` lists what each one is derived from.

## New letters (`scripts/composites.py`)
Accented letters missing upstream are built as components (carrier + the designer's combining mark), positioned on her anchors. Anchors are stored unslanted, so the mark is also shifted by the lift × tan 7.5°.

Every glyph that "carries" the base letter gets an accented copy, and every feature statement mentioning it is duplicated:
- variants via single substitution (`s→s1`)
- entry-stroke ligatures (`cs*_*` only, never e.g. the Dutch `IJ`). The letter's position inside the ligature is found by ink matching (`scripts/locate.py`), which reproduces all upstream precedents exactly. The width rule (ligature width − letter width) is off by up to 2 units.

"Replacement" letters (ð þ Þ ẞ) have their own outline but copy the joins of d/p/P/B. Their entry ligatures are rebuilt as entry + letter, and the advance keeps the designer's width relation. They do **not** follow the base letter's stylistic variants (ss03 d→d1, ss15/16 p→p1…p7); the composite test skips those runs.

New marks get anchors, code points and GDEF classes in `setup_new_marks()`. They must be removed from `@GDEF_Simple`, because a glyph may be in only one GDEF class. Anchors that can't be inferred (`caronvert`, `bar`, `slash`, some `ogonek`) come from `PROPOSED` in `composites.py`; a missing one raises an error instead of guessing.

Positions on letters the designer never accented are *inferred*. They are listed in `build/composites.json` for review and can be overridden in `sources/anchors.yaml` (key `glyph.anchor: [x, y]`, unslanted).

Positions are also in `sources/anchors.yaml` (overrides win over designer anchors, then `PROPOSED`, then inference).

`tests/check_composites.py` requires that every new letter shapes exactly like its base letter, in every context and feature configuration. It also checks accent clearance and writes `tests/report/composites.html`.

## Test bank (`tests/`)
`tests/compare.py` compares against `upstream/fonts/cogncur.ttf` in four layers:
1. HarfBuzz shaping (glyph names + positions) for every corpus line × every feature configuration (default, each ssXX, tnum, onum, calt-off, kern-off)
2. connected ink components per word (catches broken joins)
3. per-glyph raster diff and advance widths
4. flattened GSUB lookups.

The corpus is generated by `scripts/make_corpus.py`: all letter pairs and triples, uppercase+lowercase, accents, words, punctuation contexts. Thresholds and the **intentional changes** list (each with a reason) are in `tests/thresholds.yaml`. Every deliberate deviation from the reference must be added there.

Runs where the reference itself renders `.notdef` (e.g. `…`, which the original lacks) are skipped, not counted as differences.

## Gotchas
- FontForge ignores `generate(layer=…)` for UFO output (see export_ufo.py). Its Python is separate (3.14) from `.venv`; run FF scripts with `fontforge -lang=py -script`.
- macOS make 3.81 ignores `export PATH` for simple commands, so the Makefile calls `.venv/bin/<tool>` explicitly. `gftools builder` needs the venv on PATH, so it is set inline.
- ufoLib2 points compare **by value**: `list.remove(point)` can delete the wrong point. Use `_remove()` (identity) in postprocess_ufo.py.
- The designer's anchors are unslanted; capital accents are lifted 682 units, so they shift 682 × tan 7.5° ≈ 90.
- Her `G` has a descender loop (yMin −682), and some ligatures (`css1_s1`) were hand-modified. Don't assume entry + letter is exact; match ink.
- The `make all`/`make test` exit code is currently 1 because of one known, intended flag (see open items).

## Open technical items (status 2026-11-06; design decisions live in the GitHub issues)
- **ľ + ss01**: under ss01 the entry stroke into l (`csh_l`) comes from the top right and touches the apostrophe-caron (`csh_lcaron`, gap 10 < 40). This is the only failure in `make test`.
- **Dutch j́** (fontbakery `shape_languages` FAIL): with j + U+0301 at a word end, calt inserts the exit stroke `cej` between j and the mark. The original font behaves identically. A possible fix is a mark anchor on `cej` pointing back over the j; this is not decided yet.
- **Ģ**: the comma below sits at the foot of G's descender loop and looks odd; turned comma above is the alternative.
- **¶ ™**: the last missing GF Latin Core codepoints (fontbakery `glyph_coverage` FAIL).
- Remaining fontbakery WARNs are accepted or known:
  - math sign widths, vendor ID
  - brackets semi-vertical (slanted by design)
  - spurs in W, W1, ccgt (shape question)
  - contour counts.
- The generated UFO is not committed yet; Google Fonts needs sources in the repo eventually.

## GitHub (private repo `SimonVanherweghe/cogncur-tex`)
- Decision issues are in Dutch and created by `scripts/issues.py`. Each has a hidden `<!-- beslissing:<id> -->` marker, so re-runs skip existing issues. Each option is a separate comment, and people vote with 👍.
- Images are rendered by `scripts/render_sample.py` (same shaping/rendering as the test bank, on writing lines) into `docs/img/`. They are linked as `https://github.com/<repo>/blob/main/docs/img/<file>?raw=true`, so **commit and push the images before creating the issue**.
- Labels: `beslissing`, `ontwerper`, `leerkrachten`, `iedereen`.
- Issue file names use `slug()` (the id, or `"slug"`): macOS is case-insensitive, so `schets-thorn` and `schets-Thorn` collided (issue #3 showed Þ). Slugs must differ by more than case.
- **Designer files**: `scripts/designer_files.py` writes `docs/ontwerper/<slug>/` for every `ontwerper` issue (glyphs listed in its `"bestanden"`): per glyph an SVG (unslanted, font units, layers hulplijnen/omtrek/middenlijn/vlakken) and an EPS for FontForge *Import* onto Skeleton, plus `overzicht.svg/.eps` of the sample lines. The EPS paints centre lines with `fill`: FontForge expands `stroke` into outlines on import and has no flag against it, but keeps filled open paths open. `python scripts/issues.py --files` adds one comment per designer issue linking them (marker `<!-- bestanden:<id> -->`); commit and push the files first.
- The public fork `SimonVanherweghe/vtex-font` only mirrors upstream; leave it alone (forks of public repos can't be private).
