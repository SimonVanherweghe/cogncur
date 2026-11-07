// The designer's stroke-order model (upstream webapps/imgen/cogncur_shapes.svg, stripped by
// scripts/export_web.py). Each letter is a <g id="letter-…"> with ordered <path id="stroke-…">
// elements in font units (y up, baseline 0, x-height 683, ascender 1365, descender -683).
// data-lift = pen lifted before this stroke, data-dot = the stroke is a dot,
// data-entry = the entry stroke from the baseline. class="overlap" is not part of the route.
// Ids: "a", "a-alt2" (a variant), "a-noentry" / "a-alt2-noentry" (without the entry stroke).

export interface StrokeDef { d: string; entry: boolean; lift: boolean; dot: boolean }
export interface LetterDef { width: number; strokes: StrokeDef[] }
export type Letters = Map<string, LetterDef>;

export interface LetterChoice { base: string; alt: string; entry: boolean }

export function parseShapes(text: string): Letters {
  const letters: Letters = new Map();
  const doc = new DOMParser().parseFromString(text.replace(/^﻿/, ''), 'image/svg+xml');
  for (const g of doc.querySelectorAll('g[id^="letter-"]')) {
    const id = g.id.slice(7);
    if (letters.has(id) || id === 'empty') continue;     // the file repeats a few ids; first one wins
    const strokes = [...g.querySelectorAll('.strokes > path')]
      .filter((p) => (p.id || '').startsWith('stroke') && p.getAttribute('class') !== 'overlap')
      .map((p) => ({ d: p.getAttribute('d') ?? '', entry: p.hasAttribute('data-entry'), lift: p.hasAttribute('data-lift'), dot: p.hasAttribute('data-dot') }));
    letters.set(id, { width: +(g.getAttribute('data-width') ?? 0) || 1000, strokes });
  }
  return letters;
}

export const baseOf = (id: string): string => id.replace(/-noentry$/, '').replace(/-alt\d+$/, '');

/** The model id for a choice; "without entry stroke" only where the model has such a version. */
export function letterId(letters: Letters, c: LetterChoice): string {
  const core = c.base + (c.alt ? '-' + c.alt : '');
  return !c.entry && letters.has(core + '-noentry') ? core + '-noentry' : core;
}

/** Read an id back into a choice (null if the model doesn't have it). */
export function choiceOf(letters: Letters, id: string): LetterChoice | null {
  if (!id || !letters.has(id)) return null;
  const m = id.match(/-(alt\d+)/);
  return { base: baseOf(id), alt: m ? m[1] : '', entry: !id.endsWith('-noentry') };
}

/** The variants of a letter: '' (standard), 'alt1', 'alt2', … in order. */
export function variantsOf(letters: Letters, base: string): string[] {
  return [...letters.keys()]
    .filter((id) => baseOf(id) === base && !id.endsWith('-noentry'))
    .map((id) => (id === base ? '' : id.slice(base.length + 1)))
    .sort((a, b) => (+a.slice(3) || 0) - (+b.slice(3) || 0));
}

/** Letters for the picker: lowercase (incl. ij) in model order, capitals alphabetically. */
export function pickerKeys(letters: Letters): { lower: string[]; upper: string[] } {
  const bases = [...new Set([...letters.keys()].map(baseOf))];
  return { lower: bases.filter((b) => /^[a-z]+$/.test(b)), upper: bases.filter((b) => /^[A-Z]$/.test(b)).sort() };
}
