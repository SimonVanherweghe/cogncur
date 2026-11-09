// OpenType features of the font, with the Dutch texts shown on the site, and the
// shareable config codes: "cogncur: ss03 ss08 -kern" (text) and "cogncur-ss03-ss08-nokern" (link).
// Texts paraphrase the designer's own documentation (upstream/documentation/customization.html);
// the example words are hers.

export type Group = 'base' | 'lower' | 'upper' | 'num';

export interface Feature {
  tag: string;
  group: Group;
  name: string;
  desc: string;
  ex: string;
  on?: boolean;
  warn?: string;
  needs?: string[];
}

export type FeatureState = Record<string, boolean>;

export const GROUPS: { id: Group; title: string; note?: string }[] = [
  { id: 'base', title: 'Altijd aan', note: 'In Google Docs staan deze altijd aan. Uitzetten kan hier alleen om te vergelijken.' },
  { id: 'lower', title: 'Kleine letters' },
  { id: 'upper', title: 'Hoofdletters' },
  { id: 'num', title: 'Cijfers' },
];

export const FEATURES: Feature[] = [
  { tag: 'calt', group: 'base', on: true, name: 'Verbindingen tussen de letters', desc: 'Kiest voor elke letter de juiste instreek, verbinding en uithaal. Zonder deze optie staan de letters los.', ex: 'minimum' },
  { tag: 'kern', group: 'base', on: true, name: 'Spatiëring (kerning)', desc: 'Fijnregeling van de ruimte tussen bepaalde letters.', ex: 'Tom Vos' },
  { tag: 'ss01', group: 'lower', name: 'Geen instreken vanaf de basislijn', desc: 'Korte instreken aan het begin van een woord; geen instreek bij a, c, d, g, o, q en de moderne t.', ex: 'abcde' },
  { tag: 'ss02', group: 'lower', name: 'Geen uithalen aan s, p en ß', desc: 'Het ‘staartje’ aan het einde van s, p en ß verdwijnt.', ex: 'kiss rap fuß' },
  { tag: 'ss03', group: 'lower', name: 'Kortere stokken', desc: 'Stokken boven en onder de lijnen zijn 2/3 zo lang als lussen. Niet voor de gewone t.', ex: 'puddle' },
  { tag: 'ss04', group: 'lower', name: 'f en q: andere verbinding', desc: 'f verbindt met een boog vanuit het midden, q verbindt vanaf onderaan.', ex: 'ffqu' },
  { tag: 'ss05', group: 'lower', name: 'f en q: met penlift', desc: 'Na f en q wordt de pen opgetild. Combineert met ss04 en ss03.', ex: 'ffqu' },
  { tag: 'ss06', group: 'lower', name: 's met een buikje', desc: 'Een s met een bolle onderkant in plaats van de slanke s.', ex: 'kiss' },
  { tag: 'ss07', group: 'lower', name: 'Drukletter-r', desc: 'Een r die meer op de drukletter lijkt, in plaats van de traditionele schrijf-r.', ex: 'err' },
  { tag: 'ss08', group: 'lower', name: 'Moderne t', desc: 'De bekende drukletter-t. Standaard volgt de t de Duitse en Nederlandse traditie, zonder penlift.', ex: 'toot' },
  { tag: 'ss09', group: 'lower', name: 'Moderne t met rechte verbinding', desc: 'Rechte verbinding naar de moderne t, zoals veel Nederlandse methodes.', warn: 'Werkt alleen samen met ss08.', needs: ['ss08'], ex: 'toot' },
  { tag: 'ss11', group: 'lower', name: 'r en z beginnen met een hoek', desc: 'r en z (en Z) beginnen met een hoek in plaats van een boog tegen de middellijn.', ex: 'rz Z' },
  { tag: 'ss12', group: 'lower', name: 'Ronde verbindingen (onderbogen)', desc: 'Rechte stukjes in verbindingen worden bogen.', warn: 'De ontwerper raadt dit af.', ex: 'impunity' },
  { tag: 'ss13', group: 'lower', name: 'y begint met een hoek', desc: 'y begint met een hoek, zoals i; geldt ook voor de ij.', ex: 'yummy' },
  { tag: 'ss14', group: 'lower', name: 'w begint met een boog', desc: 'w begint met een boog, zoals v.', ex: 'wow' },
  { tag: 'ss15', group: 'lower', name: 'p begint met een boog', desc: 'p begint met een boog, zoals n.', ex: 'pup' },
  { tag: 'ss16', group: 'lower', name: 'Open p', desc: 'p zonder gesloten lus; verbindt zoals de n.', ex: 'pup' },
  { tag: 'ss19', group: 'upper', name: 'C, G en L zonder beginlus', desc: 'Eenvoudigere hoofdletters C, G en L.', ex: 'Cc Gg Ll' },
  { tag: 'ss20', group: 'upper', name: 'A, M en N als grote schrijfletters', desc: 'A, M en N lijken op vergrote kleine letters.', ex: 'Aa Mm Nn' },
  { tag: 'ss17', group: 'num', name: 'Cijfervarianten 1', desc: 'Andere vormen voor sommige cijfers. Met ss18 samen ontstaan bij 4 en 7 nog andere vormen.', ex: '1234567890' },
  { tag: 'ss18', group: 'num', name: 'Cijfervarianten 2', desc: 'Andere vormen voor sommige cijfers.', ex: '1234567890' },
  { tag: 'tnum', group: 'num', name: 'Even brede cijfers', desc: 'Alle cijfers even breed, handig voor rekenopgaven onder elkaar.', ex: '1111 2020' },
  { tag: 'onum', group: 'num', name: 'Mediaevalcijfers', desc: 'Cijfers met stokken boven en onder de lijn, zoals in lopende tekst.', ex: '1234567890' },
];

