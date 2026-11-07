"""Draft pen routes for every glyph: build/routes.json + tests/report/routes.html.

A route says how a pen writes a glyph: which centre-line pieces, in which order and direction,
and where the pen is lifted. Centre lines come from the `skeleton` layer of the generated UFO,
filled shapes (dots, commas) from `extra`. Neither layer stores an order, so this script drafts one:

1. Keep only contours the real ink covers (both layers hold leftovers that never reach the font).
   Closed skeleton contours that trace an ink edge are filled shapes, not centre lines.
2. Cut centre lines where one line ends on another (the bowl of `a` ends on its stem). The cut
   pieces are the steps a route is made of; a piece can be walked twice (retracing).
3. Order: letters are matched to upstream's stroke-order model (webapps/imgen/cogncur_shapes.svg)
   and follow its order, direction and pen lifts. Connectors (cc*, cg*, ce*, cf*) start at their
   leftmost end. Whatever is left gets a depth-first walk and status "review".
4. Composites (accented letters built from components) chain their components' routes.

Checks: the pieces drawn with the round 68-unit pen must cover the glyph's ink, and in every
shaped corpus line each connector must start where the previous glyph's route ends and end where
the next glyph's route starts. Manual corrections will live in sources/routes.json (phase 3).
"""
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
import ufoLib2
import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.pens.freetypePen import FreeTypePen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
UFO = ROOT / "sources/Vtex-Regular.ufo"
TTF = ROOT / "fonts/ttf/Vtex-Regular.ttf"
SHAPES = ROOT / "upstream/webapps/imgen/cogncur_shapes.svg"
CORPUS = ROOT / "tests/corpus"
OUT_JSON = ROOT / "build/routes.json"
OUT_HTML = ROOT / "tests/report/routes.html"

PEN = 68
SLANT = math.tan(math.radians(7.5))
STEP = 4.0                   # sampling distance along curves (font units)
JOIN_TOL = 6.0               # an endpoint this close to another line is a junction
NODE_TOL = 3.0               # endpoints closer than this are the same node
GAP_TOL = 20.0               # word check: allowed gap between consecutive routes (pen radius is 34)
SCALE = 0.25                 # raster scale for ink tests (4 units per pixel)
OX, OY, RW, RH = 1200, 1000, 4400, 3400   # raster window in font units


# ------------------------------------------------------------------ curves
def bez(p, t):
    pts = list(p)
    while len(pts) > 1:
        pts = [((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1]) for a, b in zip(pts, pts[1:])]
    return pts[0]


def bez_split(p, t):
    left, right, pts = [p[0]], [p[-1]], list(p)
    while len(pts) > 1:
        pts = [((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1]) for a, b in zip(pts, pts[1:])]
        left.append(pts[0])
        right.append(pts[-1])
    return left, right[::-1]


def seg_len(p):
    q = [bez(p, i / 8) for i in range(9)]
    return sum(math.dist(a, b) for a, b in zip(q, q[1:]))


class SegPen(BasePen):
    """Collects contours as lists of Bézier segments (2, 3 or 4 points each)."""

    def __init__(self):
        super().__init__(None)
        self.contours, self.cur, self.last = [], None, None

    def _moveTo(self, p):
        self.cur, self.last = {"segs": [], "start": p, "closed": False}, p

    def _lineTo(self, p):
        if p != self.last:
            self.cur["segs"].append([self.last, p])
        self.last = p

    def _qCurveToOne(self, c, p):
        self.cur["segs"].append([self.last, c, p])
        self.last = p

    def _curveToOne(self, c1, c2, p):
        self.cur["segs"].append([self.last, c1, c2, p])
        self.last = p

    def _closePath(self):
        if self.last != self.cur["start"]:
            self.cur["segs"].append([self.last, self.cur["start"]])
        self.cur["closed"] = True
        self._flush()

    def _endPath(self):
        self._flush()

    def _flush(self):
        if self.cur is not None:
            self.contours.append(self.cur)
        self.cur = None


def contours_of(drawable):
    pen = SegPen()
    drawable.draw(pen)
    return pen.contours


def sample(segs, step=STEP):
    """[(seg_index, t, x, y, s)] along a list of segments, s = arc length."""
    out, s, prev = [], 0.0, None
    for i, p in enumerate(segs):
        n = max(2, math.ceil(seg_len(p) / step))
        for k in range(n + 1):
            if k == 0 and out:
                continue
            x, y = bez(p, k / n)
            if prev is not None:
                s += math.dist(prev, (x, y))
            out.append((i, k / n, x, y, s))
            prev = (x, y)
    return out


def nearest_param(segs, pt, samples):
    """Closest (seg_index, t, distance) on segs to pt, refined from the samples."""
    arr = np.array([(x, y) for _, _, x, y, _ in samples])
    k = int(np.argmin(((arr - pt) ** 2).sum(1)))
    i, t = samples[k][0], samples[k][1]
    lo, hi = max(0.0, t - 0.15), min(1.0, t + 0.15)
    for _ in range(40):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if math.dist(bez(segs[i], m1), pt) < math.dist(bez(segs[i], m2), pt):
            hi = m2
        else:
            lo = m1
    t = (lo + hi) / 2
    return i, t, math.dist(bez(segs[i], t), pt)


def cut_open(segs, points):
    """Cut an open run of segments at the given points (each on the curve)."""
    pieces, cur = [], []
    smp = sample(segs)
    cuts = sorted({(i, round(t, 6)) for i, t, _ in (nearest_param(segs, p, smp) for p in points)})
    cuts_by_seg = defaultdict(list)
    for i, t in cuts:
        cuts_by_seg[i].append(t)
    for i, p in enumerate(segs):
        rest, t0 = p, 0.0
        for t in sorted(cuts_by_seg.get(i, [])):
            tt = (t - t0) / (1 - t0) if t0 < 1 else 0
            if tt <= 1e-4:
                if cur:
                    pieces.append(cur)
                cur = []
                continue
            if tt >= 1 - 1e-4:
                continue
            a, rest = bez_split(rest, tt)
            cur.append(a)
            pieces.append(cur)
            cur, t0 = [], t
        cur.append(rest)
    if cur:
        pieces.append(cur)
    return [pc for pc in pieces if sum(seg_len(s) for s in pc) > 1.0]


