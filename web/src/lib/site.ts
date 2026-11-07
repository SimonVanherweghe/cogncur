// Characters written by scripts/export_web.py (public/data/tekens.json), imported at build time.
import tekensJson from '../../public/data/tekens.json';

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
  issue?: { number: number; title: string; url: string };
}

export { BUILD, REPO_URL, versionText, type BuildInfo } from './build';

export const CHARS = (tekensJson as { chars: CharInfo[] }).chars;

export const GROUP_NAMES: Record<CharGroup, string> = {
  lower: 'Kleine letters', upper: 'Hoofdletters', digit: 'Cijfers', punct: 'Leestekens', symbol: 'Symbolen', mark: 'Accenten',
};

export const STATUS_TEXT: Record<Status, [label: string, desc: string]> = {
  origineel: ['Origineel', 'Getekend door de ontwerper van Cogncur.'],
  samengesteld: ['Samengesteld', 'Nieuw: letter en accent van de ontwerper, automatisch samengezet.'],
  schets: ['Schets', 'Nieuwe vorm, nog niet goedgekeurd. Er loopt een vraag aan de ontwerper.'],
  nieuw: ['Nieuw', 'Nieuw teken, gemaakt uit vormen van de ontwerper.'],
};

export const hexU = (c: string): string => 'U+' + c.codePointAt(0)!.toString(16).toUpperCase().padStart(4, '0');

/** Combining marks are shown on a dotted circle. */
export const showChar = (c: string): string => (/\p{Mn}/u.test(c) ? '◌' + c : c);
