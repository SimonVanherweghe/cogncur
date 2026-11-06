"""Test bank: compare a new build against the upstream reference font.

    python tests/compare.py <reference.ttf> <new.ttf> [--out tests/report]

Layers of checks (most important first; joins are the critical part):
  1. SHAPING   every corpus line x every feature configuration is shaped with
               HarfBuzz in both fonts. The glyph sequence (names), advances and
               offsets must be identical. This is the exact test for the
               connection logic (calt) and kerning.
  2. CONNECT   every word is rendered and its connected ink components are
               counted. The count must equal the reference (a broken join shows
               up as an extra component even if the shaping looks right).
  3. GLYPHS    every glyph present in both fonts is rasterised individually
               (unhinted) and pixel-diffed; advance widths are compared.
  4. LOOKUPS   non-contextual GSUB lookups are flattened and matched between
               the fonts, to spot silently dropped substitutions.
Writes summary.json and index.html; exits 1 if a threshold is exceeded.
"""
import argparse
import base64
import html
import io
import json
import sys
from pathlib import Path

import freetype
import numpy as np
import uharfbuzz as hb
import yaml
from fontTools.ttLib import TTFont
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"


# --------------------------------------------------------------------- fonts
class Font:
    def __init__(self, path):
        self.path = str(path)
        blob = hb.Blob.from_file_path(self.path)
        self.hb_face = hb.Face(blob)
        self.hb_font = hb.Font(self.hb_face)
        self.upem = self.hb_face.upem
        self.tt = TTFont(self.path)
        self.order = self.tt.getGlyphOrder()
        self.ft = freetype.Face(self.path)
        self._cache = {}
        self._ppem = None

    def shape(self, text, features):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf, features)
        out = []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            out.append((self.order[info.codepoint], info.cluster,
                        pos.x_advance, pos.y_advance, pos.x_offset, pos.y_offset, info.codepoint))
        return out

    def _glyph_bitmap(self, gid, ppem):
        if self._ppem != ppem:
            self.ft.set_pixel_sizes(0, ppem)
            self._ppem, self._cache = ppem, {}
        if gid not in self._cache:
            self.ft.load_glyph(gid, freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_RENDER)
            g = self.ft.glyph
            bm = g.bitmap
            arr = np.array(bm.buffer, dtype=np.uint8).reshape(bm.rows, bm.width) if bm.rows else np.zeros((0, 0), np.uint8)
            self._cache[gid] = (arr, g.bitmap_left, g.bitmap_top)
        return self._cache[gid]

    def render(self, shaped, ppem, canvas=None):
        """Render a shaped run to a grayscale array. canvas=(w, h, baseline)."""
        s = ppem / self.upem
        total = sum(g[2] for g in shaped) * s
        w, h, base = canvas or (int(total + ppem * 2), int(ppem * 2.2), int(ppem * 1.4))
        img = np.zeros((h, w), np.uint16)
        x = ppem * 0.5
        for name, cl, xa, ya, xo, yo, gid in shaped:
            arr, left, top = self._glyph_bitmap(gid, ppem)
            if arr.size:
                px = int(round(x + xo * s)) + left
                py = base - top - int(round(yo * s))
                y0, x0 = max(py, 0), max(px, 0)
                y1, x1 = min(py + arr.shape[0], h), min(px + arr.shape[1], w)
                if y1 > y0 and x1 > x0:
                    img[y0:y1, x0:x1] += arr[y0 - py:y1 - py, x0 - px:x1 - px]
            x += xa * s
        return np.clip(img, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ helpers
def feature_configs(ref: Font):
    tags = sorted({fr.FeatureTag for fr in ref.tt["GSUB"].table.FeatureList.FeatureRecord})
    configs = {"default": {}}
    for t in tags:
        if t.startswith("ss") or t in ("tnum", "onum"):
            configs[t] = {t: True}
    if "ss08" in configs and "ss09" in configs:
        configs["ss08+ss09"] = {"ss08": True, "ss09": True}
    configs["calt-off"] = {"calt": False}
    configs["kern-off"] = {"kern": False}
    return configs


def components(img, thresh=96):
    _, n = ndimage.label(img >= thresh, structure=np.ones((3, 3)))
    return n


def png_b64(arr):
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def ink(arr):
    """Black ink on white."""
    return 255 - arr


def diff_img(a, b):
    h, w = max(a.shape[0], b.shape[0]), max(a.shape[1], b.shape[1])
    A = np.zeros((h, w), np.uint8); A[:a.shape[0], :a.shape[1]] = a
    B = np.zeros((h, w), np.uint8); B[:b.shape[0], :b.shape[1]] = b
    rgb = np.full((h, w, 3), 255, np.uint8)
    both = np.minimum(A, B)
    rgb[..., 0] -= both; rgb[..., 1] -= both; rgb[..., 2] -= both
    only_a = np.clip(A.astype(int) - B, 0, 255).astype(np.uint8)  # reference only -> red
    only_b = np.clip(B.astype(int) - A, 0, 255).astype(np.uint8)  # new only -> blue
    rgb[..., 1] -= np.minimum(rgb[..., 1], only_a); rgb[..., 2] -= np.minimum(rgb[..., 2], only_a)
    rgb[..., 0] -= np.minimum(rgb[..., 0], only_b); rgb[..., 1] -= np.minimum(rgb[..., 1], only_b)
    return rgb


def pad_to(a, shape):
    out = np.zeros(shape, np.uint8)
    out[:a.shape[0], :a.shape[1]] = a[:shape[0], :shape[1]]
    return out


def load_corpus():
    items = []
    for p in sorted(CORPUS.glob("*.txt")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                items.append((p.stem, line))
    return items


def words_of(line):
    return [w for w in line.split(" ") if w]


# ------------------------------------------------------------------- checks
def check_shaping(ref, new, corpus, configs):
    mismatches, n = [], 0
    for cname, feats in configs.items():
        for group, line in corpus:
            n += 1
            a = [g[:6] for g in ref.shape(line, feats)]
            b = [g[:6] for g in new.shape(line, feats)]
            if any(g[0] == ".notdef" for g in a):
                continue  # the reference can't render this line: nothing to compare against
            if a != b:
                mismatches.append({"config": cname, "group": group, "text": line,
                                   "ref": " ".join(f"{g[0]}@{g[2]}" for g in a),
                                   "new": " ".join(f"{g[0]}@{g[2]}" for g in b)})
    return n, mismatches


def check_connectivity(ref, new, corpus, configs, ppem):
    mismatches, n, notdef = [], 0, []
    for cname, feats in configs.items():
        if cname in ("calt-off",):
            continue
        for group, line in corpus:
            for w in words_of(line):
                n += 1
                sa, sb = ref.shape(w, feats), new.shape(w, feats)
                # only a regression if the reference *does* support the word
                if any(g[0] == ".notdef" for g in sb) and not any(g[0] == ".notdef" for g in sa):
                    notdef.append({"config": cname, "text": w})
                if any(g[0] == ".notdef" for g in sa):
                    continue  # reference can't render this word
                ia, ib = ref.render(sa, ppem), new.render(sb, ppem)
                ca, cb = components(ia), components(ib)
                if ca != cb:
                    shape = (max(ia.shape[0], ib.shape[0]), max(ia.shape[1], ib.shape[1]))
                    ia, ib = pad_to(ia, shape), pad_to(ib, shape)
                    mismatches.append({"config": cname, "group": group, "text": w, "ref": ca, "new": cb,
                                       "img_ref": png_b64(ink(ia)), "img_new": png_b64(ink(ib)),
                                       "img_diff": png_b64(diff_img(ia, ib))})
    return n, mismatches, notdef


def check_glyphs(ref, new, ppem, pixel_tol):
    names = [g for g in new.order if g in set(ref.order)]
    rows, adv_diff = [], []
    for name in names:
        ga, gb = ref.order.index(name), new.order.index(name)
        wa, wb = ref.tt["hmtx"][name][0], new.tt["hmtx"][name][0]
        if wa != wb:
            adv_diff.append({"glyph": name, "ref": wa, "new": wb})
        sa = [(name, 0, wa, 0, 0, 0, ga)]
        sb = [(name, 0, wb, 0, 0, 0, gb)]
        canvas = (int(max(wa, wb) / ref.upem * ppem + ppem * 2), int(ppem * 2.2), int(ppem * 1.4))
        ia, ib = ref.render(sa, ppem, canvas), new.render(sb, ppem, canvas)
        d = np.abs(ia.astype(int) - ib.astype(int))
        diff_px = int((d > pixel_tol).sum())
        ink_px = max(int((ia > pixel_tol).sum()), 1)
        rows.append({"glyph": name, "diff_px": diff_px, "ratio": diff_px / ink_px,
                     "_imgs": (ia, ib)})
    rows.sort(key=lambda r: -r["ratio"])
    return names, rows, adv_diff


def flatten_gsub(tt):
    """Multiset of (type, mapping) for non-contextual GSUB lookups."""
    out = []
    t = tt["GSUB"].table
    for lk in t.LookupList.Lookup:
        for st in lk.SubTable:
            typ = lk.LookupType
            if typ == 7:
                typ, st = st.ExtensionLookupType, st.ExtSubTable
            if typ == 1:
                out.append(("single", frozenset(st.mapping.items())))
            elif typ == 2:
                out.append(("multiple", frozenset((k, tuple(v)) for k, v in st.mapping.items())))
            elif typ == 4:
                out.append(("ligature", frozenset((k, tuple(l.Component), l.LigGlyph)
                                                  for k, ls in st.ligatures.items() for l in ls)))
    return out


def check_lookups(ref, new):
    # entries with glyphs only one font has: empty leftovers in the reference,
    # new letters in the new build (those are checked by check_composites.py)
    ignore = set(ref.order) ^ set(new.order)
    def clean(items):
        res = []
        for typ, m in items:
            kept = frozenset(e for e in m if not (set(_names(e)) & ignore))
            res.append((typ, kept))
        return res
    a, b = clean(flatten_gsub(ref.tt)), clean(flatten_gsub(new.tt))
    unmatched_ref = [x for x in a if x not in b]
    unmatched_new = [x for x in b if x not in a]
    def desc(x):
        typ, m = x
        return {"type": typ, "entries": len(m), "sample": [str(e) for e in list(m)[:3]]}
    return len(a), [desc(x) for x in unmatched_ref], [desc(x) for x in unmatched_new]


def _names(entry):
    for part in entry:
        if isinstance(part, tuple):
            yield from part
        else:
            yield part


# ------------------------------------------------------------------- report
def write_report(out, summary, shaping_mm, conn_mm, glyph_rows, adv_diff, lookups, ref, new, ppem, verdict,
                 expected=(), intentional=None):
    out.mkdir(parents=True, exist_ok=True)
    # visual sample: real words in both fonts
    samples = []
    for line in (CORPUS / "words.txt").read_text(encoding="utf-8").splitlines()[:4] + \
            (CORPUS / "context.txt").read_text(encoding="utf-8").splitlines():
        sa, sb = ref.shape(line, {}), new.shape(line, {})
        ia, ib = ref.render(sa, 40), new.render(sb, 40)
        shape = (max(ia.shape[0], ib.shape[0]), max(ia.shape[1], ib.shape[1]))
        ia, ib = pad_to(ia, shape), pad_to(ib, shape)
        samples.append((line, png_b64(ink(ia)), png_b64(ink(ib)), png_b64(diff_img(ia, ib))))
    # join grid: all lowercase pairs in the new font
    grid = []
    for a in "abcdefghijklmnopqrstuvwxyz":
        row = []
        for b in "abcdefghijklmnopqrstuvwxyz":
            w = a + b
            img = new.render(new.shape(w, {}), 28)
            bad = any(m["text"] == w and m["config"] == "default" for m in conn_mm)
            row.append((w, png_b64(ink(img)), bad))
        grid.append(row)

    e = html.escape
    status_cls = "ok" if verdict["pass"] else "fail"
    parts = [f"""<!doctype html><html><head><meta charset="utf-8"><title>Test bank report</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--muted:#666;--line:#ddd;--ok:#1d7a3a;--bad:#b3261e;--card:#f6f6f4}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151515;--fg:#eee;--muted:#aaa;--line:#333;--card:#202020;--ok:#5fd38a;--bad:#ff8a80}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1200px;padding:24px 16px}}
h1{{font-size:22px}} h2{{margin-top:36px;border-bottom:1px solid var(--line);padding-bottom:4px}}
table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}}
.ok{{color:var(--ok);font-weight:600}} .fail{{color:var(--bad);font-weight:600}} .muted{{color:var(--muted)}}
img{{background:#fff;max-width:100%;image-rendering:auto}} code{{font-size:12px}}
.grid td{{padding:1px;border:1px solid var(--line);text-align:center}} .grid img{{height:28px}} .grid td.bad{{outline:3px solid var(--bad)}}
.legend span{{display:inline-block;padding:0 6px;margin-right:6px}}
</style></head><body>
<h1>Test bank: <code>{e(Path(new.path).name)}</code> vs reference <code>{e(Path(ref.path).name)}</code></h1>
<p class="{status_cls}">Automatic verdict: {"PASS" if verdict["pass"] else "FAIL"}</p>
<ul>{"".join(f"<li>{e(r)}</li>" for r in verdict["reasons"])}</ul>
<table><tr><th>Check</th><th>Tested</th><th>Problems</th></tr>
<tr><td>Shaping (glyphs + positions), all feature configs</td><td>{summary["shaping_tested"]}</td><td>{summary["shaping_mismatches"]}</td></tr>
<tr><td>Join connectivity (ink components per word)</td><td>{summary["connect_tested"]}</td><td>{summary["connect_mismatches"]}</td></tr>
<tr><td>Missing glyphs (.notdef) in new font</td><td>{summary["connect_tested"]}</td><td>{summary["notdef"]}</td></tr>
<tr><td>Glyph outlines (pixel diff &gt; {summary["glyph_ratio_max"]:.1%} of ink)</td><td>{summary["glyphs_tested"]}</td><td>{summary["glyphs_over_threshold"]}</td></tr>
<tr><td>Advance widths</td><td>{summary["glyphs_tested"]}</td><td>{summary["advance_mismatches"]}</td></tr>
<tr><td>GSUB non-contextual lookups (flattened)</td><td>{summary["lookups_tested"]}</td><td>{summary["lookups_unmatched_ref"]} missing / {summary["lookups_unmatched_new"]} extra</td></tr>
</table>
<p class="muted">Feature configs: {e(", ".join(summary["configs"]))}. Render size {ppem} ppem, unhinted.</p>
<p class="legend muted">Diff colours: <span style="background:#000;color:#fff">both</span><span style="color:#d00">reference only</span><span style="color:#00d">new only</span></p>
<h2>Intentional changes ({len(intentional or {})})</h2>
<table><tr><th>Glyph</th><th>Reason</th><th>Diff</th></tr>{"".join(f"<tr><td>{e(r['glyph'])}</td><td>{e((intentional or {}).get(r['glyph'], ''))}</td><td><img src='{png_b64(diff_img(*r['_imgs']))}'></td></tr>" for r in expected)}</table>
<h2>Sample text</h2><table><tr><th>Text</th><th>Reference / New / Diff</th></tr>"""]
    for line, a, b, d in samples:
        parts.append(f"<tr><td>{e(line)}</td><td><img src='{a}'><br><img src='{b}'><br><img src='{d}'></td></tr>")
    parts.append("</table><h2>All lowercase joins (new font)</h2><p class='muted'>Red outline = connectivity differs from reference.</p><table class='grid'>")
    for row in grid:
        parts.append("<tr>" + "".join(f"<td class='{'bad' if bad else ''}' title='{w}'><img src='{img}'></td>" for w, img, bad in row) + "</tr>")
    parts.append("</table>")

    parts.append(f"<h2>Shaping mismatches ({len(shaping_mm)})</h2>")
    if shaping_mm:
        parts.append("<table><tr><th>Config</th><th>Text</th><th>Reference</th><th>New</th></tr>")
        for m in shaping_mm[:300]:
            parts.append(f"<tr><td>{e(m['config'])}</td><td>{e(m['text'])}</td><td><code>{e(m['ref'])}</code></td><td><code>{e(m['new'])}</code></td></tr>")
        parts.append("</table>")
    parts.append(f"<h2>Connectivity mismatches ({len(conn_mm)})</h2>")
    if conn_mm:
        parts.append("<table><tr><th>Config</th><th>Word</th><th>Components ref/new</th><th>Reference / New / Diff</th></tr>")
        for m in conn_mm[:200]:
            parts.append(f"<tr><td>{e(m['config'])}</td><td>{e(m['text'])}</td><td>{m['ref']} / {m['new']}</td>"
                         f"<td><img src='{m['img_ref']}'><br><img src='{m['img_new']}'><br><img src='{m['img_diff']}'></td></tr>")
        parts.append("</table>")
    parts.append(f"<h2>Largest glyph differences (top 40 of {len(glyph_rows)})</h2><table><tr><th>Glyph</th><th>Diff px</th><th>% of ink</th><th>Diff</th></tr>")
    for r in [r for r in glyph_rows if r["glyph"] not in (intentional or {})][:40]:
        ia, ib = r["_imgs"]
        parts.append(f"<tr><td>{e(r['glyph'])}</td><td>{r['diff_px']}</td><td>{r['ratio']:.2%}</td><td><img src='{png_b64(diff_img(ia, ib))}'></td></tr>")
    parts.append("</table>")
    if adv_diff:
        parts.append(f"<h2>Advance width differences ({len(adv_diff)})</h2><table>")
        for a in adv_diff[:200]:
            parts.append(f"<tr><td>{e(a['glyph'])}</td><td>{a['ref']}</td><td>{a['new']}</td></tr>")
        parts.append("</table>")
    if lookups[1] or lookups[2]:
        parts.append(f"<h2>GSUB lookups without exact match</h2><pre>{e(json.dumps({'missing_in_new': lookups[1], 'extra_in_new': lookups[2]}, indent=1))}</pre>")
    parts.append("</body></html>")
    (out / "index.html").write_text("\n".join(parts), encoding="utf-8")


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reference")
    ap.add_argument("new")
    ap.add_argument("--out", default=str(HERE / "report"))
    ap.add_argument("--thresholds", default=str(HERE / "thresholds.yaml"))
    a = ap.parse_args()
    th = yaml.safe_load(Path(a.thresholds).read_text())
    ref, new = Font(a.reference), Font(a.new)
    corpus = load_corpus()
    configs = feature_configs(ref)
    ppem = th["render_ppem"]

    n_shape, shaping_mm = check_shaping(ref, new, corpus, configs)
    print(f"shaping: {n_shape} runs, {len(shaping_mm)} mismatches", flush=True)
    n_conn, conn_mm, notdef = check_connectivity(ref, new, corpus, configs, ppem)
    print(f"connectivity: {n_conn} words, {len(conn_mm)} mismatches, {len(notdef)} with .notdef", flush=True)
    names, glyph_rows, adv_diff = check_glyphs(ref, new, ppem * 2, th["pixel_tolerance"])
    intentional = th.get("intentional_changes") or {}
    over = [r for r in glyph_rows if r["ratio"] > th["glyph_diff_ratio_max"] and r["glyph"] not in intentional]
    expected = [r for r in glyph_rows if r["glyph"] in intentional]
    print(f"glyphs: {len(names)} compared, {len(over)} over threshold, max ratio "
          f"{glyph_rows[0]['ratio'] if glyph_rows else 0:.4f}, {len(adv_diff)} advance diffs", flush=True)
    n_lk, lk_ref, lk_new = check_lookups(ref, new)
    print(f"lookups: {n_lk} flattened, {len(lk_ref)} missing in new, {len(lk_new)} extra in new", flush=True)

    reasons = []
    if len(shaping_mm) > th["max_shaping_mismatches"]:
        reasons.append(f"{len(shaping_mm)} shaping mismatches (allowed {th['max_shaping_mismatches']})")
    if len(conn_mm) > th["max_connectivity_mismatches"]:
        reasons.append(f"{len(conn_mm)} connectivity mismatches (allowed {th['max_connectivity_mismatches']})")
    if notdef:
        reasons.append(f"{len(notdef)} words render .notdef")
    if over:
        reasons.append(f"{len(over)} glyphs differ more than {th['glyph_diff_ratio_max']:.1%} of their ink")
    adv_diff = [d for d in adv_diff if d["glyph"] not in intentional]
    if len(adv_diff) > th["max_advance_mismatches"]:
        reasons.append(f"{len(adv_diff)} advance width differences")
    if lk_ref or lk_new:
        reasons.append(f"GSUB lookups differ: {len(lk_ref)} missing, {len(lk_new)} extra")
    verdict = {"pass": not reasons, "reasons": reasons or ["All checks within thresholds."]}

    summary = {
        "reference": a.reference, "new": a.new, "configs": list(configs),
        "shaping_tested": n_shape, "shaping_mismatches": len(shaping_mm),
        "connect_tested": n_conn, "connect_mismatches": len(conn_mm), "notdef": len(notdef),
        "glyphs_tested": len(names), "glyphs_over_threshold": len(over),
        "glyph_ratio_max": th["glyph_diff_ratio_max"],
        "glyph_worst": [{k: v for k, v in r.items() if k != "_imgs"} for r in glyph_rows[:20]],
        "advance_mismatches": len(adv_diff),
        "lookups_tested": n_lk, "lookups_unmatched_ref": len(lk_ref), "lookups_unmatched_new": len(lk_new),
        "verdict": verdict,
        "intentional_changes": intentional,
    }
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    (out / "shaping_mismatches.json").write_text(json.dumps(shaping_mm, indent=1))
    write_report(out, summary, shaping_mm, conn_mm, glyph_rows, adv_diff, (n_lk, lk_ref, lk_new), ref, new, ppem, verdict,
                 expected, intentional)
    print("VERDICT:", "PASS" if verdict["pass"] else "FAIL", "-", "; ".join(verdict["reasons"]))
    print("report:", out / "index.html")
    sys.exit(0 if verdict["pass"] else 1)


if __name__ == "__main__":
    main()
