// Font versions on the site. "ontwikkeling" is the current state of main (public/fonts + public/data);
// every release has a frozen copy in public/versions/<slug>/ with the same layout (fonts/, data/),
// listed in public/data/releases.json (written by scripts/release.py).
import releasesJson from '../../public/data/releases.json';

export interface Release {
  version: string;         // "1.001"
  slug: string;            // "v1.001": folder and URL segment
  date: string;            // ISO date
  tag: string;             // git tag
  milestone: string | null;
  notes: { number: number; title: string }[];   // issues closed in the milestone
  changed: string[];       // characters whose outline or width changed since the previous release
  previous: string | null; // version it was compared with
}

export interface VersionInfo {
  slug: string;            // "ontwikkeling" or a release slug
  label: string;
  release: Release | null;
  latest: boolean;
}

export const DEV = 'ontwikkeling';
export const RELEASES = (releasesJson as Release[]).slice().sort((a, b) => b.version.localeCompare(a.version, undefined, { numeric: true }));
export const LATEST = RELEASES[0] ?? null;

/** What the site shows without a version in the URL: the latest release, or main while there is none. */
export const DEFAULT_SLUG = LATEST?.slug ?? DEV;

export function versionInfo(slug: string): VersionInfo {
  if (slug === DEV) return { slug, label: 'In ontwikkeling', release: null, latest: !LATEST };
  const r = RELEASES.find((x) => x.slug === slug);
  if (!r) throw new Error(`unknown version ${slug}`);
  return { slug, label: `Versie ${r.version}`, release: r, latest: r === LATEST };
}

export const ALL_VERSIONS: VersionInfo[] = [...(LATEST ? [versionInfo(LATEST.slug)] : []), versionInfo(DEV), ...RELEASES.slice(1).map((r) => versionInfo(r.slug))];

/** Folder (under the site base) with this version's fonts/ and data/. */
export const assetDir = (slug: string): string => (slug === DEV ? '' : `versions/${slug}/`);

/** getStaticPaths for a versioned page: the default (no segment), "ontwikkeling", every release. */
export function versionPaths() {
  return [undefined, DEV, ...RELEASES.map((r) => r.slug)].map((v) => ({ params: { v } }));
}

/** The slug for a route's [...v] parameter. */
export const slugOf = (v: string | undefined): string => v ?? DEFAULT_SLUG;
