// Behaviour of components/FeatureToggles.astro.
import { encode, type FeatureState } from './features';

export interface Toggles { sync(): void }

/** Checkboxes edit `state` in place and call onChange; sync() redraws them after outside changes. */
export function bindToggles(root: HTMLElement, state: FeatureState, onChange: () => void): Toggles {
  const boxes = [...root.querySelectorAll<HTMLInputElement>('input[data-tag]')];
  const sync = () => {
    for (const cb of boxes) {
      cb.checked = !!state[cb.dataset.tag!];
      cb.parentElement!.classList.toggle('on', cb.checked);
    }
    const code = encode(state);
    root.querySelector('[data-code]')!.textContent = code;
    root.querySelector('[data-count]')!.textContent = code.replace('vtex: ', '');
  };
  for (const cb of boxes) {
    cb.addEventListener('change', () => { state[cb.dataset.tag!] = cb.checked; sync(); onChange(); });
  }
  sync();
  return { sync };
}
