"""Measure the new letters against the designer's own design principles.

The principles come from her documentation, "Typeface Features"
(https://cogncur.com/documentation/typeface-features, also in
upstream/documentation/typeface-features.html). Every measurement is taken on
the centre lines (UFO layer `skeleton`, slanted like the font) and is first
taken on her own letters, so a new letter is compared with what she drew, not
with an ideal number.

  1. slant      straight downstrokes lean 7.5° and are parallel
  2. loops      tall loops cross themselves on the waist line
  3. branching  arches and counters leave/join the stem halfway up the x-height
  4. origin     which stretches of a new letter are hers and which are new

Informational only: it never fails. The designer and the user decide.

    .venv/bin/python scripts/check_principles.py [--ufo …] [--ttf …] [--out tests/report]
    (make principles; needs make sources build)
"""
from __future__ import annotations

import argparse
import html
import math
from pathlib import Path

import numpy as np
import uharfbuzz as hb
import ufoLib2
from fontTools.pens.basePen import BasePen

ROOT = Path(__file__).resolve().parent.parent
DOC = "https://cogncur.com/documentation/typeface-features"

# Centre-line guides: the pen (68) is centred on the line, so ink from y=0 to
# 682 has its centre line from 34 to 648.
BASE, WAIST, ASC, DESC = 34, 648, 1330, -648
HALF = (BASE + WAIST) / 2
SLANT = 7.5

# new letter -> the letters it was built from (scripts/new_glyphs_ff.py), each with
# the vertical shift used there (unslanted units; Þ is P's bowl moved down 300)
NEW = {
    "thorn": [("b", 0), ("p", 0)],
    "eth": [("d", 0)],
    "Thorn": [("P", 0), ("P", -300)],
    "uni1E9E": [("B", 0)],
}
# loops only close in shaped text: the upstroke of b/h/l belongs to the connector
WORDS = [("ub", "uþ"), ("ud", "uð")]
# her letters that show each principle
REF_STEMS = ["b", "d", "h", "k", "l", "p", "q", "B", "P", "D", "E"]
REF_LOOPS = ["b", "h", "k", "l"]
REF_BRANCH = ["n", "m", "h", "p", "d", "a", "q", "g"]
SAME = 3.0  # a point within this many units of her centre line counts as hers


class FlatPen(BasePen):
    """Centre lines as polylines (curves cut into 16 straight pieces)."""

    def __init__(self):
        super().__init__(None)
        self.lines: list[list[tuple[float, float]]] = []

    def _moveTo(self, p):
        self.lines.append([p])

    def _lineTo(self, p):
        self.lines[-1].append(p)

    def _qCurveToOne(self, p1, p2):
        p0 = self.lines[-1][-1]
        for i in range(1, 17):
            t = i / 16
            self.lines[-1].append(tuple((1 - t) ** 2 * np.array(p0) + 2 * (1 - t) * t * np.array(p1)
                                        + t * t * np.array(p2)))

    def _curveToOne(self, p1, p2, p3):
        p0 = self.lines[-1][-1]
        for i in range(1, 17):
            t = i / 16
            a, b, c, d = map(np.array, (p0, p1, p2, p3))
            self.lines[-1].append(tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b
                                        + 3 * (1 - t) * t * t * c + t ** 3 * d))

    def _closePath(self):
        if self.lines[-1][0] != self.lines[-1][-1]:
            self.lines[-1].append(self.lines[-1][0])

    def _endPath(self):
        pass


def polylines(layer, name):
    pen = FlatPen()
    layer[name].draw(pen)
    return [np.array(l, dtype=float) for l in pen.lines if len(l) > 1]


