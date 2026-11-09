// Character info (public/data/tekens.json per version, see version-data.ts) and how it is shown.

export type Status = 'origineel' | 'samengesteld' | 'nieuw' | 'schets';
export type CharGroup = 'lower' | 'upper' | 'digit' | 'punct' | 'symbol' | 'mark';

export interface CharInfo {
  c: string;
  name: string;
  group: CharGroup;
  status: Status;
  base?: string;
  accent?: string;
  inferred?: boolean;
}

export { BUILD, REPO_URL, versionText, type BuildInfo } from './build';

export const GROUP_NAMES: Record<CharGroup, string> = {
  lower: 'Kleine letters', upper: 'Hoofdletters', digit: 'Cijfers', punct: 'Leestekens', symbol: 'Symbolen', mark: 'Accenten',
};

export const STATUS_TEXT: Record<Status, [label: string, desc: string]> = {
  origineel: ['Origineel', 'Uit het originele Cogncur.'],
  samengesteld: ['Samengesteld', 'Nieuw: letter en accent uit het originele Cogncur, automatisch samengezet.'],
  schets: ['Schets', 'Nieuwe vorm, nog niet goedgekeurd. Er loopt een vraag aan de ontwerper.'],
  nieuw: ['Nieuw', 'Nieuw teken, gemaakt uit vormen van het originele Cogncur.'],
};

export const hexU = (c: string): string => 'U+' + c.codePointAt(0)!.toString(16).toUpperCase().padStart(4, '0');

/** Combining marks are shown on a dotted circle. */
export const showChar = (c: string): string => (/\p{Mn}/u.test(c) ? '◌' + c : c);
