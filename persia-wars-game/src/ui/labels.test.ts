import { describe, expect, it } from 'vitest';
import { content } from '../content';
import { SHORT_NAMES, shortName } from './labels';

/**
 * The Army Ledger identifies a squad by a word, because at 26px it cannot
 * identify one by its picture — six of the plain infantry are the same brown
 * ten-pixel figure. That makes this table load-bearing rather than cosmetic:
 * a missing entry or a duplicate puts the player back where the art left them.
 */
describe('ledger short names', () => {
  it('covers every unit in the roster', () => {
    const missing = content.units.filter((u) => !(u.id in SHORT_NAMES)).map((u) => u.id);
    expect(missing).toEqual([]);
  });

  it('has no entry for a unit that no longer exists', () => {
    const ids = new Set(content.units.map((u) => u.id));
    expect(Object.keys(SHORT_NAMES).filter((id) => !ids.has(id))).toEqual([]);
  });

  it('gives no two units the same word', () => {
    // 'Persian Archer' and 'Persian Cavalry' both wanted to be 'Persian'. Two
    // squads labelled identically is exactly the failure the label exists to
    // fix, so it is worth a test rather than care.
    const seen = new Map<string, string>();
    const clashes: string[] = [];
    for (const [id, label] of Object.entries(SHORT_NAMES)) {
      const first = seen.get(label);
      if (first) clashes.push(`${first} and ${id} are both "${label}"`);
      else seen.set(label, id);
    }
    expect(clashes).toEqual([]);
  });

  it('keeps every word short enough for the slot', () => {
    // Measured, not guessed. The name box is 40px wide on a 375px viewport, and
    // 8px Nunito bold runs about 4.4px per character: 'Sagartian' needs 39px and
    // fits, 'Chorasmian' needed 49px and ellipsised in the browser. Nine is the
    // real ceiling. An ellipsised name turns two long names back into one shape,
    // which is the failure this whole label exists to prevent.
    const tooLong = Object.entries(SHORT_NAMES)
      .filter(([, label]) => label.length > 9)
      .map(([id, label]) => `${id}: ${label}`);
    expect(tooLong).toEqual([]);
  });

  it('falls back to the first word for an unknown unit', () => {
    expect(shortName('not-a-unit', 'Scythian Raider')).toBe('Scythian');
    expect(shortName('not-a-unit', 'Shield-bearer')).toBe('Shield');
  });

  it('prefers the table over the fallback', () => {
    expect(shortName('spara-bearer', 'Shield-bearer')).toBe('Spara');
  });
});
