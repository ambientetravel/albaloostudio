import { describe, expect, it } from 'vitest';
import { content } from '../content';

/**
 * Unit names, and the 26px box they have to survive.
 *
 * This file used to test a SHORT_NAME lookup table: 25 hand-written one-word
 * labels, because the real names ('Paphlagonian Javelineer') could not fit the
 * Army Ledger and six plain infantry drawn ten pixels wide were the same
 * picture. The table is gone. Every unit is now a person — Zarina, Artavazda,
 * Shutruk — and the names were chosen to fit, so the name IS the short name.
 *
 * That removes a whole class of bug (a table drifting out of sync with the
 * roster) but it moves the constraint onto the DATA, where nothing enforces it
 * by construction. Hence these tests. A new unit called 'Ashurnadin' would
 * ellipsise in the ledger and silently turn two names back into one shape,
 * which is exactly the problem the names were meant to solve.
 */

const LEDGER_CEILING = 9;

describe('every unit name fits the Army Ledger', () => {
  it(`is at most ${LEDGER_CEILING} characters`, () => {
    // 8px Nunito bold runs about 4.4px per character in a 40px box: 'Sagartian'
    // needs 39px and fits; 'Chorasmian' needed 49px and ellipsised in the
    // browser. Measured, not guessed.
    const tooLong = content.units
      .filter((u) => u.name.length > LEDGER_CEILING)
      .map((u) => `${u.name} (${u.name.length})`);
    expect(tooLong).toEqual([]);
  });

  it('is one word, so it cannot wrap', () => {
    expect(content.units.filter((u) => /[\s-]/.test(u.name)).map((u) => u.name)).toEqual([]);
  });

  it('is unique across the roster', () => {
    const names = content.units.map((u) => u.name);
    expect(names.length).toBe(new Set(names).size);
  });
});

describe('the contingent survives the rename', () => {
  it('every unit still carries its troop type', () => {
    const missing = content.units.filter((u) => !u.contingent?.trim()).map((u) => u.id);
    expect(missing).toEqual([]);
  });

  it('never repeats the person as the contingent', () => {
    // The subtitle is what the history attaches to. If it echoes the name, the
    // card has lost the fact and kept only the invented individual.
    const echoed = content.units.filter((u) => u.contingent === u.name).map((u) => u.id);
    expect(echoed).toEqual([]);
  });
});

describe('Zarina', () => {
  const saka = content.units.find((u) => u.id === 'saka-horse-archer');

  it('is the Saka horse-archer, renamed but not reclassed', () => {
    expect(saka?.name).toBe('Zarina');
    expect(saka?.contingent).toBe('Saka Horse-archer');
    expect(saka?.class).toBe('horse-archer');
  });

  it('carries the evidence for showing a woman, in her own entry', () => {
    // The art rests on archaeology rather than on preference, so the game has
    // to be able to say why when a child asks. If this ever goes missing, the
    // card becomes an assertion instead of a fact.
    expect(saka?.evidence).toMatch(/burial|graves/i);
  });
});
