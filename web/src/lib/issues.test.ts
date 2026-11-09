import { describe, expect, it } from 'vitest';
import { formFields, indexIssues, subjectsOf, toRef, type ApiIssue } from './issues';

// Bodies in the format GitHub writes for issue forms (.github/ISSUE_TEMPLATE/*.yml).
const tekenBody = `### Teken

ď (U+010F, dcaron, schets)

### Voorbeeldwoorden

nďn aďe oďo ďď

### Afbeelding

![image](https://github.com/user-attachments/assets/x)

### Wat zie je?

Het accent staat te ver naar rechts.

### Voorstel (mag leeg blijven)

_No response_

### Instellingen

cogncur: ss03

### Versie van het lettertype

versie 1.000 · 386212f · 2026-11-07

### Link naar dit scherm

https://simonvanherweghe.github.io/cogncur/tekens/#teken=%C4%8F`;

const issue = (over: Partial<ApiIssue>): ApiIssue => ({
  number: 1, title: '', state: 'open', html_url: 'https://github.com/x/y/issues/1', body: '', labels: [], ...over,
});

describe('issue forms', () => {
  it('reads the fields and leaves out empty ones', () => {
    const f = formFields(tekenBody.replace(/\n/g, '\r\n'));
    expect(f['Teken']).toBe('ď (U+010F, dcaron, schets)');
    expect(f['Wat zie je?']).toBe('Het accent staat te ver naar rechts.');
    expect('Voorstel (mag leeg blijven)' in f).toBe(false);
    expect(formFields(null)).toEqual({});
  });

  it('finds the character of a teken issue', () => {
    expect(subjectsOf(issue({ title: '[Teken] ď (U+010F)', body: tekenBody }))).toEqual({ chars: ['ď'], pairs: [], words: [] });
    // also when someone wrote the issue by hand, or changed the title
    expect(subjectsOf(issue({ title: 'Accent te ver', body: tekenBody })).chars).toEqual(['ď']);
  });

  it('finds the pair of a verbinding issue', () => {
    const body = '### Letters\n\noe (in: oe noen ooee oeoe)\n\n### Wat zie je?\n\nTe hoog.';
    expect(subjectsOf(issue({ title: '[Verbinding] oe', body })).pairs).toEqual(['oe']);
  });

  it('finds the word or letter of a schrijfroute issue', () => {
    expect(subjectsOf(issue({ title: '[Schrijfroute] letter g', body: '### Letter of woord\n\ng (standaard; model: g)' })).words).toEqual(['g']);
    expect(subjectsOf(issue({ title: '[Schrijfroute] vliegtuig' })).words).toEqual(['vliegtuig']);
  });

  it('links decision issues to their characters', () => {
    const decisions = { 'accent-dubbele-aigu': { title: 'Nieuw accent: dubbele accent aigu', chars: 'őűŐŰ' } };
    const s = subjectsOf(issue({ title: 'Nieuw accent: dubbele accent aigu (ő ű)', body: '<!-- beslissing:accent-dubbele-aigu -->\nTekst' }), decisions);
    expect(s.chars).toEqual(['ő', 'ű', 'Ő', 'Ű']);
  });

  it('ignores issues that are about nothing in particular', () => {
    expect(subjectsOf(issue({ title: 'Welke stijlen?', body: 'Vraag' }))).toEqual({ chars: [], pairs: [], words: [] });
  });
});

describe('index', () => {
  it('lists open issues first, newest first, and skips nothing', () => {
    const refs = [
      toRef(issue({ number: 3, title: '[Teken] a', state: 'closed' })),
      toRef(issue({ number: 5, title: '[Teken] a' })),
      toRef(issue({ number: 4, title: '[Teken] a', labels: [{ name: 'teken' }], milestone: { title: 'Versie 1.001' } })),
    ];
    const { byChar } = indexIssues(refs);
    expect(byChar.get('a')!.map((i) => i.number)).toEqual([5, 4, 3]);
    expect(refs[2]).toMatchObject({ labels: ['teken'], milestone: 'Versie 1.001', state: 'open' });
  });
});
