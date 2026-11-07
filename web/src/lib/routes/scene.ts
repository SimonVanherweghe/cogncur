// The animated SVG for the word page: guides, the font's own ink as a "ghost" to write over,
// the pen line drawn with a moving dash, dots, air moves, direction arrows and turning points.
import { dist, segDir, segStart, segsToD, type Pt, type Seg } from './geometry';
import { spanPos, spanTime, type Span } from './motion';
import { makeInst, plan, stepEnd, type Extras, type RoutesFile } from './plan';
import { shape, type LoadedFont } from '../font';

const NS = 'http://www.w3.org/2000/svg';
export const LINE_GAP = 2600;   // distance between text lines

type Attrs = Record<string, string | number>;
function el<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Attrs = {}, parent?: Element): SVGElementTagNameMap[K] {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  parent?.appendChild(e);
  return e;
}

export interface Stroke { el: SVGPathElement; len: number; start: Pt | null; n: number }
type TimedSpan = Span & { s0: number; start: number };
export type TimedSeg =
  | { kind: 'draw'; stroke: Stroke; spans: TimedSpan[]; start: number; dur: number }
  | { kind: 'dot'; el: SVGPathElement; at: Pt; start: number; dur: number }
  | { kind: 'air'; from: Pt; to: Pt; start: number; dur: number; line: SVGLineElement };

export interface Scene {
  segs: TimedSeg[];
  strokes: Stroke[];
  total: number;
  tip: SVGCircleElement;
  stats: { strokes: number; lifts: number; dots: number; drawLen: number; walkLen: number; turns: number };
  issues: string[];
  layers: Record<'guides' | 'ghost' | 'route' | 'turns' | 'air' | 'names', SVGGElement>;
  pen: number;
}

export interface SceneInput { text: string; feats: Set<string>; extras: Extras }

