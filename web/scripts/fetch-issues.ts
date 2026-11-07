// Fetch every issue of the repository and write src/generated/issues.json: what each issue is
// about (character, pair, word), its state and milestone. Runs before `astro build` and `astro dev`
// (npm prebuild/predev). In GitHub Actions it uses GITHUB_TOKEN; locally `gh auth token`.
// Without a token or network it writes an empty list and warns: the site then shows no
// "Al gemeld" information, but still builds.
//
//   node scripts/fetch-issues.ts
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { toRef, type ApiIssue, type Decisions, type IssuesFile } from '../src/lib/issues.ts';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'src/generated/issues.json');
const { repo } = JSON.parse(readFileSync(join(ROOT, 'public/data/build.json'), 'utf8')) as { repo: string };
const decisions = JSON.parse(readFileSync(join(ROOT, 'public/data/decisions.json'), 'utf8')) as Decisions;

function token(): string | null {
  if (process.env.GITHUB_TOKEN) return process.env.GITHUB_TOKEN;
  try {
    return execFileSync('gh', ['auth', 'token'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim() || null;
  } catch {
    return null;
  }
}

async function fetchAll(tok: string | null): Promise<ApiIssue[]> {
  const headers: Record<string, string> = { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' };
  if (tok) headers.Authorization = `Bearer ${tok}`;
  const all: ApiIssue[] = [];
  for (let page = 1; page < 50; page++) {
    const res = await fetch(`https://api.github.com/repos/${repo}/issues?state=all&per_page=100&page=${page}`, { headers });
    if (!res.ok) throw new Error(`GitHub API ${res.status} ${res.statusText}`);
    const batch = (await res.json()) as ApiIssue[];
    all.push(...batch.filter((i) => !i.pull_request));
    if (batch.length < 100) break;
  }
  return all;
}

function write(data: IssuesFile) {
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(data, null, 1) + '\n');
}

try {
  const issues = (await fetchAll(token())).map((i) => toRef(i, decisions));
  write({ fetchedAt: new Date().toISOString(), repo, issues });
  const linked = issues.filter((i) => i.chars.length || i.pairs.length || i.words.length).length;
  console.log(`issues: ${issues.length} fetched, ${linked} about a character, pair or word`);
} catch (e) {
  write({ fetchedAt: null, repo, error: (e as Error).message, issues: [] });
  console.warn(`issues: not fetched (${(e as Error).message}); the site shows no "Al gemeld" information`);
}
