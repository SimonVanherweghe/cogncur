import { describe, expect, it } from 'vitest';
import { polyLen, revSegs, segDir, segsToD } from './geometry';
import { spanPos, spanTime } from './motion';
import { graphWalk, makeInst, plan, type GlyphRoute, type RoutesFile } from './plan';

describe('geometry', () => {
  it('reverses a path, point order included', () => {
    expect(revSegs([[0, 0, 10, 0], [10, 0, 15, 5, 20, 0]])).toEqual([[20, 0, 15, 5, 10, 0], [10, 0, 0, 0]]);
  });
  it('writes lines, quadratics and cubics, and bridges small gaps', () => {
    expect(segsToD([[0, 0, 10, 0], [12, 0, 15, 5, 20, 0], [20, 0, 1, 1, 2, 2, 3, 3]]))
      .toBe('M0 0L10 0L12 0Q15 5 20 0C1 1 2 2 3 3');
    expect(segsToD([[0, 0, 10, 0]], true)).toBe('M0 0L10 0Z');
  });
  it('measures direction and control-polygon length', () => {
    expect(segDir([0, 0, 10, 0], false)).toEqual({ x: 1, y: 0 });
    expect(segDir([0, 0, 0, 10], true)).toEqual({ x: 0, y: 1 });
    expect(segDir([5, 5, 5, 5], true)).toBeNull();
    expect(polyLen([[0, 0, 3, 4], [3, 4, 3, 10]])).toBe(11);
  });
});

describe('motion', () => {
  it('starts and ends at rest and covers the whole stretch', () => {
    for (const L of [5, 200, 5000]) {
      const sp = spanTime(L);
      expect(spanPos(sp, 0)).toBe(0);
      expect(spanPos(sp, sp.T)).toBe(L);
      let prev = 0;
      for (let t = 0; t <= sp.T; t += sp.T / 50) { const p = spanPos(sp, t); expect(p).toBeGreaterThanOrEqual(prev - 1e-9); prev = p; }
    }
  });
});

// A tiny "glyph": a stem up (piece 0), a bar to the right (piece 1), and a dot (fill 0).
const glyph = (route: GlyphRoute['route']): GlyphRoute => ({
  adv: 300, status: 'ok',
  pieces: [[[0, 0, 0, 500]], [[0, 500, 200, 500]]],
  fills: [[[100, 700, 120, 700], [120, 700, 120, 720], [120, 720, 100, 720], [100, 720, 100, 700]]],
  route,
});
const R: RoutesFile = {
  version: 1, upm: 2048, pen: 68, metrics: { xheight: 682, ascender: 1365, descender: -683 }, glyphOrder: [],
  glyphs: { a: glyph([[{ p: 0, r: 0 }, { p: 1, r: 0 }], [{ f: 0 }]]), space: { adv: 300, status: 'empty', pieces: [], fills: [], route: [] } },
};

describe('route planning', () => {
  it('places a glyph with y down and the dot at its centre', () => {
    const inst = makeInst(R, { gid: 1, name: 'a', x: 1000, y: 0 }, 2000);
    expect(inst.pieces[0][0]).toEqual([1000, 2000, 1000, 1500]);
    expect(inst.runs[1][0]).toMatchObject({ center: { x: 1110, y: 1290 } });
  });

  it('walks back over its own lines to reach another node', () => {
    const inst = makeInst(R, { gid: 1, name: 'a', x: 0, y: 0 }, 0);
    const walk = graphWalk(inst, { x: 200, y: -500 }, { x: 0, y: 0 })!;
    expect(walk.map((s) => s.segs)).toEqual([[[200, -500, 0, -500]], [[0, -500, 0, 0]]]);
    expect(walk.every((s) => s.segs && s.walk)).toBe(true);
    expect(graphWalk(inst, { x: 999, y: 999 }, { x: 0, y: 0 })).toBeNull();
  });

  it('writes the dots after the word, or right after each letter', () => {
    const word = [0, 300].map((x) => makeInst(R, { gid: 1, name: 'a', x, y: 0 }, 0));
    const kinds = (extras: 'word' | 'letter') => plan([word], extras).events.map((e) => e.kind).join(' ');
    expect(kinds('word')).toBe('draw air draw air dot air dot');
    expect(kinds('letter')).toBe('draw air dot air draw air dot');
  });

  it('splits words at blanks and reports glyphs without a route', () => {
    const line = [
      makeInst(R, { gid: 1, name: 'a', x: 0, y: 0 }, 0),
      makeInst(R, { gid: 2, name: 'space', x: 300, y: 0 }, 0),
      makeInst(R, { gid: 3, name: 'unknown', x: 600, y: 0 }, 0),
    ];
    expect(plan([line], 'word').issues).toEqual(['unknown: geen route']);
  });
});
