// The feedback button: copy a picture of what is on screen, then open a pre-filled GitHub issue.
// Forms: /.github/ISSUE_TEMPLATE/*.yml. GitHub fills form fields from query parameters named
// after the field ids (inputs/textareas only). Labels are set in the forms themselves: the
// `labels` URL parameter gives a 404 to anyone without triage rights.
import { BUILD, versionText } from './build';
import { showIssues } from './issue-list';
import type { IssueRef } from './issues';

export type Template = 'teken.yml' | 'verbinding.yml' | 'schrijfroute.yml' | 'algemeen.yml';
type Maybe<T> = T | Promise<T>;

export interface FeedbackRequest {
  template: Maybe<Template>;
  title: Maybe<string>;
  /** Form field id → value (teken, tekst, instellingen, link…). versie and link are added by default. */
  fields?: Maybe<Record<string, string | undefined>>;
  snapshot?: () => Maybe<HTMLCanvasElement | null>;
  /** Open issues about the same thing: listed first in the dialog, so people can react there. */
  existing?: IssueRef[];
}

const MAX_FIELD = 1500;   // keeps the whole URL far below GitHub's limit

/** The public address (GitHub Pages) of a page of this site, also when testing locally. */
export function publicLink(u: URL = new URL(location.href)): string {
  const rel = u.pathname.replace(import.meta.env.BASE_URL.replace(/\/$/, ''), '').replace(/^\//, '');
  try {
    return new URL(rel + u.search + u.hash, BUILD.siteUrl).href;
  } catch {
    return u.href;
  }
}

/** Public link to what is on screen now (page + query + hash). */
export const shareLink = (): string => publicLink();

export function issueUrl(template: Template, title: string, fields: Record<string, string | undefined>): string {
  const q = new URLSearchParams({ template, title });
  for (const [k, v] of Object.entries(fields)) if (v) q.set(k, v.slice(0, MAX_FIELD));
  return `https://github.com/${BUILD.repo}/issues/new?${q}`;
}

/** Call directly from a click handler: the clipboard write must start inside the gesture
    (Safari), so nothing is awaited before it; the PNG itself is passed as a promise. */
export function feedback(req: FeedbackRequest): void {
  const canvasP = req.snapshot ? Promise.resolve().then(req.snapshot) : Promise.resolve(null);
  const blobP = canvasP.then((cv) => (cv ? new Promise<Blob | null>((ok) => cv.toBlob(ok, 'image/png')) : null));
  let copyP: Promise<boolean> = Promise.resolve(false);
  if (req.snapshot && navigator.clipboard && 'ClipboardItem' in window) {
    try {
      const item = new ClipboardItem({ 'image/png': blobP.then((b) => b ?? Promise.reject(new Error('geen afbeelding'))) });
      copyP = navigator.clipboard.write([item]).then(() => true, () => false);
    } catch {
      copyP = Promise.resolve(false);
    }
  }
  void showDialog(req, blobP, copyP);
}

async function showDialog(req: FeedbackRequest, blobP: Promise<Blob | null>, copyP: Promise<boolean>): Promise<void> {
  const dlg = document.getElementById('fb-dialog') as HTMLDialogElement;
  const step = dlg.querySelector<HTMLElement>('[data-step]')!;
  const img = dlg.querySelector<HTMLImageElement>('[data-preview]')!;
  const open = dlg.querySelector<HTMLAnchorElement>('[data-open]')!;
  const save = dlg.querySelector<HTMLAnchorElement>('[data-save]')!;
  img.hidden = true;
  save.hidden = true;
  open.removeAttribute('href');
  open.setAttribute('aria-disabled', 'true');
  step.dataset.state = req.snapshot ? 'busy' : 'none';
  showIssues(dlg.querySelector<HTMLElement>('[data-existing]')!, (req.existing ?? []).filter((i) => i.state === 'open'));
  dlg.showModal();

  const [template, title, given] = await Promise.all([req.template, req.title, req.fields]);
  open.href = issueUrl(template, title, { versie: versionText(), link: shareLink(), ...given });
  open.removeAttribute('aria-disabled');

  const blob = await blobP.catch(() => null);
  const copied = await copyP;
  if (blob) {
    const url = URL.createObjectURL(blob);
    img.src = url;
    img.hidden = false;
    save.href = url;
    save.download = `cogncur-feedback-${Date.now()}.png`;
    save.hidden = false;
  }
  step.dataset.state = !req.snapshot ? 'none' : copied ? 'copied' : blob ? 'save' : 'failed';
}

// ---------- the 💬 Feedback button in the header (components/Nav.astro)
type Provider = () => FeedbackRequest;
let provider: Provider = () => ({ template: 'algemeen.yml', title: '[Opmerking] ' });

/** A page says what the header button reports (sync: it runs inside the click). */
export function onFeedback(fn: Provider): void {
  provider = fn;
}

export function initFeedbackButton(): void {
  document.getElementById('fb-nav')?.addEventListener('click', () => feedback(provider()));
}
