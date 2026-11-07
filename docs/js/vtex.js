// Shared code for the site: font loading + HarfBuzz shaping, drawing on writing
// lines (same zones as scripts/render_sample.py), the "vtex:" config codes from
// tools/live.html, and the feedback button that opens a pre-filled GitHub issue.
import * as hb from 'https://cdn.jsdelivr.net/npm/harfbuzzjs@1.6.3/dist/index.mjs';

export const UPM = 2048, ASC = 1768, DESC = 703;
export const XH = 682, ASCENDER = 1364, DESCENDER = 682;

// Feature list and Dutch texts: keep in sync with tools/live.html (FEATURES).
export const FEATURES = [
  { tag: 'calt', on: true, name: 'Verbindingen tussen de letters' },
  { tag: 'kern', on: true, name: 'Spatiëring (kerning)' },
  { tag: 'ss01', name: 'Geen instreken vanaf de basislijn' },
  { tag: 'ss02', name: 'Geen uithalen aan s, p en ß' },
  { tag: 'ss03', name: 'Kortere stokken' },
  { tag: 'ss04', name: 'f en q: andere verbinding' },
  { tag: 'ss05', name: 'f en q: met penlift' },
  { tag: 'ss06', name: 's met een buikje' },
  { tag: 'ss07', name: 'Drukletter-r' },
  { tag: 'ss08', name: 'Moderne t' },
  { tag: 'ss09', name: 'Moderne t met rechte verbinding' },
  { tag: 'ss11', name: 'r en z beginnen met een hoek' },
  { tag: 'ss12', name: 'Ronde verbindingen (onderbogen)' },
  { tag: 'ss13', name: 'y begint met een hoek' },
  { tag: 'ss14', name: 'w begint met een boog' },
  { tag: 'ss15', name: 'p begint met een boog' },
  { tag: 'ss16', name: 'Open p' },
  { tag: 'ss17', name: 'Cijfervarianten 1' },
  { tag: 'ss18', name: 'Cijfervarianten 2' },
  { tag: 'ss19', name: 'C, G en L zonder beginlus' },
  { tag: 'ss20', name: 'A, M en N als grote schrijfletters' },
  { tag: 'tnum', name: 'Even brede cijfers' },
  { tag: 'onum', name: 'Mediaevalcijfers' },
];
const BY_TAG = Object.fromEntries(FEATURES.map(f => [f.tag, f]));
export const defaults = () => Object.fromEntries(FEATURES.map(f => [f.tag, !!f.on]));

