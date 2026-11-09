import { describe, expect, it } from 'vitest';
import { decode, defaults, encode, linkCode } from './features';

describe('config codes', () => {
  it('encodes only what differs from the default', () => {
    expect(encode(defaults())).toBe('cogncur: standaard');
    expect(linkCode(defaults())).toBe('cogncur');
    const s = { ...defaults(), ss03: true, ss08: true, kern: false };
    expect(encode(s)).toBe('cogncur: -kern ss03 ss08');   // in FEATURES order
    expect(linkCode(s)).toBe('cogncur-nokern-ss03-ss08');
  });

  it('reads the forms shared in the issues (text and link)', () => {
    for (const code of ['cogncur: ss03 ss08 -kern', '#cogncur-ss03-ss08-nokern', 'COGNCUR: SS08, ss03; -KERN']) {
      const { state, unknown } = decode(code);
      expect(unknown).toEqual([]);
      expect(state).toMatchObject({ ss03: true, ss08: true, kern: false, calt: true, ss01: false });
    }
  });

  it('round-trips every single feature both ways', () => {
    for (const tag of Object.keys(defaults())) {
      const s = { ...defaults(), [tag]: !defaults()[tag] };
      expect(decode(encode(s)).state).toEqual(s);
      expect(decode(linkCode(s)).state).toEqual(s);
    }
  });

  it('reports unknown tokens instead of failing', () => {
    expect(decode('cogncur: ss03 ss99 hallo').unknown).toEqual(['ss99', 'hallo']);
    expect(decode('cogncur: standaard').state).toEqual(defaults());
    expect(decode('').state).toEqual(defaults());
  });
});