def stems(lines, min_len=250):
    """Straight, near-vertical runs: (slant in degrees, bottom point, top point)."""
    out = []
    for pl in lines:
        d = np.diff(pl, axis=0)
        n = len(d)
        i = 0
        while i < n:
            if np.hypot(*d[i]) < 1e-6:
                i += 1
                continue
            a0 = math.atan2(d[i][1], d[i][0])
            j = i + 1
            while j < n and (np.hypot(*d[j]) < 1e-6 or abs(_wrap(math.atan2(d[j][1], d[j][0]) - a0)) < math.radians(0.5)):
                j += 1
            p, q = pl[i], pl[j]
            length = np.hypot(*(q - p))
            if length >= min_len:
                lo, hi = (p, q) if p[1] < q[1] else (q, p)
                slant = math.degrees(math.atan2(hi[0] - lo[0], hi[1] - lo[1]))
                if abs(slant) < 25:
                    out.append((slant, lo, hi))
            i = j
    return out


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def crossings(lines, min_angle=10):
    """Points where a centre line crosses itself or another (not where it retraces)."""
    segs = []
    for k, pl in enumerate(lines):
        closed = np.allclose(pl[0], pl[-1])
        for i in range(len(pl) - 1):
            segs.append((k, i, len(pl) - 1, closed, pl[i], pl[i + 1]))
    pts = []
    for a in range(len(segs)):
        ka, ia, na, ca, p, p2 = segs[a]
        r = p2 - p
        for b in range(a + 1, len(segs)):
            kb, ib, nb, cb, q, q2 = segs[b]
            if ka == kb and (abs(ia - ib) <= 1 or (ca and {ia, ib} == {0, na - 1})):
                continue
            s = q2 - q
            den = r[0] * s[1] - r[1] * s[0]
            if abs(den) < 1e-9:
                continue
            t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / den
            u = ((q[0] - p[0]) * r[1] - (q[1] - p[1]) * r[0]) / den
            if 1e-6 < t < 1 - 1e-6 and 1e-6 < u < 1 - 1e-6:
                ang = abs(math.degrees(_wrap(math.atan2(r[1], r[0]) - math.atan2(s[1], s[0]))))
                ang = min(ang, 180 - ang)
                if ang >= min_angle:
                    pts.append(p + t * r)
    uniq = []
    for c in pts:
        if all(np.hypot(*(c - o)) > 8 for o in uniq):
            uniq.append(c)
    return sorted(uniq, key=lambda c: -c[1])


def _dist_to_segment(pts, a, b):
    ab = b - a
    t = np.clip(((pts - a) @ ab) / (ab @ ab), 0, 1)
    return np.hypot(*(pts - (a + t[:, None] * ab)).T)


def branch_points(lines, tol=4.0):
    """Heights inside the x-height where the line leaves or joins the main stem."""
    st = stems(lines)
    if not st:
        return []
    _, lo, hi = max(st, key=lambda s: np.hypot(*(s[2] - s[1])))
    ys = []
    for pl in lines:
        on = _dist_to_segment(pl, lo, hi) < tol
        for i in range(1, len(pl)):
            if on[i] != on[i - 1]:
                y = pl[i - 1][1] if on[i - 1] else pl[i][1]
                if BASE + 40 < y < WAIST - 40 and all(abs(y - o) > 10 for o in ys):
                    ys.append(float(y))
    return sorted(ys)


