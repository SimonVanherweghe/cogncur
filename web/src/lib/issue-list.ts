// "Al gemeld": a list of issues in a panel or in the feedback dialog.
import type { IssueRef } from './issues';

export function issueItems(list: IssueRef[]): HTMLLIElement[] {
  return list.map((i) => {
    const li = document.createElement('li');
    li.className = `issue ${i.state}`;
    const state = document.createElement('span');
    state.className = 'state';
    state.textContent = i.state === 'open' ? 'open' : 'gesloten';
    const a = Object.assign(document.createElement('a'), { href: i.url, target: '_blank', rel: 'noopener', textContent: `#${i.number} ${i.title}` });
    li.append(state, ' ', a);
    if (i.milestone) {
      const m = document.createElement('span');
      m.className = 'milestone';
      m.textContent = i.milestone;
      li.append(' ', m);
    }
    return li;
  });
}

/** Fill a container with a heading + list, or hide it when there is nothing. */
export function showIssues(box: HTMLElement, list: IssueRef[]): void {
  box.hidden = list.length === 0;
  box.querySelector('ul')!.replaceChildren(...issueItems(list));
}