// ---------- config codes: "vtex: ss03 ss08 -kern" and the link form "vtex-ss03-ss08-nokern"
export function encode(state) {
  const t = FEATURES.filter(f => !!state[f.tag] !== !!f.on).map(f => (state[f.tag] ? '' : '-') + f.tag);
  return 'vtex: ' + (t.length ? t.join(' ') : 'standaard');
}
export function linkCode(state) {
  const t = FEATURES.filter(f => !!state[f.tag] !== !!f.on).map(f => (state[f.tag] ? '' : 'no') + f.tag);
  return 'vtex' + (t.length ? '-' + t.join('-') : '');
}
export function decode(str) {
  const next = defaults();
  let s = (str || '').trim().replace(/^#/, '');
  const toks = /^vtex(-|$)/i.test(s)
    ? s.slice(4).split('-').filter(Boolean).map(t => t.toLowerCase())
      .map(t => (/^no[a-z0-9]{4}$/.test(t) && BY_TAG[t.slice(2)]) ? '-' + t.slice(2) : t)
    : s.replace(/^vtex\s*:?\s*/i, '').split(/[\s,;]+/).filter(Boolean).map(t => t.toLowerCase());
  for (const t of toks) {
    const neg = t.startsWith('-'), tag = neg ? t.slice(1) : t;
    if (BY_TAG[tag]) next[tag] = !neg;
  }
  return next;
}
// CSS for the same state (for text set in the web font).
export const cssFeatures = state => FEATURES.map(f => `"${f.tag}" ${state[f.tag] ? 1 : 0}`).join(', ');

// ---------- site data
let buildP;
export const build = () => (buildP ||= fetch('data/build.json').then(r => r.json()).catch(() => ({})));

// ---------- font
let fontP;
export function loadFont() {
  fontP ||= (async () => {
    const r = await fetch('fonts/Vtex-Regular.ttf');
    if (!r.ok) throw new Error('Lettertype niet gevonden (fonts/Vtex-Regular.ttf).');
    const data = await r.arrayBuffer();
    const face = new FontFace('Vtex', data.slice(0), {
      ascentOverride: `${(ASC / UPM * 100).toFixed(4)}%`,
      descentOverride: `${(DESC / UPM * 100).toFixed(4)}%`,
      lineGapOverride: '0%',
    });
    await face.load();
    document.fonts.add(face);
    const font = new hb.Font(new hb.Face(new hb.Blob(data)));
    return { font, pathCache: new Map() };
  })();
  return fontP;
}

export function shape(F, text, state) {
  const buf = new hb.Buffer();
  buf.addText(text);
  buf.guessSegmentProperties();
  hb.shape(F.font, buf, FEATURES.map(f => new hb.Feature(f.tag, state[f.tag] ? 1 : 0)));
  const infos = buf.getGlyphInfos(), pos = buf.getGlyphPositions();
  let x = 0;
  const glyphs = infos.map((info, i) => {
    const g = { gid: info.codepoint, x: x + pos[i].xOffset, y: pos[i].yOffset, cluster: info.cluster };
    x += pos[i].xAdvance;
    return g;
  });
  return { glyphs, width: x };
}
const glyphPath = (F, gid) => {
  if (!F.pathCache.has(gid)) F.pathCache.set(gid, new Path2D(F.font.glyphToPath(gid) || ''));
  return F.pathCache.get(gid);
};
// Same shaping, as a comparable key (to see whether a feature changes anything).
export const shapeKey = (F, text, state) => shape(F, text, state).glyphs.map(g => `${g.gid}@${g.x},${g.y}`).join(' ');

// ---------- drawing on writing lines (mirrors scripts/render_sample.py)
const PAPER = '#FAFCFF', RULE = '#A9C3E8', RULE_STRONG = '#6F93C9', MARGIN = '#E8838F', INK = '#1B2433';

/* lines: [{text, state, label?}]. Returns a canvas at device resolution.
   caption: small text in the bottom-right corner (version + config), so a pasted image explains itself. */
export function renderLines(F, lines, { size = 96, caption = '', maxWidth = Infinity, ink = INK } = {}) {
  const s = size / UPM;
  const rowH = Math.round((ASC + DESC + 250) * s), baseY = Math.round((ASC + 120) * s);
  const shaped = lines.map(l => shape(F, l.text, l.state));
  const labelW = lines.some(l => l.label) ? Math.max(...lines.map(l => (l.label || '').length)) * size * 0.16 + size * 0.3 : 0;
  const padL = Math.round(size * 0.6 + labelW + size * 0.3), padR = Math.round(size * 0.4);
  let width = Math.max(...shaped.map(sh => sh.width * s), size) + padL + padR;
  width = Math.min(width, maxWidth);
  const capH = caption ? Math.round(Math.max(13, size * 0.16) * 1.8) : 0;
  const height = rowH * lines.length + Math.round(size * 0.2) + capH;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const cv = document.createElement('canvas');
  cv.width = Math.ceil(width * dpr); cv.height = Math.ceil(height * dpr);
  cv.style.width = width + 'px'; cv.style.aspectRatio = `${width} / ${height}`;
  const ctx = cv.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.fillStyle = PAPER; ctx.fillRect(0, 0, width, height);
  const mx = Math.round(size * 0.6 + labelW);
  ctx.strokeStyle = MARGIN; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(mx, 0); ctx.lineTo(mx, height - capH); ctx.stroke();
  lines.forEach((l, i) => {
    const top = i * rowH, base = top + baseY;
    for (const [units, col, w, dash] of [[ASCENDER, RULE, 1, false], [XH, RULE, 1, true], [0, RULE_STRONG, 2, false], [-DESCENDER, RULE, 1, false]]) {
      ctx.strokeStyle = col; ctx.lineWidth = w; ctx.setLineDash(dash ? [6, 6] : []);
      const y = Math.round(base - units * s) + (w === 1 ? 0.5 : 0);
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
    }
    ctx.setLineDash([]);
    if (l.label) {
      ctx.fillStyle = '#5B6577';
      ctx.font = `${Math.max(12, size * 0.16)}px "Atkinson Hyperlegible", system-ui, sans-serif`;
      ctx.textAlign = 'right';
      ctx.fillText(l.label, mx - size * 0.12, base);
    }
    ctx.fillStyle = l.ink || ink;
    for (const g of shaped[i].glyphs) {
      ctx.save();
      ctx.translate(padL + g.x * s, base - g.y * s);
      ctx.scale(s, -s);
      ctx.fill(glyphPath(F, g.gid));
      ctx.restore();
    }
  });
  if (caption) {
    ctx.fillStyle = '#5B6577';
    ctx.font = `${Math.max(13, size * 0.16)}px ui-monospace, Menlo, Consolas, monospace`;
    ctx.textAlign = 'right';
    ctx.fillText(caption, width - 10, height - capH * 0.35);
  }
  return cv;
}

// SVG element on the page → canvas (inlines the computed styles that matter, since
// the page's stylesheet doesn't travel with a serialized SVG).
const SVG_PROPS = ['fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'stroke-dashoffset', 'stroke-linecap', 'stroke-linejoin',
  'opacity', 'fill-opacity', 'stroke-opacity', 'display', 'visibility', 'font-size', 'font-family'];
export async function svgToCanvas(svg, { background = PAPER, scale = 2, caption = '' } = {}) {
  const clone = svg.cloneNode(true);
  const src = [svg, ...svg.querySelectorAll('*')], dst = [clone, ...clone.querySelectorAll('*')];
  src.forEach((el, i) => {
    const cs = getComputedStyle(el);
    dst[i].setAttribute('style', SVG_PROPS.map(p => `${p}:${cs.getPropertyValue(p)}`).join(';'));
  });
  const box = svg.getBoundingClientRect();
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clone.setAttribute('width', box.width); clone.setAttribute('height', box.height);
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], { type: 'image/svg+xml' }));
  try {
    const img = new Image();
    await new Promise((ok, bad) => { img.onload = ok; img.onerror = bad; img.src = url; });
    const capH = caption ? 28 : 0;
    const cv = document.createElement('canvas');
    cv.width = Math.ceil(box.width * scale); cv.height = Math.ceil((box.height + capH) * scale);
    const ctx = cv.getContext('2d');
    ctx.scale(scale, scale);
    ctx.fillStyle = background; ctx.fillRect(0, 0, box.width, box.height + capH);
    ctx.drawImage(img, 0, 0, box.width, box.height);
    if (caption) {
      ctx.fillStyle = '#5B6577'; ctx.font = '13px ui-monospace, Menlo, Consolas, monospace'; ctx.textAlign = 'right';
      ctx.fillText(caption, box.width - 10, box.height + 18);
    }
    return cv;
  } finally { URL.revokeObjectURL(url); }
}

