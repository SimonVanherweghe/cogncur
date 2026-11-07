// Path geometry for the pen routes. A segment is a flat list of 2, 3 or 4 points
// [x0, y0, x1, y1, …]: a line, a quadratic or a cubic Bézier.

export type Seg = number[];
export interface Pt { x: number; y: number }

export const dist = (a: Pt, b: Pt): number => Math.hypot(a.x - b.x, a.y - b.y);

export const segStart = (s: Seg): Pt => ({ x: s[0], y: s[1] });
export const segEnd = (s: Seg): Pt => ({ x: s[s.length - 2], y: s[s.length - 1] });

/** The same path, travelled the other way. */
export function revSegs(segs: Seg[]): Seg[] {
  return segs.slice().reverse().map((s) => {
    const out: Seg = [];
    for (let i = s.length - 2; i >= 0; i -= 2) out.push(s[i], s[i + 1]);
    return out;
  });
}

/** Unit tangent (screen coordinates) at the start or end of a segment; null if it has no length. */
export function segDir(s: Seg, atEnd: boolean): Pt | null {
  let a: Pt, b: Pt;
  if (atEnd) {
    b = segEnd(s);
    a = b;
    for (let i = s.length - 4; i >= 0; i -= 2) { a = { x: s[i], y: s[i + 1] }; if (dist(a, b) > 0.5) break; }
  } else {
    a = segStart(s);
    b = a;
    for (let i = 2; i < s.length; i += 2) { b = { x: s[i], y: s[i + 1] }; if (dist(a, b) > 0.5) break; }
  }
  const l = dist(a, b);
  return l < 1e-6 ? null : { x: (b.x - a.x) / l, y: (b.y - a.y) / l };
}

/** Control-polygon length: an upper bound, good enough for path search. */
export function polyLen(segs: Seg[]): number {
  let L = 0;
  for (const s of segs) for (let i = 2; i < s.length; i += 2) L += Math.hypot(s[i] - s[i - 2], s[i + 1] - s[i - 1]);
  return L;
}

/** SVG path data; a gap between segments becomes a straight line (they are within joining distance). */
export function segsToD(segs: Seg[], closed = false): string {
  if (!segs.length) return '';
  const r = (v: number) => +v.toFixed(1);
  let d = `M${r(segs[0][0])} ${r(segs[0][1])}`;
  let cur = segStart(segs[0]);
  for (const s of segs) {
    if (dist(cur, segStart(s)) > 0.5) d += `L${r(s[0])} ${r(s[1])}`;
    const p = s.slice(2).map(r);
    d += (p.length === 2 ? 'L' : p.length === 4 ? 'Q' : 'C') + p.join(' ');
    cur = segEnd(s);
  }
  return closed ? d + 'Z' : d;
}
