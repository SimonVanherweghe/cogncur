// Version info written by scripts/export_web.py (public/data/build.json). Kept apart from
// site.ts so pages that only need the version don't bundle the whole character list.
import buildJson from '../../public/data/build.json';

export interface BuildInfo {
  repo: string;
  siteUrl: string;
  version: string;
  commit: string;
  date: string;
  counts: Record<'origineel' | 'samengesteld' | 'nieuw' | 'schets' | 'total', number>;
}

export const BUILD = buildJson as BuildInfo;
export const REPO_URL = `https://github.com/${BUILD.repo}`;

export const versionText = (b: BuildInfo = BUILD): string =>
  [b.version && `versie ${b.version}`, b.commit, b.date].filter(Boolean).join(' · ');
