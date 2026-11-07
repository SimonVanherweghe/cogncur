// The font in the browser: registered as the CSS font "Vtex" (for text on the page) and loaded
// into HarfBuzz (for drawing on canvas/SVG with exactly the shaping of the test bank).
import * as hb from 'harfbuzzjs';
import { FEATURES, type FeatureState } from './features';
import { versionAsset } from './url';

export const UPM = 2048, ASC = 1768, DESC = 703;
export const XH = 682, ASCENDER = 1364, DESCENDER = 682;

export interface ShapedGlyph { gid: number; name: string; x: number; y: number; adv: number; cluster: number }
export interface Shaped { glyphs: ShapedGlyph[]; width: number }

export interface LoadedFont {
  hb: hb.Font;
  data: ArrayBuffer;
  path(gid: number): Path2D;
  svgPath(gid: number): string;
}

// The CSS fonts "Vtex" and "Cogncur" (the original) are declared in layouts/Base.astro with the
// same metric overrides, so baselines line up. Here the file is only needed for HarfBuzz.

let vtex: Promise<LoadedFont> | undefined;

/** The new font in HarfBuzz. Loaded once per page (the browser cache shares it with the CSS font). */
export function loadFont(): Promise<LoadedFont> {
  vtex ??= (async () => {
    const res = await fetch(versionAsset('fonts/Vtex-Regular.ttf'));
    if (!res.ok) throw new Error(`Lettertype niet gevonden (${res.status}).`);
    const data = await res.arrayBuffer();
    const font = new hb.Font(new hb.Face(new hb.Blob(data)));
    const paths = new Map<number, string>();
    const p2d = new Map<number, Path2D>();
    const svgPath = (gid: number) => {
      if (!paths.has(gid)) paths.set(gid, font.glyphToPath(gid) || '');
      return paths.get(gid)!;
    };
    return {
      hb: font,
      data,
      svgPath,
      path(gid) {
        if (!p2d.has(gid)) p2d.set(gid, new Path2D(svgPath(gid)));
        return p2d.get(gid)!;
      },
    };
  })();
  return vtex;
}

/** Shape one line. All features are passed explicitly (on or off). */
export function shape(F: LoadedFont, text: string, state: FeatureState | Iterable<string>): Shaped {
  const on = state instanceof Set || Array.isArray(state) ? new Set(state as Iterable<string>) : null;
  const feats = FEATURES.map((f) => new hb.Feature(f.tag, (on ? on.has(f.tag) || !!f.on : (state as FeatureState)[f.tag]) ? 1 : 0));
  const buf = new hb.Buffer();
  buf.addText(text);
  buf.guessSegmentProperties();
  hb.shape(F.hb, buf, feats);
  const infos = buf.getGlyphInfos(), pos = buf.getGlyphPositions();
  let x = 0;
  const glyphs = infos.map((info, i) => {
    const p = pos[i];
    const g = { gid: info.codepoint, name: F.hb.glyphName(info.codepoint), x: x + p.xOffset, y: p.yOffset, adv: p.xAdvance, cluster: info.cluster };
    x += p.xAdvance;
    return g;
  });
  return { glyphs, width: x };
}

/** Comparable key of a shaping result (to see whether a feature changes anything). */
export const shapeKey = (F: LoadedFont, text: string, state: FeatureState): string =>
  shape(F, text, state).glyphs.map((g) => `${g.gid}@${g.x},${g.y}`).join(' ');
