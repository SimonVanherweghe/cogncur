// Turning shaped text into one pen line: the glyph routes from routes.json (scripts/routes.py),
// chained; where a route doesn't end at the next connector, the pen walks back over the glyph's
// own centre lines (shortest path), else it lifts. Dots/accents/crossbars can wait until the
// word is finished. Coordinates: font units, already slanted like the font.
import { dist, polyLen, revSegs, segEnd, segStart, type Pt, type Seg } from './geometry';

export const JOIN = 25;   // pen positions closer than this are the same point (routes.py GAP_TOL is 20)

export type RouteStep = { p: number; r: 0 | 1 } | { f: number };
export type GlyphStatus = 'ok' | 'guess' | 'review' | 'missing' | 'empty';

export interface GlyphRoute {
  adv: number;
  status: GlyphStatus;
  pieces: Seg[][];
  fills: Seg[][];
  route: RouteStep[][];
}

export interface RoutesFile {
  version: number;
  upm: number;
  pen: number;
  metrics: { xheight: number; ascender: number; descender: number };
  glyphOrder: string[];
  glyphs: Record<string, GlyphRoute>;
}

/** One step of a run: a stretch of line, or a filled shape (a dot) the pen taps at its centre. */
export type Step = { segs: Seg[]; walk?: boolean; via?: string; fill?: undefined } | { fill: Seg[]; center: Pt; segs?: undefined };

/** A glyph placed on the sheet, in screen coordinates (y down). */
export interface Inst {
  name: string;
  gid: number;
  g: GlyphRoute | undefined;
  ox: number;
  oy: number;
  by: number;
  pieces: Seg[][];
  fills: Seg[][];
  runs: Step[][];
}

export interface PlacedGlyph { gid: number; name: string; x: number; y: number }

/** Place a glyph with its baseline at screen y = by. */
export function makeInst(R: RoutesFile, sg: PlacedGlyph, by: number): Inst {
  const g = R.glyphs[sg.name];
  const ox = sg.x, oy = sg.y;
  const tp = (s: Seg): Seg => {
    const o: Seg = [];
    for (let i = 0; i < s.length; i += 2) o.push(ox + s[i], by - (oy + s[i + 1]));
    return o;
  };
  const inst: Inst = { name: sg.name, gid: sg.gid, g, ox, oy, by, pieces: [], fills: [], runs: [] };
  if (!g) return inst;
  inst.pieces = g.pieces.map((pc) => pc.map(tp));
  inst.fills = g.fills.map((f) => f.map(tp));
  inst.runs = g.route.map((run) => run.map((st): Step => {
    if ('f' in st) {
      const f = inst.fills[st.f], pts = f.map(segStart);
      const center = { x: pts.reduce((a, p) => a + p.x, 0) / pts.length, y: pts.reduce((a, p) => a + p.y, 0) / pts.length };
      return { fill: f, center };
    }
    return { segs: st.r ? revSegs(inst.pieces[st.p]) : inst.pieces[st.p] };
  }));
  return inst;
}

export const stepStart = (st: Step): Pt => (st.fill ? st.center : segStart(st.segs[0]));
export const stepEnd = (st: Step): Pt => (st.fill ? st.center : segEnd(st.segs[st.segs.length - 1]));
export const runStart = (run: Step[]): Pt => stepStart(run[0]);
export const runEnd = (run: Step[]): Pt => stepEnd(run[run.length - 1]);

/** Shortest walk over a glyph's centre lines from P to Q (both within JOIN of a piece end).
    This is how the pen reaches an exit the stored route doesn't end on (B has 8), or starts
    from an entry other than the route's start: it retraces its own line. */