def rotate_closed(segs, pt):
    """Open a closed contour at pt: returns segments starting and ending there."""
    i, t, _ = nearest_param(segs, pt, sample(segs))
    a, b = bez_split(segs[i], t)
    return [b] + segs[i + 1:] + segs[:i] + [a]


def piece_len(pc):
    return sum(seg_len(s) for s in pc)


def reverse_piece(pc):
    return [list(reversed(s)) for s in reversed(pc)]


def transform_piece(pc, m):
    a, b, c, d, e, f = m
    return [[(a * x + c * y + e, b * x + d * y + f) for x, y in s] for s in pc]


# ------------------------------------------------------------------ raster
def raster(draw, glyphset=None):
    pen = FreeTypePen(glyphset)
    m = (SCALE, 0, 0, SCALE, OX * SCALE, OY * SCALE)
    draw(TransformPen(pen, m))
    a = pen.array(width=int(RW * SCALE), height=int(RH * SCALE), contain=False) > 0.5
    return a[::-1]           # row index = y up


def px(x, y):
    return int(round((x + OX) * SCALE)), int(round((y + OY) * SCALE))


def inside(mask, x, y):
    c, r = px(x, y)
    return 0 <= r < mask.shape[0] and 0 <= c < mask.shape[1] and mask[r, c]


def dilate(mask, n):
    out = mask.copy()
    for _ in range(n):
        o = out.copy()
        o[1:] |= out[:-1]; o[:-1] |= out[1:]; o[:, 1:] |= out[:, :-1]; o[:, :-1] |= out[:, 1:]
        out = o
    return out


DISC = [(dr, dc) for dr in range(-10, 11) for dc in range(-10, 11)
        if (dr * dr + dc * dc) ** 0.5 <= PEN / 2 * SCALE + 0.75]


def stamp(mask, pts):
    for x, y in pts:
        c, r = px(x, y)
        for dr, dc in DISC:
            rr, cc = r + dr, c + dc
            if 0 <= rr < mask.shape[0] and 0 <= cc < mask.shape[1]:
                mask[rr, cc] = True


# ------------------------------------------------------------------ upstream stroke model
def load_shapes():
    import xml.etree.ElementTree as ET
    ns = "{http://www.w3.org/2000/svg}"
    root = ET.parse(SHAPES).getroot()
    shapes = {}
    for g in root.iter(f"{ns}g"):
        gid = g.get("id", "")
        if not gid.startswith("letter-") or gid[7:] in shapes or gid == "letter-empty":
            continue
        strokes = []
        sg = g.find(f"{ns}g[@class='strokes']")
        for p in (sg.findall(f"{ns}path") if sg is not None else []):
            if not p.get("id", "").startswith("stroke") or p.get("class") == "overlap":
                continue
            pen = SegPen()
            parse_path(p.get("d"), pen)
            segs = [s for c in pen.contours for s in c["segs"]]
            if not segs:
                continue
            strokes.append({"segs": segs, "entry": p.get("data-entry") is not None,
                            "lift": p.get("data-lift") is not None, "dot": p.get("data-dot") is not None})
        shapes[gid[7:]] = strokes
    return shapes


def shape_base(sid):
    return re.sub(r"(-alt\d+)?(-noentry)?$", "", sid)


# ------------------------------------------------------------------ per-glyph geometry
class GlyphGeo:
    def __init__(self, name):
        self.name = name
        self.pieces = []      # list of segment lists (open; a loop starts and ends at the same point)
        self.fills = []       # closed filled shapes (dots, commas): list of segment lists
        self.notes = []
        self.junk = 0


def ink_mask(glyphset, name):
    return raster(lambda pen: glyphset[name].draw(pen), glyphset)


def classify(name, skel, extra, ink):
    """Split a glyph's layer contours into centre lines, filled shapes and leftovers."""
    deep_off = [(0, 0), (20, 0), (-20, 0), (0, 20), (0, -20)]
    near = dilate(ink, 2)
    lines, fills, junk = [], [], 0
    for c in skel:
        smp = sample(c["segs"], 8)
        if not smp:
            continue
        deep = np.mean([all(inside(ink, x + dx, y + dy) for dx, dy in deep_off) for _, _, x, y, _ in smp])
        onink = np.mean([inside(near, x, y) for _, _, x, y, _ in smp])
        if deep >= 0.85:
            lines.append(c)
        elif c["closed"] and onink >= 0.9:
            fills.append(c["segs"])
        else:
            junk += 1
    for c in extra:
        smp = sample(c["segs"], 8)
        if smp and np.mean([inside(near, x, y) for _, _, x, y, _ in smp]) >= 0.9:
            fills.append(c["segs"])
        else:
            junk += 1
    return lines, fills, junk


def build_pieces(lines, markers):
    """Cut centre lines at junctions; loops are opened at a junction, a marker or their start."""
    smps = [sample(c["segs"]) for c in lines]
    ends = [pt for c in lines if not c["closed"] for pt in (c["segs"][0][0], c["segs"][-1][-1])]
    pieces = []
    for ci, c in enumerate(lines):
        cuts = []
        arr = np.array([(x, y) for _, _, x, y, _ in smps[ci]])
        total = smps[ci][-1][4]
        for e in ends + markers:
            d = np.sqrt(((arr - e) ** 2).sum(1))
            k = int(np.argmin(d))
            if d[k] > JOIN_TOL:
                continue
            s = smps[ci][k][4]
            if not c["closed"] and (s < 12 or s > total - 12):
                continue                                  # touches an end: already a node
            cuts.append((s, (smps[ci][k][2], smps[ci][k][3])))
        cuts.sort()
        pts = []
        for s, p in cuts:
            if not pts or s - pts[-1][0] > 8:
                pts.append((s, p))
        if c["closed"]:
            start = pts[0][1] if pts else c["segs"][0][0]
            segs = rotate_closed(c["segs"], start)
            pieces += cut_open(segs, [p for _, p in pts[1:]]) if len(pts) > 1 else [segs]
        else:
            pieces += cut_open(c["segs"], [p for _, p in pts])
    return pieces


