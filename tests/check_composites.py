"""Check the accented letters added by scripts/composites.py.

    python tests/check_composites.py <font.ttf> <sources/X.ufo> <build/composites.json> [--out tests/report]

1. JOINS (exact): for every new letter X with base B, every context and every
   feature configuration, shaping text with X must equal shaping the same
   text with B, after mapping accented glyph names back to their carriers.
   Same glyphs, same clusters, same advances and offsets.
2. CLEARANCE: the gap between the accent and the letter (cedilla excluded:
   it is meant to touch). Gaps under the threshold are listed for review.
3. REVIEW PAGE: every new letter in context; inferred accent positions are
   marked so a person can confirm them.
"""
import argparse
import re
import html
import json
import sys
from pathlib import Path

import numpy as np
import ufoLib2
import yaml
from fontTools.pens.freetypePen import FreeTypePen
from fontTools.pens.transformPen import TransformPen
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import Font, feature_configs, png_b64, ink  # noqa: E402

LOWER = "abcdefghijklmnopqrstuvwxyz"
# accents that are meant to touch or cross the letter: no clearance check
TOUCHING = {"cedilla", "ogonek", "bar", "slash"}


def contexts(char, capital):
    out = [char, f"({char})", f"{char}.", f"'{char}"]
    for l in LOWER:
        out += [char + l, char + l + "n"]
        if not capital:
            out += [l + char, l + char + "n", "n" + l + char]
    return out


def check_joins(font, manifest, configs):
    mismatches, n, skipped = [], 0, 0
    for m in manifest:
        if m.get("kind") == "symbol":
            continue
        rev = {v: k for k, v in m["mapping"].items()}
        X, B = m["char"], m["base"]
        b_char = chr(next(u for u in font.tt.getBestCmap() if font.tt.getBestCmap()[u] == B))
        for cname, feats in configs.items():
            for text in contexts(X, X.isupper()):
                n += 1
                sx = font.shape(text, feats)
                sb = font.shape(text.replace(X, b_char), feats)
                ax = [(rev.get(g[0], g[0]),) + tuple(g[1:6]) for g in sx]
                ab = [tuple(g[:6]) for g in sb]
                if m.get("kind") == "drawn" and any(re.match(rf"^(cs\w+_)?{re.escape(B)}\d+$", g[0]) for g in sb):
                    skipped += 1  # base switches to a variant (e.g. ss03 d->d1); the new letter keeps its shape
                    continue
                if ax != ab:
                    mismatches.append({"char": X, "config": cname, "text": text,
                                       "with_accent": " ".join(g[0] for g in sx),
                                       "with_base": " ".join(g[0] for g in sb)})
    print(f"  (drawn letters: {skipped} runs skipped where the base letter becomes a stylistic variant)")
    return n, mismatches


def raster(ufo, glyph_name, offset=(0, 0), size=(3000, 3200), origin=(800, 1000)):
    pen = FreeTypePen(ufo)
    tp = TransformPen(pen, (1, 0, 0, 1, offset[0] + origin[0], offset[1] + origin[1]))
    ufo[glyph_name].draw(tp)
    return pen.array(width=size[0], height=size[1], contain=False) > 0.5


def clearance(ufo, manifest):
    rows = []
    for m in manifest:
        if m.get("kind", "accented") != "accented":
            continue
        for carrier, acc in m["mapping"].items():
            g = ufo[acc]
            base_c, mark_c = g.components
            dx, dy = mark_c.transformation[4], mark_c.transformation[5]
            a = raster(ufo, base_c.baseGlyph)
            b = raster(ufo, mark_c.baseGlyph, (dx, dy))
            overlap = int((a & b).sum())
            if overlap:
                gap = 0
            else:
                dist = ndimage.distance_transform_edt(~a)
                gap = float(dist[b].min()) if b.any() else float("nan")
            rows.append({"glyph": acc, "char": m["char"], "accent": m["accent"], "gap": round(gap),
                         "overlap_px": overlap,
                         "inferred": any(i["glyph"] in (carrier, base_c.baseGlyph) for i in m["inferred"])
                         or any(i["glyph"] == carrier for i in m["inferred"])})
    return rows


