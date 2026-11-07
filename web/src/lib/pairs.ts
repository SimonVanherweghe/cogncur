// Letter sets for the pair table (pages/verbindingen.astro).
const LOWER = 'abcdefghijklmnopqrstuvwxyz', UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';

export const PAIR_SETS = {
  klein: ['Kleine letters', LOWER, LOWER],
  hoofd: ['Hoofdletter + kleine letter', UPPER, LOWER],
  accent: ['Met accenten', 'aeionu', 'áàâäãéèêëíïóöôúüñçšžčřđłąęőű'],
} as const satisfies Record<string, readonly [string, string, string]>;

export type PairSet = keyof typeof PAIR_SETS;

/** Default sample: the pair alone, between n's, after o and before e, doubled. */
export const contextFor = (p: string): string => `${p} n${p}n o${p}e ${p}${p}`;
