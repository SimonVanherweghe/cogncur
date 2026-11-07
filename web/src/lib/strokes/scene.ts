// The animated SVG for one letter from the designer's stroke model: guides, the letter as a trace,
// the pen line, air moves, direction arrows, numbered start points and turning points.
// Timing follows upstream: 0.5 s lead-in, 1.5 s per lift, duration from length, 0.1 s overlap.
import type { LetterDef } from './letters';

const NS = 'http://www.w3.org/2000/svg';
export const PEN = 68;                                    // round pen, same as the font's style layers
export const LINES = { asc: 1365, x: 683, base: 0, desc: -683 };

interface Pt { x: number; y: number }
type Attrs = Record<string, string | number>;
function el<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Attrs = {}, parent?: Element): SVGElementTagNameMap[K] {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  parent?.appendChild(e);
  return e;
}

const norm = (x: number, y: number): Pt | null => { const l = Math.hypot(x, y); return l < 1e-6 ? null : { x: x / l, y: y / l }; };
function dirAt(path: SVGPathElement, s: number, len: number): Pt | null {
  const a = path.getPointAtLength(Math.max(0, s - 4)), b = path.getPointAtLength(Math.min(len, s + 4));
  return norm(b.x - a.x, b.y - a.y);
}
/** Turning points inside one stroke: the direction flips by more than ~140° over a short distance. */
function cusps(path: SVGPathElement, len: number): Pt[] {
  const out: Pt[] = [], step = 6, span = 14;
  for (let s = span; s <= len - span; s += step) {
    const a = path.getPointAtLength(s - span), b = path.getPointAtLength(s), c = path.getPointAtLength(s + span);
    const d1 = norm(b.x - a.x, b.y - a.y), d2 = norm(c.x - b.x, c.y - b.y);
    if (!d1 || !d2) continue;
    if (d1.x * d2.x + d1.y * d2.y < -0.75) {
      const last = out[out.length - 1];
      if (!last || Math.hypot(last.x - b.x, last.y - b.y) > 60) out.push({ x: b.x, y: b.y });
    }
  }
  return out;
}

/** CSS-style cubic-bezier easing (upstream uses .22,0,.78,1: the pen slows at every start and turn). */
export function bezierEase(p1x: number, p1y: number, p2x: number, p2y: number): (x: number) => number {
  const cx = 3 * p1x, bx = 3 * (p2x - p1x) - cx, ax = 1 - cx - bx;
  const cy = 3 * p1y, by = 3 * (p2y - p1y) - cy, ay = 1 - cy - by;
  const X = (t: number) => ((ax * t + bx) * t + cx) * t, Y = (t: number) => ((ay * t + by) * t + cy) * t;
  const dX = (t: number) => (3 * ax * t + 2 * bx) * t + cx;
  return (x) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 8; i++) { const e = X(t) - x, d = dX(t); if (Math.abs(e) < 1e-5 || !d) break; t -= e / d; }
    return Y(Math.min(1, Math.max(0, t)));
  };
}
const ease = bezierEase(0.22, 0, 0.78, 1);
const easeAir = bezierEase(0.42, 0, 0.58, 1);

interface Stroke { d: string; entry: boolean; lift: boolean; dot: boolean; i: number; el: SVGPathElement; len: number; start: Pt; end: Pt }
type Seg =
  | { kind: 'draw'; s: Stroke; start: number; dur: number }
  | { kind: 'dot'; s: Stroke; start: number; dur: number }
  | { kind: 'air'; from: Pt; to: Pt; start: number; dur: number; line: SVGLineElement };

export interface LetterScene {
  id: string;
  L: LetterDef;
  strokes: Stroke[];
  runs: Stroke[][];
  segs: Seg[];
  total: number;
  tip: SVGCircleElement;
  turnPts: Pt[];
  slant: number;
  layers: Record<'ghost' | 'air' | 'route' | 'turns' | 'guides', SVGGElement>;
}