# ------------------------------------------------------------------ routing
def piece_samples(pieces):
    out = []
    for pi, pc in enumerate(pieces):
        for _, _, x, y, s in sample(pc):
            out.append((pi, s, x, y))
    return out


def match_shape(geo, strokes, use_entry):
    """Fit one upstream shape onto the glyph's pieces; returns (score, dx, mapped strokes) or None."""
    S = [s for s in strokes if (use_entry or not s["entry"]) and not s["dot"]]
    if not S or not geo.pieces:
        return None
    G = piece_samples(geo.pieces)
    g = np.array([(x, y) for _, _, x, y in G])
    shp = [np.array([(x + SLANT * y, y) for _, _, x, y, _ in sample(st["segs"], 6)]) for st in S]
    allp = np.vstack(shp)

    def fit(dx, sub=1):
        q = allp[::sub] + (dx, 0)
        d = np.sqrt(((q[:, None, :] - g[None, ::sub, :]) ** 2).sum(2))
        return float(np.median(d.min(1)))

    gx = g[:, 0].mean() - allp[:, 0].mean()
    coarse = min(range(int(gx) - 260, int(gx) + 261, 8), key=lambda dx: fit(dx, 3))
    dx = min(range(coarse - 8, coarse + 9), key=lambda v: fit(v, 2))
    med = fit(dx)
    q = allp + (dx, 0)
    d = np.sqrt(((g[:, None, :] - q[None, :, :]) ** 2).sum(2))
    gcov = float((d.min(1) < 25).mean())
    return med - 40 * gcov, dx, med, gcov


def route_from_shape(geo, strokes, use_entry, dx):
    """Translate an upstream stroke list into runs of piece steps."""
    G = piece_samples(geo.pieces)
    g = np.array([(x, y) for _, _, x, y in G])
    lens = [piece_len(pc) for pc in geo.pieces]
    runs, cur = [], []
    used_fill = set()
    loops = [math.dist(*ends(pc)) <= NODE_TOL for pc in geo.pieces]
    for st in strokes:
        # entry strokes are mapped too: upstream folds e.g. the first leg of m into the entry stroke;
        # the part that belongs to the connector glyph simply finds no piece nearby
        if st["dot"]:
            x, y = st["segs"][0][0]
            p = (x + SLANT * y + dx, y)
            k = nearest_fill(geo, p, used_fill)
            if k is not None:
                if cur:
                    runs.append(cur)
                runs.append([{"f": k}])
                used_fill.add(k)
                cur = []
            continue
        if st["lift"] and cur:
            runs.append(cur)
            cur = []
        pts = [(x + SLANT * y + dx, y) for _, _, x, y, _ in sample(st["segs"], 6)]
        seq, prev = [], None
        for p in pts:
            d = np.sqrt(((g - p) ** 2).sum(1))
            cand = np.nonzero(d < 25)[0]
            if not len(cand):
                continue
            k = int(cand[np.argmin(d[cand])])
            if prev is not None:
                # stay on the line we are following (crossings, retraced stems)
                same = [c for c in cand if G[c][0] == prev[0] and abs(G[c][1] - prev[1]) < 30]
                if same:
                    k = min(same, key=lambda c: d[c])
            prev = (G[k][0], G[k][1])
            seq.append(prev)
        # split into monotone stretches on one piece
        stretches = []
        for pi, s in seq:
            if stretches and stretches[-1]["p"] == pi:
                stc = stretches[-1]
                if loops[pi]:                                  # unwrap positions on a loop
                    while s - stc["s1"] > lens[pi] / 2:
                        s -= lens[pi]
                    while s - stc["s1"] < -lens[pi] / 2:
                        s += lens[pi]

                if stc["dir"] == 0 and abs(s - stc["s1"]) > 4:
                    stc["dir"] = 1 if s > stc["s1"] else -1
                if stc["dir"] and (s - stc["s1"]) * stc["dir"] < -15:      # reversal on the same piece
                    stretches.append({"p": pi, "s0": stc["s1"], "s1": s, "dir": -stc["dir"]})
                    continue
                if stc["dir"] == 0 or (s - stc["s1"]) * stc["dir"] >= 0:
                    stc["s1"] = s
            else:
                stretches.append({"p": pi, "s0": s, "s1": s, "dir": 0})
        for stc in stretches:
            covered = abs(stc["s1"] - stc["s0"])
            L = lens[stc["p"]]
            if covered < min(0.5 * L, 60) or stc["dir"] == 0:
                continue
            step = {"p": stc["p"], "r": 1 if stc["dir"] < 0 else 0, "entry": st["entry"]}
            if cur and (cur[-1]["p"], cur[-1]["r"]) == (step["p"], step["r"]):
                continue
            cur.append(step)
    if cur:
        runs.append(cur)
    # an entry stroke only counts where no other stroke draws the same piece in the same direction
    # (the first leg of m); elsewhere it merely runs alongside the letter's own lines. The direction
    # matters: upstream's n puts "down the stem" in the entry stroke and "back up" in the next one.
    # Running the other way, it is only dropped where that keeps the line unbroken.
    own = {(s["p"], s["r"]) for r in runs for s in r if "p" in s and not s["entry"]}
    own_p = {p for p, _ in own}
    out = []
    for r in runs:
        kept = []
        for j, s in enumerate(r):
            if "p" in s:
                if s.pop("entry") and s["p"] in own_p:
                    if (s["p"], s["r"]) in own:
                        continue
                    prev = kept[-1] if kept and "p" in kept[-1] else None
                    nxt = next((t for t in r[j + 1:] if "p" in t), None)
                    if (prev is None or nxt is None
                            or math.dist(step_ends(geo, prev)[1], step_ends(geo, nxt)[0]) <= GAP_TOL):
                        continue
                if kept and "p" in kept[-1] and (kept[-1]["p"], kept[-1]["r"]) == (s["p"], s["r"]):
                    continue
            kept.append(s)
        # there-back-there on one piece is a mapping artefact (a nearby return stroke), never intended
        i = 0
        while i + 2 < len(kept):
            a, b, c = kept[i:i + 3]
            if "p" in a and "p" in b and "p" in c and a["p"] == b["p"] == c["p"] and a["r"] == c["r"] != b["r"]:
                del kept[i + 1:i + 3]
            else:
                i += 1
        if kept:
            out.append(kept)
    return out