export function graphWalk(inst: Inst | null, P: Pt, Q: Pt): Step[] | null {
  if (!inst || !inst.pieces.length) return null;
  const nodes: Pt[] = [];
  const adj: { to: number; k: number; r: 0 | 1; w: number }[][] = [];
  const nodeOf = (p: Pt) => {
    for (let i = 0; i < nodes.length; i++) if (dist(nodes[i], p) < 3) return i;
    nodes.push(p);
    adj.push([]);
    return nodes.length - 1;
  };
  inst.pieces.forEach((pc, k) => {
    const a = nodeOf(segStart(pc[0])), b = nodeOf(segEnd(pc[pc.length - 1])), w = polyLen(pc);
    adj[a].push({ to: b, k, r: 0, w });
    adj[b].push({ to: a, k, r: 1, w });
  });
  const near = (p: Pt) => {
    let best = -1, bd = JOIN;
    nodes.forEach((n, i) => { const d = dist(n, p); if (d < bd) { bd = d; best = i; } });
    return best;
  };
  const s = near(P), t = near(Q);
  if (s < 0 || t < 0) return null;
  if (s === t) return [];
  // Dijkstra (glyphs have a handful of nodes, so a linear scan is fine)
  const D = nodes.map(() => Infinity);
  const prev: ({ from: number; e: (typeof adj)[number][number] } | null)[] = nodes.map(() => null);
  const done = nodes.map(() => false);
  D[s] = 0;
  for (;;) {
    let u = -1;
    for (let i = 0; i < nodes.length; i++) if (!done[i] && D[i] < Infinity && (u < 0 || D[i] < D[u])) u = i;
    if (u < 0 || u === t) break;
    done[u] = true;
    for (const e of adj[u]) if (D[u] + e.w < D[e.to]) { D[e.to] = D[u] + e.w; prev[e.to] = { from: u, e }; }
  }
  if (D[t] === Infinity) return null;
  const steps: Step[] = [];
  for (let v = t; v !== s; v = prev[v]!.from) {
    const { e } = prev[v]!;
    steps.unshift({ segs: e.r ? revSegs(inst.pieces[e.k]) : inst.pieces[e.k], walk: true });
  }
  return steps;
}

/** Which run of a glyph reaches the point where the next glyph starts: the last run that passes
    within JOIN of it, else the run ending closest to it. */
export function exitRun(inst: Inst, Q: Pt | null): number {
  if (!Q) return inst.runs.length - 1;
  let found = -1;
  inst.runs.forEach((run, k) => {
    for (const st of run) if (st.segs && st.segs.some((s) => dist(segStart(s), Q) < JOIN || dist(segEnd(s), Q) < JOIN)) found = k;
  });
  if (found >= 0) return found;
  let best = 0, bd = Infinity;
  inst.runs.forEach((run, k) => { const d = dist(runEnd(run), Q); if (d < bd) { bd = d; best = k; } });
  return best;
}

export type PlanEvent =
  | { kind: 'draw'; steps: Step[] }
  | { kind: 'dot'; fill: Seg[]; center: Pt }
  | { kind: 'air'; from: Pt; to: Pt };

export type Extras = 'word' | 'letter';

/** The whole text as pen-down strokes, dots and air moves. */
export function plan(lines: Inst[][], extras: Extras): { events: PlanEvent[]; issues: string[] } {
  const events: PlanEvent[] = [];
  const issues: string[] = [];
  let pen: Pt | null = null;
  let cur: Step[] | null = null;   // current pen-down stroke

  const lift = () => { if (cur && cur.length) events.push({ kind: 'draw', steps: cur }); cur = null; };
  const moveTo = (P: Pt) => {      // pen up and fly to P
    lift();
    if (pen && dist(pen, P) > 1) events.push({ kind: 'air', from: pen, to: P });
    pen = P;
  };
  // continue the pen-down line to P if possible (same point, or a walk over one of the glyphs)
  const reach = (P: Pt, a: Inst | null, b: Inst | null) => {
    if (pen && cur && dist(pen, P) < JOIN) return true;
    if (pen && cur) {
      for (const g of [a, b]) {
        const w = graphWalk(g, pen, P);
        if (w) { for (const s of w) if (s.segs) s.via = g!.name; cur.push(...w); pen = P; return true; }
      }
    }
    return false;
  };
  const drawRun = (run: Step[], prevInst: Inst | null, inst: Inst) => {
    for (const st of run) {
      if (st.fill) { moveTo(st.center); events.push({ kind: 'dot', fill: st.fill, center: st.center }); continue; }
      const P = stepStart(st);
      if (!reach(P, prevInst, inst)) { moveTo(P); cur = []; }
      cur ??= [];
      cur.push(st);
      pen = stepEnd(st);
    }
  };

  for (const line of lines) {
    const words: Inst[][] = [];
    let w: Inst[] = [];
    for (const inst of line) {
      if (!inst.g) { issues.push(`${inst.name}: geen route`); continue; }
      if (!inst.runs.length) { if (w.length) words.push(w); w = []; continue; }   // space and other blanks
      w.push(inst);
    }
    if (w.length) words.push(w);

    for (const word of words) {
      const deferred: { run: Step[]; inst: Inst }[] = [];
      let prevInst: Inst | null = null;
      word.forEach((inst, i) => {
        const next = word[i + 1];
        const Q = next ? runStart(next.runs[0]) : null;
        const out = exitRun(inst, Q);
        inst.runs.forEach((run, k) => {
          if (extras === 'word' && k > out) deferred.push({ run, inst });
          else drawRun(run, prevInst, inst);
        });
        prevInst = inst;
      });
      lift();
      for (const { run, inst } of deferred) drawRun(run, null, inst);
      lift();
    }
  }
  return { events, issues };
}
