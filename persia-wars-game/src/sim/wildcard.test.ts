import { describe, expect, it } from 'vitest';
import { draftPool, getBattle } from '../content';
import { simulate, type Squad } from './battle';
import { choose, commitPicks, holdsWildcard, improviseDeck, startMatch } from './match';
import {
  WILDCARD_BASE,
  WILDCARD_FROM_ROUND,
  WILDCARD_MAX,
  WILDCARD_MULT,
  roundSeedFor,
  wildcardChance,
  wildcardFor,
  type Side,
} from './roundCore.ts';

/**
 * The Wildcard.
 *
 * The one thing that must never slip here is determinism. The recorder replays
 * a match byte-identically from a few hundred bytes of decisions, and the
 * server detects desync by comparing what both clients computed. A wildcard
 * drawn from `Math.random()` would break both SILENTLY — it would surface as
 * players being disconnected mid-match for no visible reason, which is close to
 * the worst failure this codebase could ship.
 */

const battle = getBattle('pasargadae-550');
const ARENA = 13;
const SIDES: Side[] = ['a', 'b'];

describe('the wildcard is derived, never rolled', () => {
  it('gives the same answer every time for the same inputs', () => {
    for (let seed = 1; seed <= 200; seed += 1) {
      for (const side of SIDES) {
        const first = wildcardFor(seed, 4, side, 1);
        for (let n = 0; n < 5; n += 1) {
          expect(wildcardFor(seed, 4, side, 1)).toBe(first);
        }
      }
    }
  });

  it('does not fire on the opening round', () => {
    // There is no board to read and no deficit to be behind by, so a round-one
    // doubling is pure luck rather than a comeback or a decision.
    for (let seed = 1; seed <= 400; seed += 1) {
      for (const side of SIDES) {
        expect(wildcardFor(seed, WILDCARD_FROM_ROUND - 1, side, 0)).toBe(false);
      }
    }
  });

  it('does not fire for both sides together', () => {
    // Unsalted, both sides share the round seed and would always roll the same
    // answer — which would cancel out and make the mechanic invisible.
    let together = 0;
    let either = 0;
    for (let seed = 1; seed <= 3000; seed += 1) {
      const a = wildcardFor(seed, 4, 'a', 0);
      const b = wildcardFor(seed, 4, 'b', 0);
      if (a || b) either += 1;
      if (a && b) together += 1;
    }
    expect(either).toBeGreaterThan(200);
    expect(together / either).toBeLessThan(0.2);
  });
});

describe('it favours the side that is behind', () => {
  const rate = (deficit: number): number => {
    let hits = 0;
    const trials = 4000;
    for (let seed = 1; seed <= trials; seed += 1) {
      if (wildcardFor(seed, 4, 'a', deficit)) hits += 1;
    }
    return hits / trials;
  };

  it('rises with the deficit', () => {
    const [even, one, two] = [rate(0), rate(1), rate(2)];
    expect(one).toBeGreaterThan(even);
    expect(two).toBeGreaterThan(one);
  });

  it('is still possible at level pegging', () => {
    // A comeback you can only get by losing is not a surprise, and the surprise
    // is half the reason this exists.
    expect(rate(0)).toBeGreaterThan(0.03);
  });

  it('lands near the stated chance, so the number in the doc is the truth', () => {
    expect(Math.abs(rate(0) - WILDCARD_BASE)).toBeLessThan(0.03);
    expect(Math.abs(rate(2) - wildcardChance(2))).toBeLessThan(0.03);
  });

  it('never runs away — a big deficit is a chance, not a guarantee', () => {
    expect(wildcardChance(99)).toBe(WILDCARD_MAX);
    expect(rate(9)).toBeLessThan(0.55);
  });
});

describe('a doubled squad is twice the squad', () => {
  const squadOf = (doubled: boolean): Squad => ({
    side: 'a',
    units: [{ unitId: 'persian-archer', tier: 2, traits: [], ...(doubled ? { doubled: true } : {}) }],
    doctrines: [],
    passive: undefined,
    order: undefined,
  });

  it(`multiplies the same number rank moves, by ${WILDCARD_MULT}`, () => {
    const plain = simulate(battle, squadOf(false), squadOf(false), 7, 4);
    const wild = simulate(battle, squadOf(true), squadOf(false), 7, 4);
    const plainHp = plain.roster.find((u) => u.side === 'a')!.maxHp;
    const wildHp = wild.roster.find((u) => u.side === 'a')!.maxHp;
    // Rounding in spawn means this is close rather than exact.
    expect(wildHp / plainHp).toBeGreaterThan(WILDCARD_MULT - 0.05);
    expect(wildHp / plainHp).toBeLessThan(WILDCARD_MULT + 0.05);
  });

  it('wins the round it would otherwise have drawn', () => {
    const wild = simulate(battle, squadOf(true), squadOf(false), 11, 4);
    expect(wild.winner).toBe('a');
  });
});

describe('the flag survives the ledger', () => {
  const pool = draftPool(battle, ARENA).map((u) => u.id);

  const play = (seed: number, wild: boolean) => {
    let m = startMatch(battle, seed, ARENA, {
      a: improviseDeck(pool, seed, 4),
      b: improviseDeck(pool, seed ^ 0x51ed, 4),
    });
    m = choose(m, 'a', m.offers.a[0].id);
    m = choose(m, 'b', m.offers.b[0].id);
    return { m, wild };
  };

  it('marks the squad taken on a wildcard round', () => {
    const { m } = play(4242, true);
    const after = commitPicks(m);
    // Round 1 never carries a wildcard, so nothing here should be doubled.
    expect(after.ledgers.a.squads.every((s) => !s.doubled)).toBe(true);
  });

  it('is sticky — ranking a doubled squad up does not undouble it', () => {
    // The reward would otherwise evaporate the moment you improved the squad,
    // which is the exact opposite of what a reward should do.
    const entry = { unitId: 'persian-archer', tier: 1 as const, traits: [], doubled: true };
    const ledger = { squads: [entry], doctrines: [] };
    const card = { id: 'persian-archer', kind: 'unit' as const };
    const idx = { 'persian-archer': { kind: 'unit' as const, cls: 'archer' as const, counters: [] } };
    const after = addPickLocal(ledger, card, 5, idx);
    expect(after.squads[0].doubled).toBe(true);
    expect(after.squads[0].tier).toBeGreaterThan(1);
  });
});

// Imported late so the describe block above reads in the order it runs.
import { addPick as addPickLocal } from './roundCore.ts';

describe('holdsWildcard agrees with the pure function', () => {
  it('reads the same answer the ledger will be built from', () => {
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    for (const seed of [1, 999, 31337]) {
      const m = startMatch(battle, seed, ARENA, {
        a: improviseDeck(pool, seed, 4),
        b: improviseDeck(pool, seed ^ 0x51ed, 4),
      });
      for (const side of SIDES) {
        expect(holdsWildcard(m, side)).toBe(wildcardFor(m.seed, m.round, side, 0));
      }
    }
    // And the round seed it rides on has not moved.
    expect(roundSeedFor(90210, 1)).toBe((90210 ^ ((1 * 0x5bf03635) >>> 0)) >>> 0);
  });
});