def nearest_fill(geo, p, used):
    best, bd = None, 120.0
    for k, f in enumerate(geo.fills):
        if k in used:
            continue
        pts = [q for s in f for q in s]
        cx, cy = np.mean([q[0] for q in pts]), np.mean([q[1] for q in pts])
        d = math.dist((cx, cy), p)
        if d < bd:
            best, bd = k, d
    return best


def ends(pc):
    return pc[0][0], pc[-1][-1]


def step_ends(geo, st):
    if "f" in st:
        pts = [q for s in geo.fills[st["f"]] for q in s]
        c = (float(np.mean([q[0] for q in pts])), float(np.mean([q[1] for q in pts])))
        return c, c
    a, b = ends(geo.pieces[st["p"]])
    return (b, a) if st["r"] else (a, b)


def dfs_runs(geo, todo, start=None):
    """Cover the pieces in `todo` with pen-down walks (retracing where needed)."""
    nodes = []

    def node(p):
        for i, q in enumerate(nodes):
            if math.dist(p, q) <= NODE_TOL:
                return i
        nodes.append(p)
        return len(nodes) - 1

    adj = defaultdict(list)
    for pi in todo:
        a, b = ends(geo.pieces[pi])
        na, nb = node(a), node(b)
        adj[na].append((pi, 0, nb))
        adj[nb].append((pi, 1, na))
    left, runs = set(todo), []
    while left:
        cand = {n for pi in left for n in (node(ends(geo.pieces[pi])[0]), node(ends(geo.pieces[pi])[1]))}
        if start is not None and not runs:
            cur = min(cand, key=lambda n: math.dist(nodes[n], start))
        else:
            odd = [n for n in cand if sum(1 for pi, _, _ in adj[n] if pi in left) % 2]
            cur = min(odd or cand, key=lambda n: (nodes[n][0], nodes[n][1]))
        run, stack, heading = [], [], None
        while True:
            opts = [(pi, r, nb) for pi, r, nb in adj[cur] if pi in left]
            if opts:
                def turn(o):
                    pc = geo.pieces[o[0]] if not o[1] else reverse_piece(geo.pieces[o[0]])
                    p0, p1 = pc[0][0], bez(pc[0], 0.2)
                    v = (p1[0] - p0[0], p1[1] - p0[1])
                    if heading is None:
                        return 0
                    n = math.hypot(*v) or 1
                    return -(v[0] * heading[0] + v[1] * heading[1]) / n
                pi, r, nb = min(opts, key=turn)
                left.discard(pi)
                run.append({"p": pi, "r": r})
                stack.append((pi, r, cur))
                pc = geo.pieces[pi] if not r else reverse_piece(geo.pieces[pi])
                a, b = bez(pc[-1], 0.8), pc[-1][-1]
                h = math.hypot(b[0] - a[0], b[1] - a[1]) or 1
                heading = ((b[0] - a[0]) / h, (b[1] - a[1]) / h)
                cur = nb
            elif stack and connected_left(adj, stack, left):
                pi, r, prev = stack.pop()
                run.append({"p": pi, "r": 1 - r})                     # retrace back along the line
                cur, heading = prev, None
            else:
                break
        runs.append(run)
    return runs


def connected_left(adj, stack, left):
    """True when an unvisited piece is reachable from a node on the current stack."""
    seen = {n for _, _, n in stack}
    frontier = list(seen)
    while frontier:
        n = frontier.pop()
        for pi, _, nb in adj[n]:
            if pi in left:
                return True
            if nb not in seen:
                seen.add(nb)
                frontier.append(nb)
    return False


def route_glyph(name, geo, shapes, cats):
    """Return (runs, source)."""
    if not geo.pieces and not geo.fills:
        return [], "empty"
    if cats == "connector":
        runs = dfs_runs(geo, list(range(len(geo.pieces))))
        return runs + [[{"f": k}] for k in range(len(geo.fills))], "connector"
    base = base_letter(name)
    best = None
    for sid, strokes in shapes.items():
        if shape_base(sid) != base:
            continue
        for use_entry in ((False, True) if name.startswith("cs") else (False,)):
            m = match_shape(geo, strokes, use_entry)
            if m and (best is None or m[0] < best[0]):
                best = (m[0], sid, use_entry, m[1], m[2], m[3])
    runs, source = [], "heuristic"
    if best and best[4] < 15 and best[5] > 0.5:
        _, sid, use_entry, dx, med, gcov = best
        runs = route_from_shape(geo, shapes[sid], use_entry, dx)
        source = f"shape:{sid}" + ("+entry" if use_entry else "")
    elif best:
        geo.notes.append(f"best stroke model {best[1]} fits poorly (median {best[4]:.0f}, cover {best[5]:.0%})")
    covered = {s["p"] for r in runs for s in r if "p" in s}
    rest = [pi for pi in range(len(geo.pieces)) if pi not in covered]
    if rest:
        start = step_ends(geo, runs[-1][-1])[1] if runs else None
        extra = dfs_runs(geo, rest, start)
        if runs:
            nodes_done = [p for pi in covered for p in ends(geo.pieces[pi])]
            touching = any(math.dist(p, q) <= NODE_TOL for pi in rest for p in ends(geo.pieces[pi]) for q in nodes_done)
            if touching:
                geo.notes.append(f"{len(rest)} piece(s) not in the stroke model; walked automatically")
            else:
                geo.notes.append(f"{len(rest)} separate piece(s) not in the stroke model (e.g. an accent), "
                                 "added after the letter; direction guessed")
        runs += extra
    used = {s["f"] for r in runs for s in r if "f" in s}
    runs += [[{"f": k}] for k in range(len(geo.fills)) if k not in used]
    return [r for r in runs if r], source


