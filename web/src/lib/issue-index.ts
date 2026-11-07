// The issues fetched before the build (scripts/fetch-issues.ts), indexed by character, pair and word.
import data from '../generated/issues.json';
import { indexIssues, type IssuesFile } from './issues';

export const ISSUES = data as IssuesFile;
export const { byChar, byPair, byWord } = indexIssues(ISSUES.issues);

/** Issues about any word of a text (the word page). */
export function issuesForText(text: string) {
  const seen = new Map<number, (typeof ISSUES.issues)[number]>();
  for (const w of [text.trim(), ...text.split(/\s+/)]) for (const i of byWord.get(w) ?? []) seen.set(i.number, i);
  return [...seen.values()];
}
