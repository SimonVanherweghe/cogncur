// Build-time data per version (server only): the character list and build info of "ontwikkeling"
// (public/data/) and of every release (public/versions/<slug>/data/).
import devTekens from '../../public/data/tekens.json';
import devBuild from '../../public/data/build.json';
import type { BuildInfo } from './build';
import type { CharInfo } from './site';
import { DEV } from './versions';

const tekens = import.meta.glob<{ chars: CharInfo[] }>('../../public/versions/*/data/tekens.json', { eager: true, import: 'default' });
const builds = import.meta.glob<BuildInfo>('../../public/versions/*/data/build.json', { eager: true, import: 'default' });
const key = (slug: string, file: string) => `../../public/versions/${slug}/data/${file}`;

export function charsFor(slug: string): CharInfo[] {
  if (slug === DEV) return (devTekens as { chars: CharInfo[] }).chars;
  const t = tekens[key(slug, 'tekens.json')];
  if (!t) throw new Error(`no tekens.json for ${slug}`);
  return t.chars;
}

export function buildFor(slug: string): BuildInfo {
  if (slug === DEV) return devBuild as BuildInfo;
  const b = builds[key(slug, 'build.json')];
  if (!b) throw new Error(`no build.json for ${slug}`);
  return b;
}
