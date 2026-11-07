// Text on writing lines, drawn on a canvas with HarfBuzz. Same zones as scripts/render_sample.py:
// ascender 1364, x-height 682 (dashed), baseline 0 (strong), descender -682; red margin.
import type { FeatureState } from './features';
import { ASC, ASCENDER, DESC, DESCENDER, UPM, XH, shape, type LoadedFont } from './font';

export const PAPER = '#FAFCFF';
const RULE = '#A9C3E8', RULE_STRONG = '#6F93C9', MARGIN = '#E8838F', INK = '#1B2433', MUTED = '#5B6577';

export interface SheetLine { text: string; state: FeatureState; label?: string; ink?: string }
export interface SheetOptions { size?: number; caption?: string; ink?: string }

/** caption: small text bottom right (version + config), so a pasted image explains itself. */
export function renderLines(F: LoadedFont, lines: SheetLine[], { size = 96, caption = '', ink = INK }: SheetOptions = {}): HTMLCanvasElement {
  const s = size / UPM;
  const rowH = Math.round((ASC + DESC + 250) * s), baseY = Math.round((ASC + 120) * s);
  const shaped = lines.map((l) => shape(F, l.text, l.state));
  const hasLabels = lines.some((l) => l.label);
  const labelW = hasLabels ? Math.max(...lines.map((l) => (l.label ?? '').length)) * size * 0.16 + size * 0.3 : 0;
  const padL = Math.round(size * 0.6 + labelW + size * 0.3), padR = Math.round(size * 0.4);
  const width = Math.max(...shaped.map((sh) => sh.width * s), size) + padL + padR;
  const capH = caption ? Math.round(Math.max(13, size * 0.16) * 1.8) : 0;
  const height = rowH * lines.length + Math.round(size * 0.2) + capH;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  const cv = document.createElement('canvas');
  cv.width = Math.ceil(width * dpr);
  cv.height = Math.ceil(height * dpr);
  cv.style.width = `${width}px`;
  cv.style.aspectRatio = `${width} / ${height}`;
  const ctx = cv.getContext('2d')!;
  ctx.scale(dpr, dpr);
  ctx.fillStyle = PAPER;
  ctx.fillRect(0, 0, width, height);

  const mx = Math.round(size * 0.6 + labelW);
  ctx.strokeStyle = MARGIN;
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(mx, 0); ctx.lineTo(mx, height - capH); ctx.stroke();

  lines.forEach((l, i) => {
    const base = i * rowH + baseY;
    const rules: [number, string, number, boolean][] = [[ASCENDER, RULE, 1, false], [XH, RULE, 1, true], [0, RULE_STRONG, 2, false], [-DESCENDER, RULE, 1, false]];
    for (const [units, col, w, dash] of rules) {
      ctx.strokeStyle = col; ctx.lineWidth = w; ctx.setLineDash(dash ? [6, 6] : []);
      const y = Math.round(base - units * s) + (w === 1 ? 0.5 : 0);
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
    }
    ctx.setLineDash([]);
    if (l.label) {
      ctx.fillStyle = MUTED;
      ctx.font = `${Math.max(12, size * 0.16)}px "Atkinson Hyperlegible", system-ui, sans-serif`;
      ctx.textAlign = 'right';
      ctx.fillText(l.label, mx - size * 0.12, base);
    }
    ctx.fillStyle = l.ink ?? ink;
    for (const g of shaped[i].glyphs) {
      ctx.save();
      ctx.translate(padL + g.x * s, base - g.y * s);
      ctx.scale(s, -s);
      ctx.fill(F.path(g.gid));
      ctx.restore();
    }
  });

  if (caption) drawCaption(ctx, caption, width, height - capH * 0.35, Math.max(13, size * 0.16));
  return cv;
}

export function drawCaption(ctx: CanvasRenderingContext2D, text: string, right: number, y: number, px = 13): void {
  ctx.fillStyle = MUTED;
  ctx.font = `${px}px ui-monospace, Menlo, Consolas, monospace`;
  ctx.textAlign = 'right';
  ctx.fillText(text, right - 10, y);
}