def base_letter(name):
    m = re.match(r"cs[a-z]+_(.+)$", name)
    if m:
        name = m.group(1)
    name = name.split(".")[0]
    return LETTER_OF.get(name) or re.sub(r"\d+$", "", name)


LETTER_OF = {}


def category(name):
    if re.match(r"(cc|cg|ce|cf)[A-Za-z0-9]", name) and name not in ("ccedilla", "ccaron", "ccircumflex"):
        return "connector"
    return "letter"


# ------------------------------------------------------------------ word check
def corpus_lines():
    for p in sorted(CORPUS.glob("*.txt")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield line


def run_ends(geo_runs, gname, rec):
    """(start of first run, end of every pen-down run) in glyph coordinates."""
    runs = rec["runs"]
    if not runs:
        return None, []
    geo = geo_runs[gname]
    first = step_ends(geo, runs[0][0])[0]
    return first, [step_ends(geo, r[-1])[1] for r in runs if "p" in r[-1]]


def word_check(ttf_path, geos, recs):
    blob = hb.Blob.from_file_path(str(ttf_path))
    face = hb.Face(blob)
    font = hb.Font(face)
    names = TTFont(ttf_path).getGlyphOrder()
    tt = TTFont(ttf_path)
    feats = sorted({fr.FeatureTag for fr in tt["GSUB"].table.FeatureList.FeatureRecord if re.match(r"ss\d\d", fr.FeatureTag)})
    configs = [{}] + [{f: True} for f in feats]
    seen, issues = set(), defaultdict(list)
    contacts = defaultdict(lambda: {"in": defaultdict(int), "out": defaultdict(int)})
    checked = 0
    for line in corpus_lines():
        for cfg in configs:
            buf = hb.Buffer()
            buf.add_str(line)
            buf.guess_segment_properties()
            hb.shape(font, buf, cfg)
            gl = [(names[i.codepoint], p.x_offset, p.y_offset, p.x_advance) for i, p in zip(buf.glyph_infos, buf.glyph_positions)]
            for (a, ax, ay, aadv), (b, bx, by, _) in zip(gl, gl[1:]):
                if category(a) != "connector" and category(b) != "connector":
                    continue
                # cg* entry strokes start fresh at the baseline and ce* exit strokes end in the air:
                # only the side of a connector that joins a letter has to touch it
                if (category(b) == "connector" and b.startswith("cg")) or \
                        (category(a) == "connector" and a.startswith("ce")):
                    continue
                key = (a, b, aadv - ax + bx, by - ay)
                if key in seen:
                    continue
                seen.add(key)
                ra, rb = recs.get(a), recs.get(b)
                if not ra or not rb or not ra["runs"] or not rb["runs"]:
                    continue
                checked += 1
                _, a_ends = run_ends(geos, a, ra)
                b_start, _ = run_ends(geos, b, rb)
                bs = (b_start[0] + key[2], b_start[1] + key[3])
                if category(b) == "connector" and category(a) != "connector":
                    contacts[a]["out"][(round(bs[0]), round(bs[1]))] += 1
                if category(a) == "connector" and category(b) != "connector" and a_ends:
                    ae = a_ends[-1]
                    contacts[b]["in"][(round(ae[0] - key[2]), round(ae[1] - key[3]))] += 1
                gap = min((math.dist(e, bs) for e in a_ends), default=1e9)
                if gap > GAP_TOL:
                    word = next((w for w in line.split() if w), line)
                    why = (round(gap), cfg and next(iter(cfg)) or "", line[:40])
                    # blame the letter: connectors are single lines whose direction is certain
                    if category(a) != "connector":
                        issues[a].append((b,) + why)
                    if category(b) != "connector":
                        issues[b].append((a,) + why)
    return issues, checked, len(configs), contacts


def clusters(counter, tol=8):
    out = []
    for p, n in sorted(counter.items(), key=lambda kv: -kv[1]):
        for c in out:
            if math.dist(c["p"], p) <= tol:
                c["n"] += n
                break
        else:
            out.append({"p": p, "n": n})
    return out


def cut_pieces(geo, runs, pts):
    """Cut pieces where a contact point lies inside them; route steps follow the new pieces."""
    new, mapping = [], {}
    for i, pc in enumerate(geo.pieces):
        smp = sample(pc)
        arr = np.array([(x, y) for _, _, x, y, _ in smp])
        L = smp[-1][4]
        cuts = []
        for p in pts:
            d = np.sqrt(((arr - p) ** 2).sum(1))
            k = int(np.argmin(d))
            if d[k] < 12 and 8 < smp[k][4] < L - 8:
                cuts.append((smp[k][2], smp[k][3]))
        subs = cut_open(pc, cuts) if cuts else [pc]
        mapping[i] = list(range(len(new), len(new) + len(subs)))
        new += subs
    geo.pieces = new
    out = []
    for r in runs:
        rr = []
        for st in r:
            if "p" in st:
                ids = mapping[st["p"]][::-1] if st["r"] else mapping[st["p"]]
                rr += [{"p": j, "r": st["r"]} for j in ids]
            else:
                rr.append(st)
        out.append(rr)
    return out


def shortest_walk(geo, a, b):
    """Steps along the pieces from point a to point b (retracing lines), or None."""
    import heapq
    nodes = []

    def node(p):
        for i, q in enumerate(nodes):
            if math.dist(p, q) <= NODE_TOL:
                return i
        nodes.append(p)
        return len(nodes) - 1

    adj = defaultdict(list)
    for pi, pc in enumerate(geo.pieces):
        u, v = node(pc[0][0]), node(pc[-1][-1])
        L = piece_len(pc)
        adj[u].append((v, pi, 0, L))
        adj[v].append((u, pi, 1, L))
    src = min(range(len(nodes)), key=lambda i: math.dist(nodes[i], a))
    dst = min(range(len(nodes)), key=lambda i: math.dist(nodes[i], b))
    if math.dist(nodes[src], a) > 15 or math.dist(nodes[dst], b) > 15:
        return None
    dist, prev, heap = {src: 0.0}, {}, [(0.0, src)]
    while heap:
        d, u = heapq.heappop(heap)
        if u == dst:
            break
        if d > dist.get(u, 1e18):
            continue
        for v, pi, r, L in adj[u]:
            if d + L < dist.get(v, 1e18):
                dist[v], prev[v] = d + L, (u, pi, r)
                heapq.heappush(heap, (d + L, v))
    if dst not in dist:
        return None
    steps, u = [], dst
    while u != src:
        pu, pi, r = prev[u]
        steps.append({"p": pi, "r": r})
        u = pu
    return steps[::-1], dist[dst]


def fit_run(geo, run, entry, exit_):
    """Best of the run and its reverse, each trimmed to start at the entry and end at the exit
    as long as trimming drops no piece. Ties keep the original."""
    def pieces(r):
        return {s["p"] for s in r if "p" in s}

    def trim(r):
        need = pieces(r)
        if entry is not None:
            idx = [i for i, s in enumerate(r) if "p" in s and math.dist(step_ends(geo, s)[0], entry) <= GAP_TOL]
            for i in idx:
                if i > 0 and pieces(r[i:]) == need:
                    r = r[i:]
                    break
        if exit_ is not None:
            idx = [i for i, s in enumerate(r) if "p" in s and math.dist(step_ends(geo, s)[1], exit_) <= GAP_TOL]
            for i in reversed(idx):
                if i < len(r) - 1 and pieces(r[:i + 1]) == need:
                    r = r[:i + 1]
                    break
        return r

    def score(r):
        steps = [s for s in r if "p" in s]
        if not steps:
            return (0, 0)
        ok_in = entry is None or math.dist(step_ends(geo, steps[0])[0], entry) <= GAP_TOL
        ok_out = exit_ is None or math.dist(step_ends(geo, steps[-1])[1], exit_) <= GAP_TOL
        return (ok_in + ok_out, -sum(piece_len(geo.pieces[s["p"]]) for s in steps))

    if any("f" in s for s in run):
        return run
    rev = [{"p": s["p"], "r": 1 - s["r"]} for s in reversed(run)]
    cands = [run, trim(run), trim(rev)]
    best = max(cands, key=score)
    return run if score(best) <= score(run) else best


def mend_runs(geo, runs):
    """A run is one pen-down line. Where a step does not start where the previous one ended, walk
    the shortest way over the centre lines (noted, so the glyph goes to review), or lift the pen."""
    out = []
    for run in runs:
        cur = []
        for s in run:
            if cur and "p" in s and "p" in cur[-1]:
                a, b = step_ends(geo, cur[-1])[1], step_ends(geo, s)[0]
                if math.dist(a, b) > GAP_TOL:
                    w = shortest_walk(geo, a, b)
                    if w:
                        cur += w[0]
                        geo.notes.append(f"gap of {math.dist(a, b):.0f} units inside a stroke (stroke model "
                                         "mapped badly here), closed along the centre lines")
                    else:
                        out.append(cur)
                        cur = []
                        geo.notes.append(f"gap of {math.dist(a, b):.0f} units inside a stroke: pen lifted")
            cur.append(s)
        if cur:
            out.append(cur)
    # a closed gap can leave "there and straight back" on a piece the route draws elsewhere anyway
    for run in out:
        i = 0
        while i + 1 < len(run):
            a, b = run[i], run[i + 1]
            if "p" in a and "p" in b and a["p"] == b["p"] and a["r"] != b["r"]:
                elsewhere = sum(1 for r in out for t in r if t.get("p") == a["p"]) > 2
                before = step_ends(geo, run[i - 1])[1] if i > 0 and "p" in run[i - 1] else None
                after = step_ends(geo, run[i + 2])[0] if i + 2 < len(run) and "p" in run[i + 2] else None
                if elsewhere and (before is None or after is None or math.dist(before, after) <= GAP_TOL):
                    del run[i:i + 2]
                    i = max(0, i - 1)
                    continue
            i += 1
    return out


def attach_contacts(geo, rec, contact):
    ins, outs = clusters(contact["in"]), clusters(contact["out"])
    if not ins and not outs:
        return
    runs = cut_pieces(geo, rec["runs"], [c["p"] for c in ins + outs])
    pen = [i for i, r in enumerate(runs) if any("p" in s for s in r)]
    if not pen:
        rec["runs"] = runs
        return
    # straighten the main run with the real entry/exit points: upstream draws e.g. the upstroke of
    # l inside the letter, while the font puts it in the connector, which flips or pads the mapping
    first = pen[0]
    fitted = fit_run(geo, runs[first], ins[0]["p"] if ins else None, outs[0]["p"] if outs else None)
    if fitted != runs[first]:
        geo.notes.append("main stroke trimmed/turned to run from the entry to the exit")
        runs[first] = fitted
    if outs:
        x = outs[0]["p"]
        run_end = [step_ends(geo, runs[i][-1])[1] for i in pen if "p" in runs[i][-1]]
        if not any(math.dist(e, x) <= GAP_TOL for e in run_end):
            # walk on from the pen-down run that is connected to the exit (not e.g. an accent)
            walks = [(w, i) for i in pen for w in [shortest_walk(geo, step_ends(geo, runs[i][-1])[1], x)] if w]
            w, last = min(walks, key=lambda t: t[0][1]) if walks else (None, None)
            if w:
                runs[last] += w[0]
                geo.notes.append(f"added {w[1]:.0f} units of retracing to reach the exit at {x}")
            else:
                geo.notes.append(f"exit at {x} is not on any centre line")
    if ins:
        e = ins[0]["p"]
        first = pen[0]
        start = step_ends(geo, runs[first][0])[0]
        if math.dist(start, e) > GAP_TOL:
            w = shortest_walk(geo, e, start)
            if w:
                runs[first] = w[0] + runs[first]
                geo.notes.append(f"added {w[1]:.0f} units of retracing from the entry at {e}")
            else:
                geo.notes.append(f"entry at {e} is not on any centre line")
    if len(outs) > 1:
        geo.notes.append(f"{len(outs)} different exit points in the corpus; routed to the most common")
    rec["runs"] = runs
    rec["entries"] = [[*c["p"], c["n"]] for c in ins]
    rec["exits"] = [[*c["p"], c["n"]] for c in outs]


# ------------------------------------------------------------------ main
def main():
    ufo = ufoLib2.Font.open(UFO)
    skel, extra = ufo.layers["skeleton"], ufo.layers["extra"]
    tt = TTFont(TTF)
    order = tt.getGlyphOrder()
    gs = tt.getGlyphSet()
    cmap = {v: k for k, v in tt.getBestCmap().items()}
    for gname, cp in cmap.items():
        base = unicodedata.normalize("NFD", chr(cp))[0]
        if base.isalpha() and base != chr(cp):
            LETTER_OF[gname] = base
    shapes = load_shapes()

    geos, recs = {}, {}
    composites = [n for n in order if ufo[n].components]
    for n in order:
        if n in composites:
            continue
        ink = ink_mask(gs, n)
        geo = GlyphGeo(n)
        sk = contours_of(skel[n]) if n in skel else []
        ex = contours_of(extra[n]) if n in extra else []
        lines, fills, junk = classify(n, sk, ex, ink)
        markers = [tuple((p.x, p.y)) for c in (skel[n].contours if n in skel else []) if len(c.points) == 1 for p in c.points]
        geo.pieces = build_pieces(lines, markers)
        geo.fills = fills
        geo.junk = junk
        if junk:
            geo.notes.append(f"{junk} layer contour(s) outside the ink ignored")
        runs, source = route_glyph(n, geo, shapes, category(n))
        geos[n] = geo
        recs[n] = {"runs": runs, "source": source, "ink": ink}

    def expand(n):
        if n in geos:
            return
        geo = GlyphGeo(n)
        runs = []
        for comp in ufo[n].components:
            expand(comp.baseGlyph)
            sub, m = geos[comp.baseGlyph], tuple(comp.transformation)
            po, fo = len(geo.pieces), len(geo.fills)
            geo.pieces += [transform_piece(pc, m) for pc in sub.pieces]
            geo.fills += [transform_piece(f, m) for f in sub.fills]
            for r in recs[comp.baseGlyph]["runs"]:
                runs.append([{"p": s["p"] + po, "r": s["r"]} if "p" in s else {"f": s["f"] + fo} for s in r])
            geo.notes += [f"{comp.baseGlyph}: {x}" for x in sub.notes]
        geos[n] = geo
        recs[n] = {"runs": runs, "source": "composite:" + "+".join(c.baseGlyph for c in ufo[n].components),
                   "ink": ink_mask(gs, n)}

    for n in composites:
        expand(n)

    # ink coverage
    for n in order:
        geo, rec = geos[n], recs[n]
        ink = rec.pop("ink")
        total = int(ink.sum())
        rec["adv"] = tt["hmtx"][n][0]
        if not total:
            rec["status"], rec["cover"] = ("empty", 1.0)
            continue
        if not geo.pieces and not geo.fills:
            rec["status"], rec["cover"] = "missing", 0.0
            geo.notes.append("ink but no centre lines")
            continue
        m = np.zeros_like(ink)
        stamp(m, [(x, y) for _, _, x, y in piece_samples(geo.pieces)])
        if geo.fills:
            fm = raster(lambda pen: [draw_segs(pen, f) for f in geo.fills])
            m |= dilate(fm, 1)
        cover = float((m & ink).sum() / total)
        rec["cover"] = round(cover, 3)
        if cover < 0.96:
            geo.notes.append(f"centre lines cover only {cover:.0%} of the ink")

    # entry and exit points from the shaped corpus: cut the lines there, and walk on to them
    _, _, _, contacts = word_check(TTF, geos, recs)
    for n, c in contacts.items():
        if n in geos and recs[n]["runs"]:
            attach_contacts(geos[n], recs[n], c)
    for n in order:
        if recs[n]["runs"]:
            recs[n]["runs"] = mend_runs(geos[n], recs[n]["runs"])
    issues, checked, ncfg, _ = word_check(TTF, geos, recs)
    for n in order:
        geo, rec = geos[n], recs[n]
        if n in issues:
            worst = sorted(issues[n], key=lambda t: -t[1])
            geo.notes.append(f"word check: {len(worst)} join(s) with a gap, e.g. next to {worst[0][0]} "
                             f"({worst[0][1]} units{', ' + worst[0][2] if worst[0][2] else ''}) in “{worst[0][3]}”")
        if "status" not in rec:
            partial = any("walked automatically" in x or "retracing" in x or "inside a stroke" in x for x in geo.notes)
            bad = rec["cover"] < 0.96 or n in issues or partial
            if bad:
                rec["status"] = "review"
            elif rec["source"] == "heuristic" or any("direction guessed" in x for x in geo.notes):
                rec["status"] = "guess"            # no stroke model: order walked automatically
            else:
                rec["status"] = "ok"
        rec["notes"] = geo.notes

    out = {"version": 1, "upm": ufo.info.unitsPerEm, "pen": PEN, "font": TTF.name,
           "metrics": {"xheight": ufo.info.xHeight, "ascender": ufo.info.ascender, "descender": ufo.info.descender},
           "glyphOrder": order,   # glyph id -> name (the browser HarfBuzz build has no glyph names)
           "glyphs": {}}
    for n in order:
        geo, rec = geos[n], recs[n]
        out["glyphs"][n] = {
            "adv": rec["adv"], "status": rec["status"], "source": rec["source"], "cover": rec.get("cover"),
            "notes": rec["notes"],
            "pieces": [[[round(v, 1) for q in s for v in q] for s in pc] for pc in geo.pieces],
            "fills": [[[round(v, 1) for q in s for v in q] for s in f] for f in geo.fills],
            "route": rec["runs"],
            "entries": rec.get("entries", []),     # [x, y, times seen] where incoming connectors end
            "exits": rec.get("exits", []),         # [x, y, times seen] where outgoing connectors start
        }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, separators=(",", ":")))
    write_report(out, gs, checked, ncfg)
    counts = defaultdict(int)
    for g in out["glyphs"].values():
        counts[g["status"]] += 1
    print(f"{len(order)} glyphs: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"word check: {checked} distinct joins over {ncfg} feature configurations")
    print(f"-> {OUT_JSON.relative_to(ROOT)}, {OUT_HTML.relative_to(ROOT)}")


def draw_segs(pen, segs):
    pen.moveTo(segs[0][0])
    for s in segs:
        if len(s) == 2:
            pen.lineTo(s[1])
        elif len(s) == 3:
            pen.qCurveTo(s[1], s[2])
        else:
            pen.curveTo(s[1], s[2], s[3])
    pen.closePath()


# ------------------------------------------------------------------ report
def write_report(out, gs, checked, ncfg):
    def d_of(pc):
        p = f"M{pc[0][0]} {pc[0][1]}"
        for s in pc:
            p += {4: "L", 6: "Q", 8: "C"}[len(s)] + " ".join(str(v) for v in s[2:])
        return p

    def rev(pc):
        return [sum([[s[i], s[i + 1]] for i in range(len(s) - 2, -1, -2)], []) for s in reversed(pc)]

    cards = []
    order = sorted(out["glyphs"].items(), key=lambda kv: ({"missing": 0, "review": 1, "guess": 2, "ok": 3, "empty": 4}[kv[1]["status"]], kv[0]))
    for name, g in order:
        if g["status"] == "empty":
            continue
        sp = SVGPathPen(gs)
        gs[name].draw(sp)
        steps = [s for r in g["route"] for s in r]
        n = max(1, len(steps))
        body, k = [], 0
        for ri, r in enumerate(g["route"]):
            for j, s in enumerate(r):
                hue = int(220 - 220 * k / max(1, n - 1))
                col = f"hsl({hue} 80% 42%)"
                if "f" in s:
                    pc = g["fills"][s["f"]]
                    body.append(f'<path d="{d_of(pc)}Z" fill="{col}" stroke="none"/>')
                else:
                    pc = g["pieces"][s["p"]]
                    pc = rev(pc) if s["r"] else pc
                    body.append(f'<path d="{d_of(pc)}" stroke="{col}" marker-end="url(#ah)" style="color:{col}"/>')
                    if j == 0:
                        body.append(f'<circle cx="{pc[0][0]}" cy="{pc[0][1]}" r="30" fill="{col}"/>'
                                    f'<text x="{pc[0][0] - 60}" y="{-pc[0][1] - 40}" transform="scale(1 -1)">{ri + 1}</text>')
                k += 1
        notes = "".join(f"<li>{x}</li>" for x in g["notes"])
        cards.append(
            f'<figure class="{g["status"]}"><svg viewBox="-300 -800 {g["adv"] + 600} 2400">'
            f'<g transform="translate(0 800) scale(1 -1)"><path d="{sp.getCommands()}" fill="#D0D8E4"/>'
            f'<g fill="none" stroke-width="22" stroke-linecap="round">{"".join(body)}</g></g></svg>'
            f'<figcaption><b>{name}</b> <span class="st">{g["status"]}</span><br><small>{g["source"]} · ink {g["cover"]:.0%}'
            f'</small><ul>{notes}</ul></figcaption></figure>')
    counts = defaultdict(int)
    for g in out["glyphs"].values():
        counts[g["status"]] += 1
    summary = " · ".join(f"<b>{counts[k]}</b> {k}" for k in ("ok", "guess", "review", "missing", "empty"))
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(f"""<!doctype html><meta charset="utf-8"><title>Routes</title>
<style>body{{font:14px system-ui;margin:16px;background:#F5F7FA;color:#1B2433}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}}
figure{{margin:0;background:#fff;border:1px solid #D5DCE6;border-radius:6px;padding:6px}}
figure.review{{border-color:#E3A008}} figure.guess{{border-color:#7C9CD6}} figure.missing{{border-color:#D92D20}}
svg{{width:100%;height:170px}} svg text{{font:bold 110px system-ui;fill:#1B2433}}
.st{{font-size:11px;padding:1px 6px;border-radius:9px;background:#E3E8F0}}
.review .st{{background:#FDF0C4}} .missing .st{{background:#FCD9D6}}
ul{{margin:4px 0 0 16px;padding:0;font-size:12px;color:#5B6577}}</style>
<svg width="0" height="0" style="position:absolute"><defs><marker id="ah" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="3" markerHeight="3" orient="auto"><path d="M0 0L10 5L0 10z" fill="context-stroke"/></marker></defs></svg>
<h1>Pen routes (draft)</h1>
<p>{summary}. Colour runs from blue (first) to red (last); numbers mark where the pen goes down.
Word check: {checked} distinct joins in the corpus over {ncfg} feature configurations.</p>
<div class="grid">{''.join(cards)}</div>""", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