export const BY_TAG: Record<string, Feature> = Object.fromEntries(FEATURES.map((f) => [f.tag, f]));
export const STYLISTIC = FEATURES.filter((f) => f.tag.startsWith('ss'));

export const defaults = (): FeatureState => Object.fromEntries(FEATURES.map((f) => [f.tag, !!f.on]));

const changed = (state: FeatureState) => FEATURES.filter((f) => !!state[f.tag] !== !!f.on);

/** Text form, for issues and comments: "cogncur: ss03 ss08 -kern" (only what differs from the default). */
export function encode(state: FeatureState): string {
  const toks = changed(state).map((f) => (state[f.tag] ? '' : '-') + f.tag);
  return 'cogncur: ' + (toks.length ? toks.join(' ') : 'standaard');
}

/** Link form, for URL hashes: "cogncur-ss03-ss08-nokern" (artifacts and some chats only pass plain names). */
export function linkCode(state: FeatureState): string {
  const toks = changed(state).map((f) => (state[f.tag] ? '' : 'no') + f.tag);
  return 'cogncur' + (toks.length ? '-' + toks.join('-') : '');
}

/** Accepts both forms (and "#…", "standaard"). Unknown tokens are returned, not thrown. */
export function decode(str: string | null | undefined): { state: FeatureState; unknown: string[] } {
  const state = defaults();
  const unknown: string[] = [];
  const s = (str ?? '').trim().replace(/^#/, '');
  const toks = /^cogncur(-|$)/i.test(s)
    ? s.slice('cogncur'.length).split('-').filter(Boolean).map((t) => t.toLowerCase())
        .map((t) => (/^no[a-z0-9]{4}$/.test(t) && BY_TAG[t.slice(2)] ? '-' + t.slice(2) : t))
    : s.replace(/^cogncur\s*:?\s*/i, '').split(/[\s,;]+/).filter(Boolean).map((t) => t.toLowerCase());
  for (const t of toks) {
    const neg = t.startsWith('-');
    const tag = neg ? t.slice(1) : t;
    if (tag === 'standaard' || tag === 'default') continue;
    if (BY_TAG[tag]) state[tag] = !neg;
    else unknown.push(t);
  }
  return { state, unknown };
}

/** CSS font-feature-settings for text set in the web font. */
export const cssFeatures = (state: FeatureState): string =>
  FEATURES.map((f) => `"${f.tag}" ${state[f.tag] ? 1 : 0}`).join(', ');

/** Warnings for combinations that don't do what people expect. */
export function warnings(state: FeatureState): string[] {
  const out: string[] = [];
  if (state.ss09 && !state.ss08) out.push('ss09 werkt alleen samen met ss08.');
  if (!state.calt) out.push('Zonder calt staan de letters los.');
  return out;
}