export function buildLetterScene(svg: SVGSVGElement, id: string, L: LetterDef, slant: number): LetterScene {
  svg.replaceChildren();
  const tan = Math.tan((slant * Math.PI) / 180);
  const x0 = -80 - tan * 700, x1 = L.width + 80 + tan * 1400;
  const yTop = -60, h = LINES.asc - LINES.desc + 120;     // screen coords: y_s = 1365 - y
  svg.setAttribute('viewBox', `${x0} ${yTop} ${x1 - x0} ${h}`);
  svg.setAttribute('aria-label', `Animatie van de schrijfroute van ${id}`);

  const guides = el('g', {}, svg);
  for (const [y, cls] of [[LINES.asc, 'asc'], [LINES.x, 'x'], [LINES.base, 'base'], [LINES.desc, 'desc']] as const) {
    el('line', {
      x1: x0, x2: x1, y1: LINES.asc - y, y2: LINES.asc - y,
      stroke: cls === 'base' ? 'var(--rule-strong)' : 'var(--rule)',
      'stroke-width': cls === 'base' ? 12 : 8, 'stroke-dasharray': cls === 'x' ? '60 50' : 'none',
    }, guides);
  }

  const slantG = el('g', { transform: `translate(${tan * LINES.asc} 0) skewX(${-slant})` }, svg);
  const g = el('g', { transform: `matrix(1 0 0 -1 0 ${LINES.asc})` }, slantG);
  const ghost = el('g', { fill: 'none', stroke: 'var(--ghost)', 'stroke-width': PEN, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, g);
  const air = el('g', { fill: 'none', stroke: 'var(--air)', 'stroke-width': 14, 'stroke-dasharray': '36 30', 'stroke-linecap': 'round' }, g);
  const ink = el('g', { fill: 'none', stroke: 'var(--paper-ink)', 'stroke-width': PEN, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, g);
  const route = el('g', {}, g);
  const turns = el('g', { fill: 'none', stroke: 'var(--turn)', 'stroke-width': 12 }, g);
  const tip = el('circle', { r: 40, fill: 'var(--tip)' }, g);

  const strokes: Stroke[] = L.strokes.map((s, i) => {
    el('path', { d: s.d }, ghost);
    const p = el('path', { d: s.d }, ink);
    const len = Math.max(1, p.getTotalLength());
    const a = p.getPointAtLength(0), b = p.getPointAtLength(len);
    return { ...s, i, el: p, len, start: { x: a.x, y: a.y }, end: { x: b.x, y: b.y } };
  });

  // runs: pen-down sequences between lifts
  const runs: Stroke[][] = [];
  for (const s of strokes) {
    if (!runs.length || s.lift || s.dot) runs.push([]);
    runs[runs.length - 1].push(s);
  }

  // timeline
  const segs: Seg[] = [];
  let t = 0.5;
  let prev: Stroke | null = null;
  for (const s of strokes) {
    if (prev && (s.lift || s.dot)) {
      const line = el('line', { x1: prev.end.x, y1: prev.end.y, x2: prev.end.x, y2: prev.end.y }, air);
      segs.push({ kind: 'air', from: prev.end, to: s.start, start: t + 0.2, dur: 1.0, line });
      t += 1.5;
    }
    if (s.dot) {
      segs.push({ kind: 'dot', s, start: t, dur: 0.3 });
      t += 0.4;
    } else {
      const dur = Math.ceil(s.len / 60) / 10 + 0.3;
      segs.push({ kind: 'draw', s, start: t, dur });
      t += dur - 0.1;
    }
    prev = s;
  }
  const total = t + 0.4;

  // arrows beside each stroke, on the right-hand side of travel, so a retraced stretch shows
  // up-arrows on one side and down-arrows on the other
  const SIDE = PEN / 2 + 52;
  for (const s of strokes) {
    if (s.dot) continue;
    const n = Math.max(1, Math.round(s.len / 320));
    for (let k = 0; k < n; k++) {
      const at = (s.len * (k + 0.5)) / n;
      const pt = s.el.getPointAtLength(at), d = dirAt(s.el, at, s.len);
      if (!d) continue;
      el('path', {
        d: 'M-30,-32 L16,0 L-30,32',
        transform: `translate(${pt.x + d.y * SIDE} ${pt.y - d.x * SIDE}) rotate(${(Math.atan2(d.y, d.x) * 180) / Math.PI})`,
        fill: 'none', stroke: 'var(--route)', 'stroke-width': 16, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      }, route);
    }
  }
  runs.forEach((run, k) => {
    const s0 = run[0];
    el('circle', { cx: s0.start.x, cy: s0.start.y, r: 30, fill: 'var(--route)' }, route);
    const tx = el('text', {
      transform: `translate(${s0.start.x - 70} ${s0.start.y + 70}) scale(1 -1)`,
      'font-size': 120, 'font-weight': 700, 'font-family': 'Atkinson Hyperlegible, system-ui, sans-serif',
      fill: 'var(--route)', 'text-anchor': 'middle', 'dominant-baseline': 'middle',
    }, route);
    tx.textContent = String(k + 1);
  });

  // turning points: inside strokes and at stroke joins inside a run
  const turnPts: Pt[] = [];
  for (const run of runs) {
    run.forEach((s, j) => {
      if (!s.dot) turnPts.push(...cusps(s.el, s.len));
      if (j > 0 && !s.dot) {
        const p = run[j - 1];
        const a = dirAt(p.el, p.len - 6, p.len), b = dirAt(s.el, 6, s.len);
        if (a && b && a.x * b.x + a.y * b.y < -0.5) turnPts.push({ x: s.start.x, y: s.start.y });
      }
    });
  }
  for (const pt of turnPts) el('circle', { cx: pt.x, cy: pt.y, r: 58 }, turns);

  for (const s of strokes) {
    s.el.setAttribute('stroke-dasharray', `${s.len} ${s.len + 200}`);
    s.el.style.visibility = 'hidden';
  }
  return { id, L, strokes, runs, segs, total, tip, turnPts, slant, layers: { ghost, air, route, turns, guides } };
}

export function renderLetterAt(scene: LetterScene, time: number): void {
  let pen: Pt | null = null, down = true;
  for (const seg of scene.segs) {
    const p = Math.min(1, Math.max(0, (time - seg.start) / seg.dur));
    if (seg.kind === 'draw') {
      const e = ease(p), s = seg.s;
      s.el.style.visibility = e > 0 ? 'visible' : 'hidden';
      s.el.setAttribute('stroke-dashoffset', String(s.len * (1 - e)));
      if (time >= seg.start || !pen) { pen = s.el.getPointAtLength(s.len * e); down = true; }
    } else if (seg.kind === 'dot') {
      seg.s.el.style.visibility = time >= seg.start ? 'visible' : 'hidden';
      if (time >= seg.start) { pen = seg.s.end; down = true; }
    } else {
      const e = easeAir(p);
      const x = seg.from.x + (seg.to.x - seg.from.x) * e, y = seg.from.y + (seg.to.y - seg.from.y) * e;
      seg.line.setAttribute('x2', String(x));
      seg.line.setAttribute('y2', String(y));
      seg.line.style.visibility = p > 0 ? 'visible' : 'hidden';
      if (time >= seg.start && p < 1) { pen = { x, y }; down = false; }
      else if (p >= 1 && time >= seg.start) { pen = seg.to; down = false; }
    }
  }
  pen ??= scene.strokes[0]?.start ?? { x: 0, y: 0 };
  const tip = scene.tip;
  tip.setAttribute('cx', String(pen.x));
  tip.setAttribute('cy', String(pen.y));
  tip.setAttribute('r', down ? '40' : '54');
  tip.setAttribute('fill', down ? 'var(--tip)' : 'none');
  tip.setAttribute('stroke', down ? 'none' : 'var(--tip)');
  tip.setAttribute('stroke-width', down ? '0' : '14');
  tip.style.visibility = time >= scene.total - 0.05 ? 'hidden' : 'visible';
}

export function letterStats(s: LetterScene): [string, string | number][] {
  const len = s.strokes.reduce((a, x) => a + (x.dot ? 0 : x.len), 0);
  return [
    ['Halen in het model', s.strokes.length],
    ['Doorlopende lijnen', s.runs.length],
    ['Pen optillen', s.runs.length - 1],
    ['Keerpunten', s.turnPts.length],
    ['Lengte van de lijn', `${Math.round(len).toLocaleString('nl-BE')} eenheden`],
  ];
}

function sample(path: SVGPathElement, len: number, step = 10): number[][] {
  const pts: number[][] = [];
  for (let s = 0; s < len; s += step) { const p = path.getPointAtLength(s); pts.push([+p.x.toFixed(1), +p.y.toFixed(1)]); }
  const e = path.getPointAtLength(len);
  pts.push([+e.x.toFixed(1), +e.y.toFixed(1)]);
  return pts;
}

/** Pen down/up as point lists every 10 units (for plotters, robots or flight paths). */
export function exportLetterJSON(scene: LetterScene): string {
  const out: { pen: 'up' | 'down'; points: number[][] }[] = [];
  let prevEnd: Pt | null = null;
  const r = (p: Pt) => [+p.x.toFixed(1), +p.y.toFixed(1)];
  for (const run of scene.runs) {
    if (prevEnd) out.push({ pen: 'up', points: [r(prevEnd), r(run[0].start)] });
    const pts: number[][] = [];
    for (const s of run) { const p = sample(s.el, s.len); if (pts.length) p.shift(); pts.push(...p); }
    out.push({ pen: 'down', points: pts });
    prevEnd = run[run.length - 1].end;
  }
  return JSON.stringify({
    letter: scene.id, source: 'syboor/cogncur cogncur_shapes.svg',
    units: 'font units, y up', lines: LINES, pen: PEN, slant: scene.slant, path: out,
  }, null, 1).replace(/\[\n\s+(-?[\d.]+),\n\s+(-?[\d.]+)\n\s+\]/g, '[$1,$2]');
}

/** One subpath per run: the leading moveto of a continuing stroke becomes a lineto (the stroke data
    sometimes leaves a gap of ~1 unit), so the line really is one path and relative commands stay exact. */
export function exportLetterSVG(scene: LetterScene): string {
  const ds = scene.runs.map((run) => run.map((s, j) => (j === 0 ? s.d.trim() : s.d.trim().replace(/^M/, 'L'))).join(' '));
  const w = Math.ceil(scene.L.width);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -${LINES.asc} ${w} ${LINES.asc - LINES.desc}">\n` +
    `  <!-- ${scene.id}: one path per continuous line, font units, y up (flipped below) -->\n` +
    `  <g transform="scale(1 -1)" fill="none" stroke="#000" stroke-width="${PEN}" stroke-linecap="round" stroke-linejoin="round">\n` +
    ds.map((d, i) => `    <path id="lijn-${i + 1}" d="${d}"/>`).join('\n') + '\n  </g>\n</svg>';
}