// ---------- feedback
export const versionText = b => [b.version && `versie ${b.version}`, b.commit, b.date].filter(Boolean).join(' · ');

// Public link to what is on screen now: the site URL (if known) + this page + its hash.
export function shareLink(b) {
  const page = location.pathname.split('/').pop() || 'index.html';
  try { return b.siteUrl ? new URL(page + location.hash, b.siteUrl).href : location.href; }
  catch (e) { return location.href; }
}

/* Opens a dialog: the snapshot is copied to the clipboard right away (inside the click,
   which Safari requires), then a link opens the pre-filled form on GitHub.
   opts: { template, title, fields: {id: value}, snapshot: () => Promise<canvas> }
   (template, title and fields may also be promises). */
export async function feedback(opts) {
  // No await before clipboard.write(): Safari only allows it synchronously inside the click.
  const canvasP = opts.snapshot ? Promise.resolve().then(opts.snapshot) : Promise.resolve(null);
  const blobP = canvasP.then(cv => cv && new Promise(ok => cv.toBlob(ok, 'image/png')));
  let copied = false;
  const copyP = (async () => {
    if (!opts.snapshot || !navigator.clipboard || !window.ClipboardItem) return false;
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blobP })]);
    return true;
  })().then(ok => (copied = ok), () => false);

  // title and fields may be promises (the tool pages gather them asynchronously).
  const [b, template, title, given] = await Promise.all([build(), opts.template, opts.title, opts.fields]);
  const fields = Object.assign({ versie: versionText(b), link: shareLink(b) }, given);
  const q = new URLSearchParams({ template, title: title || '' });
  for (const [k, v] of Object.entries(fields)) if (v) q.set(k, String(v).slice(0, 1500));
  const url = `https://github.com/${b.repo || 'SimonVanherweghe/cogncur-tex'}/issues/new?${q}`;

  const dlg = feedbackDialog();
  dlg.querySelector('.fb-open').href = url;
  const img = dlg.querySelector('.fb-preview'), step = dlg.querySelector('.fb-step1');
  img.hidden = true; step.textContent = opts.snapshot ? 'Afbeelding maken…' : '';
  dlg.querySelector('.fb-download').hidden = true;
  dlg.showModal();
  const blob = await blobP.catch(() => null);
  await copyP;
  if (blob) {
    const objUrl = URL.createObjectURL(blob);
    img.src = objUrl; img.hidden = false;
    const dl = dlg.querySelector('.fb-download');
    dl.href = objUrl; dl.download = `vtex-feedback-${Date.now()}.png`; dl.hidden = false;
  }
  step.innerHTML = !opts.snapshot ? ''
    : copied ? '✅ De afbeelding is <strong>gekopieerd</strong>. Plak ze op GitHub in het vak <em>Afbeelding</em> met <kbd>Cmd</kbd>+<kbd>V</kbd> (Mac) of <kbd>Ctrl</kbd>+<kbd>V</kbd> (Windows).'
    : blob ? 'Kopiëren lukte niet in deze browser. Bewaar de afbeelding met de knop hieronder en sleep ze op GitHub in het vak <em>Afbeelding</em>.'
    : 'Er kon geen afbeelding gemaakt worden. Je kan op GitHub zelf een schermafbeelding toevoegen.';
}

