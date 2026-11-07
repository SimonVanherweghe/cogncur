// Paths under the site's base (/cogncur-tex/ on GitHub Pages, also in `npm run dev`).

const BASE = import.meta.env.BASE_URL.replace(/\/?$/, '/');

/** URL of a file in public/, e.g. asset('fonts/Vtex-Regular.ttf'). */
export const asset = (path: string): string => BASE + path.replace(/^\//, '');

/** Link to another page of the site, e.g. page('tekens'). */
export const page = (name: string): string => (name === 'index' ? BASE : `${BASE}${name}/`);

/** Hash as key/value pairs: #teken=ď&code=vtex-ss03 */
export const hashParams = (): URLSearchParams => new URLSearchParams(location.hash.slice(1));

/** Replace the hash without a history entry; empty values are left out. */
export function setHash(pairs: [string, string | null | undefined][]): void {
  const parts = pairs.filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v as string)}`);
  try {
    history.replaceState(null, '', location.pathname + location.search + (parts.length ? '#' + parts.join('&') : ''));
  } catch {
    /* sandboxed */
  }
}