def resample(pl, step=4.0):
    out = [pl[0]]
    for a, b in zip(pl[:-1], pl[1:]):
        n = max(1, int(np.hypot(*(b - a)) // step))
        out.extend(a + (b - a) * (i / n) for i in range(1, n + 1))
    return np.array(out)


def origin(new_lines, src_lines):
    """Per sample point of the new letter: distance to the nearest of her centre lines."""
    segs = [(a, b) for pl in src_lines for a, b in zip(pl[:-1], pl[1:])]
    A = np.array([s[0] for s in segs])
    B = np.array([s[1] for s in segs])
    AB = B - A
    L2 = np.maximum((AB ** 2).sum(1), 1e-9)
    res = []
    for pl in new_lines:
        pts = resample(pl)
        d = np.empty(len(pts))
        for i, p in enumerate(pts):
            t = np.clip(((p - A) * AB).sum(1) / L2, 0, 1)
            d[i] = np.hypot(*(p - (A + t[:, None] * AB)).T).min()
        res.append((pts, d))
    return res


def new_stretches(res, min_len=20, gap=24):
    """Stretches (length, from point, to point) that are not on her centre lines.
    A run of 'hers' shorter than `gap` inside a new stretch (a new line merely
    crossing one of hers) does not split it."""
    out = []
    for pts, d in res:
        new = d > SAME
        i = 0
        while i < len(new):
            if not new[i]:
                j = i
                while j + 1 < len(new) and not new[j + 1]:
                    j += 1
                if i > 0 and j + 1 < len(new) and (j - i + 1) * 4.0 < gap:
                    new[i:j + 1] = True
                i = j + 1
            else:
                i += 1
        i = 0
        while i < len(pts):
            if new[i]:
                j = i
                while j + 1 < len(pts) and new[j + 1]:
                    j += 1
                length = float(np.sum(np.hypot(*np.diff(pts[i:j + 1], axis=0).T))) if j > i else 0.0
                if length >= min_len:
                    out.append((length, pts[i], pts[j]))
                i = j + 1
            else:
                i += 1
    return out


# ---------------------------------------------------------------- report

def fmt_pt(p):
    return f"({p[0]:.0f}, {p[1]:.0f})"


def frac(y):
    return (y - BASE) / (WAIST - BASE)


def shaped(sk, ttf, text):
    """Centre lines of a shaped word: (glyph names, polylines placed like HarfBuzz places them)."""
    font = hb.Font(hb.Face(hb.Blob.from_file_path(ttf)))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    x, names, lines = 0, [], []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = font.glyph_to_string(info.codepoint)
        names.append(name)
        if name in sk:
            lines += [pl + (x + pos.x_offset, pos.y_offset) for pl in polylines(sk, name)]
        x += pos.x_advance
    return names, lines


def shift(lines, dy):
    """Move centre lines vertically by dy unslanted units (so along the slant)."""
    return [pl + (dy * math.tan(math.radians(SLANT)), dy) for pl in lines]


def measure(sk, ttf):
    data = {}
    for name in sorted(set(REF_STEMS + REF_LOOPS + REF_BRANCH + list(NEW) + [s for v in NEW.values() for s, _ in v])):
        if name in sk:
            lines = polylines(sk, name)
            data[name] = {"lines": lines, "stems": stems(lines), "cross": crossings(lines),
                          "branch": branch_points(lines)}
    for pair in WORDS:
        for text in pair:
            names, lines = shaped(sk, ttf, text)
            # only crossings the last letter adds: drop those the word without it already has
            before = crossings(shaped(sk, ttf, text[:-1])[1]) if len(text) > 1 else []
            data["word:" + text] = {"lines": lines, "stems": [], "branch": [], "glyphs": names,
                                    "cross": [c for c in crossings(lines) if c[1] > BASE + 40
                                              and all(np.hypot(*(c - b)) > 8 for b in before)]}
    return data


def markdown(data, sk):
    md = [f"# The new letters against the designer's principles\n",
          f"Source: [Typeface Features]({DOC}). Centre lines (UFO layer `skeleton`), font units, "
          f"slanted like the font. Guides on the centre line: baseline {BASE}, waist line {WAIST}, "
          f"halfway {HALF:.0f}, ascender {ASC}, descender {DESC}. Generated by `scripts/check_principles.py`.\n"]

    md.append("## 1. Slant: straight downstrokes lean 7.5° and are parallel\n")
    md.append("| letter | straight downstrokes (slant, from y to y) |\n|---|---|")
    for n in REF_STEMS + list(NEW):
        if n in data:
            s = ", ".join(f"{a:.2f}° ({lo[1]:.0f}→{hi[1]:.0f})" for a, lo, hi in data[n]["stems"]) or "–"
            md.append(f"| {'**' + n + '** (new)' if n in NEW else n} | {s} |")

    md.append("\n## 2. Loops: tall loops cross themselves on the waist line\n")
    md.append(f"The upstroke of b, h, l belongs to the connector, so the loop only closes in a word. "
              f"Crossings the last letter adds, above the baseline, in shaped text (waist line = y {WAIST}).\n")
    md.append("| text | glyphs | crossings (x, y) |\n|---|---|---|")
    for pair in WORDS:
        for i, text in enumerate(pair):
            w = data["word:" + text]
            c = ", ".join(fmt_pt(p) for p in w["cross"]) or "**none**"
            label = f"**{text}** (new)" if i else text
            md.append(f"| {label} | {' '.join(w['glyphs'])} | {c} |")

    md.append("\n## 3. Branching: arches and counters leave or join the stem halfway up\n")
    md.append(f"Heights where the line leaves or joins the main stem inside the x-height "
              f"(as a fraction of the x-height; halfway = 0.50). Measured where the line is 4 units off the "
              f"stem, so a curve that leaves the stem reads a little above its true branch point and one "
              f"that joins it a little below: compare with her letters, not with 0.50.\n")
    md.append("| letter | branch points |\n|---|---|")
    for n in REF_BRANCH + ["thorn", "eth"]:
        if n in data:
            b = ", ".join(f"y {y:.0f} = {frac(y):.2f}" for y in data[n]["branch"]) or "–"
            md.append(f"| {'**' + n + '** (new)' if n in NEW else n} | {b} |")

    md.append("\n## 4. Origin: what is hers and what is new\n")
    md.append(f"A point counts as hers when it lies within {SAME:.0f} units of one of her centre lines "
              f"in the letters it was built from.\n")
    md.append("| new letter | built from | hers | new stretches (length: from → to) |\n|---|---|---|---|")
    for n, srcs in NEW.items():
        if n not in data:
            continue
        src_lines = [pl for s, dy in srcs for pl in shift(data[s]["lines"], dy)]
        res = origin(data[n]["lines"], src_lines)
        total = sum(float(np.sum(np.hypot(*np.diff(p, axis=0).T))) for p, _ in res)
        mine = sum(float(np.sum(np.hypot(*np.diff(p, axis=0).T)[d[1:] <= SAME])) for p, d in res)
        st = "; ".join(f"{l:.0f}: {fmt_pt(a)} → {fmt_pt(b)}" for l, a, b in new_stretches(res))
        md.append(f"| **{n}** | {', '.join(s + (f' moved {dy}' if dy else '') for s, dy in srcs)} | {100 * mine / total:.0f}% | {st or '–'} |")
        data[n]["origin"] = res
    return "\n".join(md) + "\n"


def svg(data, name, colour_new=False, size=260):
    lines = data[name]["lines"]
    xs = [0, max(float(np.max(pl[:, 0])) for pl in lines) + 60]
    vb = f"{xs[0] - 80} {-ASC - 120} {xs[1] - xs[0] + 160} {ASC - DESC + 240}"
    out = [f'<svg viewBox="{vb}" width="{size}" xmlns="http://www.w3.org/2000/svg">',
           '<g transform="scale(1,-1)" fill="none" stroke-linecap="round" stroke-linejoin="round">']
    for y, c in [(BASE, "#bbb"), (WAIST, "#bbb"), (HALF, "#9cf"), (ASC, "#ddd"), (DESC, "#ddd")]:
        dash = ' stroke-dasharray="12 10"' if y == HALF else ""
        out.append(f'<line x1="{xs[0] - 80}" x2="{xs[1] + 80}" y1="{y}" y2="{y}" stroke="{c}" stroke-width="4"{dash}/>')
    if colour_new and "origin" in data[name]:
        for pts, d in data[name]["origin"]:
            for a, b, dd in zip(pts[:-1], pts[1:], d[1:]):
                col = "#e4572e" if dd > SAME else "#444"
                out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{col}" stroke-width="14"/>')
    else:
        for pl in lines:
            pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in pl)
            out.append(f'<polyline points="{pts}" stroke="#444" stroke-width="14"/>')
    for _, lo, hi in data[name]["stems"]:
        k = 300 / max(hi[1] - lo[1], 1)
        a, b = lo - (hi - lo) * k, hi + (hi - lo) * k
        out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="#2a9d8f" stroke-width="3" stroke-dasharray="6 8"/>')
    for p in data[name]["cross"]:
        out.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="22" stroke="#d62828" stroke-width="6"/>')
    for y in data[name]["branch"]:
        out.append(f'<line x1="{xs[0] - 80}" x2="{xs[0] - 20}" y1="{y:.1f}" y2="{y:.1f}" stroke="#1d4ed8" stroke-width="10"/>')
    out.append("</g></svg>")
    return "".join(out)


def report_html(md, data):
    cards = []
    for n, srcs in NEW.items():
        if n not in data:
            continue
        figs = [f'<figure>{svg(data, n, colour_new=True)}<figcaption><b>{n}</b> (new)</figcaption></figure>']
        figs += [f'<figure>{svg(data, s)}<figcaption>{s} (hers)</figcaption></figure>'
                 for s in dict.fromkeys(s for s, _ in srcs)]
        cards.append(f'<section><h3>{n}</h3><div class="row">{"".join(figs)}</div></section>')
    words = "".join(f'<figure>{svg(data, "word:" + t, size=300)}<figcaption>{html.escape(t)}: '
                    f'{html.escape(" ".join(data["word:" + t]["glyphs"]))}</figcaption></figure>'
                    for pair in WORDS for t in pair)
    refs = "".join(f'<figure>{svg(data, s, size=180)}<figcaption>{s}</figcaption></figure>'
                   for s in REF_LOOPS + ["n", "a", "q"] if s in data)
    return f"""<!doctype html><meta charset="utf-8"><title>Principles check</title>
<style>body{{font:15px system-ui;margin:24px;max-width:1100px}}.row{{display:flex;flex-wrap:wrap;gap:12px}}
figure{{margin:0;text-align:center}}pre{{white-space:pre-wrap;background:#f6f6f6;padding:12px}}
.key span{{display:inline-block;margin-right:16px}}</style>
<h1>The new letters against the designer's principles</h1>
<p>Source: <a href="{DOC}">Typeface Features</a>. Centre lines from the UFO layer <code>skeleton</code>.</p>
<p class="key"><span style="color:#e4572e">■ new stretch</span><span style="color:#444">■ hers</span>
<span style="color:#2a9d8f">┅ straight downstroke, extended</span><span style="color:#d62828">○ crossing</span>
<span style="color:#1d4ed8">▬ branch point</span><span style="color:#9cf">┅ halfway</span></p>
{''.join(cards)}<h2>Loops in words (connector + letter)</h2><div class="row">{words}</div>
<h2>Her letters, for comparison</h2><div class="row">{refs}</div>
<h2>Numbers</h2><pre>{html.escape(md)}</pre>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ufo", default=str(ROOT / "sources/Cogncur-Regular.ufo"))
    ap.add_argument("--ttf", default=str(ROOT / "fonts/ttf/Cogncur-Regular.ttf"))
    ap.add_argument("--out", default=str(ROOT / "tests/report"))
    a = ap.parse_args()
    sk = ufoLib2.Font.open(a.ufo).layers["skeleton"]
    data = measure(sk, a.ttf)
    md = markdown(data, sk)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "principles.md").write_text(md, encoding="utf-8")
    (out / "principles.html").write_text(report_html(md, data), encoding="utf-8")
    print(md)
    print(f"→ {out / 'principles.html'}")


if __name__ == "__main__":
    main()