def review_page(out, font, manifest, clear, mismatches, n, th, verdict):
    e = html.escape
    by_char = {}
    for r in clear:
        by_char.setdefault(r["char"], []).append(r)
    parts = [f"""<!doctype html><html><head><meta charset="utf-8"><title>New letters review</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--muted:#666;--line:#ddd;--bad:#b3261e;--warn:#9a6700;--ok:#1d7a3a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151515;--fg:#eee;--muted:#aaa;--line:#333;--bad:#ff8a80;--warn:#e3b341;--ok:#5fd38a}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;max-width:1200px;margin:0 auto;padding:24px 16px}}
table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:middle}}
img{{background:#fff;height:64px}} .flag{{color:var(--warn);font-weight:600}} .bad{{color:var(--bad);font-weight:600}} .ok{{color:var(--ok);font-weight:600}}
</style></head><body>
<h1>New letters: review</h1>
<p class="{'ok' if verdict['pass'] else 'bad'}">Joins: {"PASS" if not mismatches else "FAIL"} – {n} shaping runs compared with the base letter, {len(mismatches)} differences.</p>
<p>Accent clearance threshold: {th['min_accent_gap']} units. <span class="flag">Inferred</span> = the designer never placed this accent on this letter; position calculated, please check.</p>
<table><tr><th>Letter</th><th>In context (new build)</th><th>Glyphs</th><th>Min gap</th><th>Placement</th></tr>"""]
    for m in manifest:
        X = m["char"]
        kind = m.get("kind", "accented")
        if kind == "symbol":
            words = f"a{X}b 1{X}2 {X}"
        elif X.islower():
            words = f"{X} n{X}n o{X}a {X}{X}"
        else:
            words = f"{X}an {X}o {X}{X.lower() if X.lower() != X else ''}n"
        img = font.render(font.shape(words, {}), 56)
        rows = by_char.get(X, [])
        gap = None
        if kind == "accented" and m["accent"] not in TOUCHING and rows:
            gap = min(r["gap"] for r in rows)
        inferred = sorted({i["glyph"] + "." + i["anchor"] for i in m["inferred"] if i.get("how") != "drawn"})
        if kind == "drawn":
            inferred = ["new drawing (draft)"]
        elif kind == "symbol":
            inferred = [f"new glyph from {m['base']} (draft)"]
        gap_txt = {"drawn": "–", "symbol": "–"}.get(kind) or ("touches (" + m["accent"] + ")" if gap is None else f"{gap}")
        gap_cls = "" if gap is None or gap >= th["min_accent_gap"] else "bad"
        parts.append(f"<tr><td style='font-size:20px'>{e(X)} <span style='color:var(--muted);font-size:13px'>U+{m['unicode']}</span></td>"
                     f"<td><img src='{png_b64(ink(img))}'></td><td>{len(m['mapping'])}</td>"
                     f"<td class='{gap_cls}'>{gap_txt}</td>"
                     f"<td>{'<span class=flag>Inferred: ' + e(', '.join(inferred)) + '</span>' if inferred else 'Designer anchors'}</td></tr>")
    parts.append("</table>")
    if mismatches:
        parts.append("<h2>Join differences</h2><table><tr><th>Config</th><th>Text</th><th>With accent</th><th>With base</th></tr>")
        for mm in mismatches[:200]:
            parts.append(f"<tr><td>{e(mm['config'])}</td><td>{e(mm['text'])}</td><td><code>{e(mm['with_accent'])}</code></td><td><code>{e(mm['with_base'])}</code></td></tr>")
        parts.append("</table>")
    parts.append("</body></html>")
    (out / "composites.html").write_text("\n".join(parts), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("font")
    ap.add_argument("ufo")
    ap.add_argument("manifest")
    ap.add_argument("--reference", default="upstream/fonts/cogncur.ttf")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "report"))
    ap.add_argument("--thresholds", default=str(Path(__file__).resolve().parent / "thresholds.yaml"))
    a = ap.parse_args()
    th = yaml.safe_load(Path(a.thresholds).read_text())
    manifest = json.loads(Path(a.manifest).read_text())
    font = Font(a.font)
    configs = feature_configs(Font(a.reference))
    n, mm = check_joins(font, manifest, configs)
    print(f"composite joins: {n} runs, {len(mm)} mismatches")
    clear = clearance(ufoLib2.Font.open(a.ufo), manifest)
    tight = [r for r in clear if r["accent"] not in TOUCHING and r["gap"] < th["min_accent_gap"]]
    print(f"accent clearance: {len(clear)} glyphs, {len(tight)} under {th['min_accent_gap']} units: "
          + ", ".join(f"{r['glyph']}={r['gap']}" for r in tight[:20]))
    inferred = sum(1 for m in manifest if m["inferred"])
    print(f"inferred placements to review: {inferred} letters")
    reasons = []
    if mm:
        reasons.append(f"{len(mm)} join differences")
    if tight:
        reasons.append(f"{len(tight)} accents closer than {th['min_accent_gap']} units")
    verdict = {"pass": not reasons, "reasons": reasons}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    review_page(out, font, manifest, clear, mm, n, th, verdict)
    print("VERDICT:", "PASS" if verdict["pass"] else "FAIL", "-", "; ".join(reasons) or "joins identical to base letters")
    print("review:", out / "composites.html")
    sys.exit(0 if verdict["pass"] else 1)


if __name__ == "__main__":
    main()