let dialogEl;
function feedbackDialog() {
  if (dialogEl) return dialogEl;
  dialogEl = document.createElement('dialog');
  dialogEl.className = 'fb-dialog';
  dialogEl.innerHTML = `
    <form method="dialog" class="fb-close-form"><button class="fb-close" aria-label="Sluiten">×</button></form>
    <h2>Feedback geven</h2>
    <p class="fb-step1" role="status"></p>
    <img class="fb-preview" alt="Voorbeeld van de afbeelding" hidden>
    <p>Op GitHub staat het formulier al ingevuld met het teken, de instellingen, de versie en een link naar dit scherm. Jij schrijft alleen wat je ziet.</p>
    <div class="fb-actions">
      <a class="fb-open btn primary" target="_blank" rel="noopener">Formulier openen op GitHub ↗</a>
      <a class="fb-download btn" hidden>Afbeelding bewaren</a>
    </div>
    <p class="fb-note">Je hebt een GitHub-account nodig. Lukt het niet? Laat het Simon weten.</p>`;
  document.body.appendChild(dialogEl);
  dialogEl.addEventListener('click', e => { if (e.target === dialogEl) dialogEl.close(); });
  dialogEl.querySelector('.fb-open').addEventListener('click', () => setTimeout(() => dialogEl.close(), 300));
  return dialogEl;
}

// ---------- helpers
export const $ = id => document.getElementById(id);
export const hexU = c => 'U+' + c.codePointAt(0).toString(16).toUpperCase().padStart(4, '0');
export function hashParams() { return new URLSearchParams(location.hash.slice(1)); }
export function setHash(params) {
  const h = '#' + [...params].filter(([, v]) => v !== '' && v != null).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
  try { history.replaceState(null, '', h); } catch (e) { /* sandboxed */ }
}
