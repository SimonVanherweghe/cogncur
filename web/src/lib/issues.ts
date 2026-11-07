// What each GitHub issue is about, so the site can show "Al gemeld" next to a character,
// a letter pair or a word. Used at build time by scripts/fetch-issues.ts and in the browser.
//
// Sources, in order:
//  - the issue forms (.github/ISSUE_TEMPLATE/*.yml): GitHub writes each field as "### <label>\n\n<value>",
//    with "_No response_" for an empty field
//  - the titles the website pre-fills: "[Teken] ď (U+010F)", "[Verbinding] oe", "[Schrijfroute] letter g"
//  - the decision issues of scripts/issues.py: a "<!-- beslissing:<id> -->" marker, and the characters
//    of that decision (data/decisions.json, written by scripts/export_web.py)

export interface IssueRef {
  number: number;
  title: string;
  state: 'open' | 'closed';
  url: string;
  labels: string[];
  milestone: string | null;
  closedAt: string | null;
  chars: string[];
  pairs: string[];
  words: string[];
}

export interface IssuesFile { fetchedAt: string | null; repo: string; error?: string; issues: IssueRef[] }
export type Decisions = Record<string, { title: string; chars: string }>;

/** The raw issue as the GitHub REST API returns it (only what we use). */
export interface ApiIssue {
  number: number;
  title: string;
  state: string;
  html_url: string;
  body?: string | null;
  labels: (string | { name?: string })[];
  milestone?: { title: string } | null;
  closed_at?: string | null;
  pull_request?: unknown;
}

/** Issue-form fields: label → value (empty and "_No response_" fields left out). */
export function formFields(body: string | null | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  const parts = (body ?? '').replace(/\r\n/g, '\n').split(/^### /m).slice(1);
  for (const part of parts) {
    const nl = part.indexOf('\n');
    const label = (nl < 0 ? part : part.slice(0, nl)).trim();
    const value = (nl < 0 ? '' : part.slice(nl + 1)).trim();
    if (label && value && value !== '_No response_') out[label] = value;
  }
  return out;
}

const firstChar = (s: string): string | null => {
  const c = [...s.trim()][0];
  return c && !/\s/.test(c) ? c : null;
};
const uniq = <T,>(xs: T[]): T[] => [...new Set(xs)];

/** Characters, pairs and words an issue is about. */
export function subjectsOf(issue: ApiIssue, decisions: Decisions = {}): Pick<IssueRef, 'chars' | 'pairs' | 'words'> {
  const f = formFields(issue.body);
  const chars: string[] = [], pairs: string[] = [], words: string[] = [];
  const title = issue.title.trim();

  // [Teken] ď (U+010F)  /  field "Teken": "ď (U+010F, dcaron, schets)"
  let m = title.match(/^\[Teken\]\s*(.+)$/u);
  for (const v of [m?.[1], f['Teken']]) { const c = v ? firstChar(v) : null; if (c) chars.push(c); }

  // [Verbinding] oe  /  field "Letters": "oe (in: oe noen ooee)"
  m = title.match(/^\[Verbinding\]\s*(\S+)/u);
  for (const v of [m?.[1], f['Letters']?.split(/\s+/)[0]]) if (v) pairs.push(v);

  // [Schrijfroute] hond / [Schrijfroute] letter g  /  field "Letter of woord": "g (standaard; model: g)"
  m = title.match(/^\[Schrijfroute\]\s*(?:letter\s+)?(.+)$/u);
  for (const v of [m?.[1], f['Letter of woord']]) {
    const w = v?.replace(/\s*\(.*$/s, '').replace(/…$/, '').trim();
    if (w) words.push(w);
  }

  // decision issues
  const marker = (issue.body ?? '').match(/<!--\s*beslissing:([^\s>]+)\s*-->/);
  if (marker && decisions[marker[1]]) chars.push(...[...decisions[marker[1]].chars]);

  return { chars: uniq(chars), pairs: uniq(pairs), words: uniq(words) };
}

export function toRef(issue: ApiIssue, decisions: Decisions = {}): IssueRef {
  return {
    number: issue.number,
    title: issue.title,
    state: issue.state === 'closed' ? 'closed' : 'open',
    url: issue.html_url,
    labels: issue.labels.map((l) => (typeof l === 'string' ? l : l.name ?? '')).filter(Boolean),
    milestone: issue.milestone?.title ?? null,
    closedAt: issue.closed_at ?? null,
    ...subjectsOf(issue, decisions),
  };
}

/** Lookup tables: character / pair / word → issues (open ones first, newest first). */
export function indexIssues(issues: IssueRef[]) {
  const add = (map: Map<string, IssueRef[]>, key: string, i: IssueRef) => {
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(i);
  };
  const byChar = new Map<string, IssueRef[]>(), byPair = new Map<string, IssueRef[]>(), byWord = new Map<string, IssueRef[]>();
  const sorted = [...issues].sort((a, b) => (a.state === b.state ? b.number - a.number : a.state === 'open' ? -1 : 1));
  for (const i of sorted) {
    for (const c of i.chars) add(byChar, c, i);
    for (const p of i.pairs) add(byPair, p, i);
    for (const w of i.words) add(byWord, w, i);
  }
  return { byChar, byPair, byWord };
}

export const openOnly = (list: IssueRef[] | undefined): IssueRef[] => (list ?? []).filter((i) => i.state === 'open');
