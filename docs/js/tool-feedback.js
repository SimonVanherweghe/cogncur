// Feedback button for the tool pages (tools/live.html, woorden.html, schrijven.html),
// which scripts/build_site.py copies into the site. The tools stay unchanged: this
// reads what they show from their DOM, their URL hash and window.schrijfroute.
import { loadFont, build, renderLines, svgToCanvas, feedback, encode, decode, defaults, versionText } from './vtex.js';

const tool = document.querySelector('script[data-tool]').dataset.tool;   // module scripts have no currentScript
const $ = id => document.getElementById(id);
const short = (s, n = 40) => (s.length > n ? s.slice(0, n - 1) + '…' : s);
// Pause an animation (woorden/schrijven) so the snapshot shows the frame the person stopped at.
const pause = () => { const b = $('play'); if (b && /pauze/i.test(b.textContent)) b.click(); };

async function live() {
  const state = location.hash.toLowerCase().startsWith('#vtex') ? decode(location.hash) : defaults();
  const text = $('text').value.replace(/\s+$/, '');
  const lines = text.split('\n').slice(0, 8);
  const [F, b] = await Promise.all([loadFont(), build()]);
  return {
    template: 'algemeen.yml',
    title: `[Opmerking] ${short(lines[0] || '')}`,
    fields: { tekst: text, instellingen: encode(state) },
    snapshot: () => renderLines(F, lines.map(t => ({ text: t, state })), { size: 90, caption: `${versionText(b)} · ${encode(state)}` }),
  };
}

function woordenState() {
  const s = defaults();
  for (const t of window.schrijfroute?.state?.feats || []) s[t] = true;
  return s;
}
async function woorden() {
  pause();
  const b = await build();
  const state = woordenState(), text = $('text').value.trim();
  return {
    template: 'schrijfroute.yml',
    title: `[Schrijfroute] ${short(text)}`,
    fields: { tekst: text, instellingen: encode(state) },
    snapshot: () => svgToCanvas($('stage'), { caption: `${versionText(b)} · ${encode(state)} · ${$('time').textContent}` }),
  };
}
async function letters() {
  pause();
  const b = await build();
  const letter = $('badge').textContent.trim();
  const variant = $('variant')?.selectedOptions?.[0]?.textContent || '';
  return {
    template: 'schrijfroute.yml',
    title: `[Schrijfroute] letter ${letter}`,
    fields: { tekst: `${letter}${variant ? ` (${variant})` : ''}`, instellingen: 'schrijfmodel van de ontwerper (per letter)' },
    snapshot: () => svgToCanvas($('stage'), { caption: `${versionText(b)} · ${$('time').textContent}` }),
  };
}

const MAKERS = { live, woorden, letters };
// Build the options inside the click, but call feedback() without awaiting first:
// the clipboard write must start in the same gesture (Safari).
$('fb-nav').addEventListener('click', () => {
  const o = MAKERS[tool]();
  feedback({
    template: o.then(x => x.template),
    title: o.then(x => x.title),
    fields: o.then(x => x.fields),
    snapshot: () => o.then(x => x.snapshot()),
  });
});