export function buildScene(svg: SVGSVGElement, F: LoadedFont, R: RoutesFile, input: SceneInput): Scene {
  svg.replaceChildren();
  const texts = input.text.split('\n').map((s) => s.replace(/\s+$/, '')).filter((s, i, a) => s || i < a.length - 1);
  const shaped = texts.map((t) => shape(F, t, input.feats));
  const { ascender: asc, descender: desc, xheight: xh } = R.metrics;
  const top = 200;
  const lines = shaped.map((sh, li) => sh.glyphs.map((sg) => makeInst(R, sg, top + asc + li * LINE_GAP)));
  const width = Math.max(1200, ...shaped.map((s) => s.width));
  const x0 = -350, x1 = width + 350;
  const height = top + asc + (lines.length - 1) * LINE_GAP - desc + 300;
  svg.setAttribute('viewBox', `${x0} 0 ${x1 - x0} ${height}`);
  svg.setAttribute('aria-label', `Animatie van de schrijfroute van ${input.text.replace(/\n/g, ' ')}`);

  const guides = el('g', {}, svg);
  lines.forEach((_, li) => {
    const by = top + asc + li * LINE_GAP;
    for (const [y, kind] of [[asc, 'asc'], [xh, 'x'], [0, 'base'], [desc, 'desc']] as const) {
      el('line', {
        x1: x0 + 60, x2: x1 - 60, y1: by - y, y2: by - y,
        stroke: kind === 'base' ? 'var(--rule-strong)' : 'var(--rule)',
        'stroke-width': kind === 'base' ? 12 : 8, 'stroke-dasharray': kind === 'x' ? '60 50' : 'none',
      }, guides);
    }
  });
  const ghost = el('g', { fill: 'var(--ghost)' }, svg);
  const names = el('g', { 'font-family': 'ui-monospace, Menlo, monospace', 'font-size': 64, 'text-anchor': 'start' }, svg);
  const air = el('g', { fill: 'none', stroke: 'var(--air)', 'stroke-width': 14, 'stroke-dasharray': '36 30', 'stroke-linecap': 'round' }, svg);
  const ink = el('g', { fill: 'none', stroke: 'var(--paper-ink)', 'stroke-width': R.pen, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
  const dots = el('g', { fill: 'var(--paper-ink)' }, svg);
  const route = el('g', {}, svg);
  const turns = el('g', { fill: 'none', stroke: 'var(--turn)', 'stroke-width': 12 }, svg);
  const tip = el('circle', { r: 40, fill: 'var(--tip)' }, svg);

  // ghost: the font's own ink, so any mismatch between route and letter shows up
  const flagged: string[] = [];
  lines.forEach((line) => line.forEach((inst, k) => {
    const d = F.svgPath(inst.gid);
    if (d) el('path', { d, transform: `translate(${inst.ox} ${inst.by - inst.oy}) scale(1 -1)` }, ghost);
    const st = inst.g ? inst.g.status : 'missing';
    if (st === 'review' || st === 'missing') flagged.push(`${inst.name} (${st === 'missing' ? 'geen route' : 'nakijken'})`);
    if (inst.name === 'space') return;
    const t = el('text', {
      x: inst.ox, y: inst.by - desc + 110 + (k % 2) * 80,
      fill: st === 'ok' ? 'var(--ui-muted)' : st === 'guess' ? 'var(--ui-focus)' : 'var(--warn)',
    }, names);
    t.textContent = inst.name;
  }));

  const { events, issues } = plan(lines, input.extras);

  // timeline
  const segs: TimedSeg[] = [], strokes: Stroke[] = [], turnPts: Pt[] = [];
  let t = 0.4, nStroke = 0, walkLen = 0, drawLen = 0, lifts = 0;
  for (const ev of events) {
    if (ev.kind === 'air') {
      const line = el('line', { x1: ev.from.x, y1: ev.from.y, x2: ev.from.x, y2: ev.from.y }, air);
      const dur = 0.3 + dist(ev.from, ev.to) / 3200;
      segs.push({ kind: 'air', from: ev.from, to: ev.to, start: t, dur, line });
      t += dur;
      lifts++;
    } else if (ev.kind === 'dot') {
      const p = el('path', { d: segsToD(ev.fill, true) }, dots);
      segs.push({ kind: 'dot', el: p, at: ev.center, start: t, dur: 0.3 });
      t += 0.4;
    } else {
      const lineSteps = ev.steps.filter((s): s is Extract<typeof s, { segs: Seg[] }> => !!s.segs);
      const allSegs = lineSteps.flatMap((s) => s.segs);
      const p = el('path', { d: segsToD(allSegs) }, ink);
      // stops: wherever the direction turns sharply between two steps (a turning point)
      const probe = el('path', {}, svg);
      let acc = 0;
      const bounds = [0];
      lineSteps.forEach((st, j) => {
        probe.setAttribute('d', segsToD(st.segs));
        const L = probe.getTotalLength();
        if (st.walk) walkLen += L;
        acc += L;
        if (j < lineSteps.length - 1) {
          const a = segDir(st.segs[st.segs.length - 1], true), b = segDir(lineSteps[j + 1].segs[0], false);
          if (a && b && a.x * b.x + a.y * b.y < 0.2) {
            bounds.push(acc);
            if (a.x * b.x + a.y * b.y < -0.5) turnPts.push(stepEnd(st));
          }
        }
      });
      probe.remove();
      const len = Math.max(1, p.getTotalLength());
      bounds.push(len);
      const spans: TimedSpan[] = [];
      let ts = t;
      for (let j = 1; j < bounds.length; j++) {
        const sp = spanTime(Math.max(0.01, bounds[j] - bounds[j - 1]));
        spans.push({ ...sp, s0: bounds[j - 1], start: ts });
        ts += sp.T;
      }
      p.setAttribute('stroke-dasharray', `${len} ${len + 200}`);
      const stroke: Stroke = { el: p, len, start: allSegs.length ? segStart(allSegs[0]) : null, n: ++nStroke };
      strokes.push(stroke);
      segs.push({ kind: 'draw', stroke, spans, start: t, dur: ts - t });
      drawLen += len;
      t = ts + 0.05;
    }
  }
  const total = t + 0.4;

  // direction arrows (right-hand side of travel) and numbered start points
  const SIDE = R.pen / 2 + 52;
  for (const s of strokes) {
    const n = Math.max(1, Math.round(s.len / 380));
    for (let k = 0; k < n; k++) {
      const at = (s.len * (k + 0.5)) / n;
      const a = s.el.getPointAtLength(Math.max(0, at - 4)), b = s.el.getPointAtLength(Math.min(s.len, at + 4));
      const l = dist(a, b);
      if (l < 1e-6) continue;
      const d = { x: (b.x - a.x) / l, y: (b.y - a.y) / l };
      const pt = s.el.getPointAtLength(at);
      el('path', {
        d: 'M-30,-32 L16,0 L-30,32',
        transform: `translate(${pt.x - d.y * SIDE} ${pt.y + d.x * SIDE}) rotate(${(Math.atan2(d.y, d.x) * 180) / Math.PI})`,
        fill: 'none', stroke: 'var(--route)', 'stroke-width': 16, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      }, route);
    }
    if (s.start) {
      el('circle', { cx: s.start.x, cy: s.start.y, r: 30, fill: 'var(--route)' }, route);
      const tx = el('text', {
        x: s.start.x - 70, y: s.start.y - 70, 'font-size': 120, 'font-weight': 700,
        'font-family': 'Atkinson Hyperlegible, system-ui, sans-serif',
        fill: 'var(--route)', 'text-anchor': 'middle', 'dominant-baseline': 'middle',
      }, route);
      tx.textContent = String(s.n);
    }
  }
  for (const pt of turnPts) el('circle', { cx: pt.x, cy: pt.y, r: 58 }, turns);

  return {
    segs, strokes, total, tip, pen: R.pen,
    stats: { strokes: strokes.length, lifts, dots: segs.filter((s) => s.kind === 'dot').length, drawLen, walkLen, turns: turnPts.length },
    issues: [...new Set([...issues, ...flagged])],
    layers: { guides, ghost, route, turns, air, names },
  };
}

/** Show the scene at a moment in time (seconds). */
export function renderAt(scene: Scene, time: number): void {
  let pen: Pt | null = null, down = true;
  for (const seg of scene.segs) {
    if (seg.kind === 'draw') {
      const s = seg.stroke;
      let pos = 0;
      for (const sp of seg.spans) if (time >= sp.start) pos = sp.s0 + spanPos(sp, time - sp.start);
      if (time < seg.start) pos = 0;
      s.el.style.visibility = pos > 0 ? 'visible' : 'hidden';
      s.el.setAttribute('stroke-dashoffset', String(s.len - pos));
      if (time >= seg.start || !pen) { pen = s.el.getPointAtLength(pos); down = true; }
    } else if (seg.kind === 'dot') {
      seg.el.style.visibility = time >= seg.start ? 'visible' : 'hidden';
      if (time >= seg.start || !pen) { pen = seg.at; down = true; }
    } else {
      const p = Math.min(1, Math.max(0, (time - seg.start) / seg.dur));
      const e = p < 0.5 ? 2 * p * p : 1 - 2 * (1 - p) * (1 - p);
      const x = seg.from.x + (seg.to.x - seg.from.x) * e, y = seg.from.y + (seg.to.y - seg.from.y) * e;
      seg.line.setAttribute('x2', String(x));
      seg.line.setAttribute('y2', String(y));
      seg.line.style.visibility = p > 0 ? 'visible' : 'hidden';
      if (time >= seg.start) { pen = { x, y }; down = p >= 1; }
    }
  }
  const tip = scene.tip;
  if (!pen) { tip.style.visibility = 'hidden'; return; }
  tip.setAttribute('cx', String(pen.x));
  tip.setAttribute('cy', String(pen.y));
  tip.setAttribute('r', down ? '40' : '54');
  tip.setAttribute('fill', down ? 'var(--tip)' : 'none');
  tip.setAttribute('stroke', down ? 'none' : 'var(--tip)');
  tip.setAttribute('stroke-width', down ? '0' : '14');
  tip.style.visibility = time >= scene.total - 0.05 ? 'hidden' : 'visible';
}

/** One path per continuous line, in writing order, plus the dots. */
export function exportSVG(scene: Scene, svg: SVGSVGElement, text: string): string {
  const paths = scene.strokes.map((s, i) => `    <path id="lijn-${i + 1}" d="${s.el.getAttribute('d')}"/>`);
  const dots = scene.segs.filter((s) => s.kind === 'dot').map((s, i) => `    <path id="punt-${i + 1}" d="${s.el.getAttribute('d')}"/>`);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${svg.getAttribute('viewBox')}">\n` +
    `  <!-- ${text.replace(/--/g, '- -')}: one path per continuous line, in writing order -->\n` +
    `  <g fill="none" stroke="#000" stroke-width="${scene.pen}" stroke-linecap="round" stroke-linejoin="round">\n` +
    paths.join('\n') + '\n  </g>\n  <g fill="#000">\n' + dots.join('\n') + '\n  </g>\n</svg>';
}

/** Pen down/up as point lists every 10 units (for a plotter). */
export function exportPoints(scene: Scene, text: string, features: string[]): string {
  const out: { pen: 'up' | 'down'; dot?: true; points: number[][] }[] = [];
  let prevEnd: Pt | null = null;
  const r = (p: Pt) => [+p.x.toFixed(1), +p.y.toFixed(1)];
  for (const seg of scene.segs) {
    if (seg.kind === 'air') continue;
    if (seg.kind === 'dot') {
      if (prevEnd) out.push({ pen: 'up', points: [r(prevEnd), r(seg.at)] });
      out.push({ pen: 'down', dot: true, points: [r(seg.at)] });
      prevEnd = seg.at;
      continue;
    }
    const s = seg.stroke, pts: number[][] = [];
    for (let d = 0; d < s.len; d += 10) pts.push(r(s.el.getPointAtLength(d)));
    pts.push(r(s.el.getPointAtLength(s.len)));
    if (prevEnd) out.push({ pen: 'up', points: [r(prevEnd), pts[0]] });
    out.push({ pen: 'down', points: pts });
    const e = s.el.getPointAtLength(s.len);
    prevEnd = { x: e.x, y: e.y };
  }
  return JSON.stringify({ text, features, units: 'font units, y down (SVG)', pen: scene.pen, path: out }, null, 1)
    .replace(/\[\n\s+(-?[\d.]+),\n\s+(-?[\d.]+)\n\s+\]/g, '[$1,$2]');
}
