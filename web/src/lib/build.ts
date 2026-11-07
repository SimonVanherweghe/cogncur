// Version info written by scripts/export_web.py (public/data/build.json). Kept apart from
// site.ts so pages that only need the version don't bundle the whole character list.
import buildJson from '../../public/data/build.json';

export interface BuildInfo {
  repo: string;
  /** Characters changed since the previous release (outline or width), if there is one. */
  changedSince?: { version: string; chars: string[] };
  siteUrl: string;
  version: string;
  commit: string;
  date: string;
  counts: Record<'origineel' | 'samengesteld' | 'nieuw' | 'schets' | 'total', number>;
}

export const BUILD = buildJson as BuildInfo;
export const REPO_URL = `https://github.com/${BUILD.repo}`;

/** What the page shows (embedded by layouts/Base.astro): version label + its build info. */
export interface PageData { slug: string; label: string; build: BuildInfo }

export function pageData(): PageData | null {
  if (typeof document === 'undefined') return null;
  const el = document.getElementById('page-data');
  return el ? (JSON.parse(el.textContent ?? 'null') as PageData) : null;
}

/** "Versie 1.001 · abc1234 · 2026-11-20" or "In ontwikkeling (lettertype 1.001) · …": goes into every feedback issue. */
export function versionText(page: PageData | null = pageData()): string {
  const b = page?.build ?? BUILD;
  const label = !page ? `versie ${b.version}` : page.slug.startsWith('v') ? page.label : `${page.label} (lettertype ${b.version})`;
  return [label, b.commit, b.date].filter(Boolean).join(' · ');
}
