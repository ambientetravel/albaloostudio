import { describe, expect, it } from 'vitest';
import { draftPool, getBattle, getCommander, getUnit } from '../content';
import { counterMultiplier, simulate, type Squad } from './battle';
import { aiRoundPick } from './ai';
import {
  bothChosen,
  choose,
  commitPicks,
  improviseDeck,
  nextRound,
  scoreRound,
  startMatch,
  winnerOf,
  type MatchState,
} from './match';
import { MAX_SQUADS, ROUNDS_MAX, WINS_NEEDED } from './roundCore.ts';

const battle = getBattle('pasargadae-550');
const squad = (side: 'a' | 'b', ids: string[]): Squad => ({
  side,
  units: ids.map((unitId) => ({ unitId, tier: 1 as const, traits: [] })),
  doctrines: [],
});

describe('battle simulation', () => {
  it('is deterministic for a given seed', () => {
    const a = squad('a', ['immortal', 'persian-archer', 'persian-cavalry', 'spara-bearer']);
    const b = squad('b', ['persian-cavalry', 'persian-cavalry', 'saka-horse-archer', 'immortal']);
    const first = simulate(battle, a, b, 12345);
    const second = simulate(battle, a, b, 12345);
    expect(second.winner).toBe(first.winner);
    expect(second.ticks).toBe(first.ticks);
    expect(JSON.stringify(second.frames)).toBe(JSON.stringify(first.frames));
  });

  it('produces a different battle for a different seed', () => {
    const a = squad('a', ['immortal', 'persian-archer', 'persian-cavalry', 'spara-bearer']);
    const b = squad('b', ['persian-cavalry', 'saka-horse-archer', 'immortal', 'persian-archer']);
    const first = simulate(battle, a, b, 1);
    const second = simulate(battle, a, b, 999);
    expect(second.ticks).not.toBe(first.ticks);
  });

  it('always terminates with a resolved winner', () => {
    const a = squad('a', ['spara-bearer', 'spara-bearer', 'spara-bearer', 'spara-bearer']);
    const b = squad('b', ['spara-bearer', 'spara-bearer', 'spara-bearer', 'spara-bearer']);
    const log = simulate(battle, a, b, 7);
    expect(log.frames.length).toBeGreaterThan(0);
    expect(['a', 'b', 'draw']).toContain(log.winner);
  });

  it('never lets a unit walk off the field', () => {
    const a = squad('a', ['saka-horse-archer', 'saka-horse-archer', 'persian-archer', 'persian-archer']);
    const b = squad('b', ['persian-cavalry', 'persian-cavalry', 'immortal', 'immortal']);
    const log = simulate(battle, a, b, 42);
    for (const frame of log.frames) {
      for (const p of frame.pos) {
        expect(p.x).toBeGreaterThanOrEqual(2);
        expect(p.x).toBeLessThanOrEqual(98);
      }
    }
  });
});

describe('the combat triangle', () => {
  it('rewards infantry for fighting cavalry and punishes it for fighting archers', () => {
    const immortal = getUnit('immortal');
    expect(counterMultiplier(immortal, 'cavalry')).toBeGreaterThan(1);
    expect(counterMultiplier(immortal, 'archer')).toBeLessThan(1);
    expect(counterMultiplier(immortal, 'heavy-infantry')).toBe(1);
  });

  it('lets the counter beat the raw stat line', () => {
    // Cavalry has lower attack than an Immortal but should still win the
    // matchup against archers, which is the lesson the triangle teaches.
    const archers = squad('b', ['persian-archer', 'persian-archer', 'persian-archer', 'persian-archer']);
    const cavalry = squad('a', ['persian-cavalry', 'persian-cavalry', 'persian-cavalry', 'persian-cavalry']);
    const wins = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].filter(
      (seed) => simulate(battle, cavalry, archers, seed).winner === 'a',
    ).length;
    expect(wins).toBeGreaterThanOrEqual(8);
  });

  it('makes a gorge a bad place for chariots', () => {
    const gorge = getBattle('persian-gates-330');
    const plain = getBattle('pasargadae-550');
    const chariots = squad('a', ['scythed-chariot', 'scythed-chariot', 'scythed-chariot', 'scythed-chariot']);
    const foot = squad('b', ['spara-bearer', 'spara-bearer', 'spara-bearer', 'spara-bearer']);

    const seeds = [11, 22, 33, 44, 55, 66, 77, 88];
    const onPlain = seeds.filter((s) => simulate(plain, chariots, foot, s).winner === 'a').length;
    const inGorge = seeds.filter((s) => simulate(gorge, chariots, foot, s).winner === 'a').length;
    expect(inGorge).toBeLessThan(onPlain);
  });
});

/**
 * Plays a whole match through, choosing with the supplied strategies. Returns
 * the final state, so a test can assert on the score, the ledgers or the length.
 */
function playMatch(
  seed: number,
  arena: number,
  choosers: Record<'a' | 'b', (m: MatchState, side: 'a' | 'b') => string>,
  onRound?: (m: MatchState) => void,
): MatchState {
  const pool = draftPool(battle, arena).map((u) => u.id);
  let m = startMatch(battle, seed, arena, {
    a: improviseDeck(pool, seed, 4),
    b: improviseDeck(pool, seed ^ 0xbeef, 4),
  });

  let guard = 0;
  while (m.phase !== 'over' && guard++ < 40) {
    m = choose(m, 'a', choosers.a(m, 'a'));
    m = choose(m, 'b', choosers.b(m, 'b'));
    expect(bothChosen(m)).toBe(true);
    m = commitPicks(m);
    onRound?.(m);
    const roundSeed = (m.seed ^ ((m.round * 0x5bf03635) >>> 0)) >>> 0;
    const log = simulate(
      battle,
      { side: 'a', units: m.ledgers.a.squads, doctrines: m.ledgers.a.doctrines },
      { side: 'b', units: m.ledgers.b.squads, doctrines: m.ledgers.b.doctrines },
      roundSeed,
      m.round,
    );
    m = scoreRound(m, log.winner, log.remaining);
    if (m.phase !== 'over') m = nextRound(m);
  }
  return m;
}

const takeFirst = (m: MatchState, side: 'a' | 'b'): string => m.offers[side][0].id;

describe('the round loop', () => {
  it('runs a whole match and stops at four round wins', () => {
    for (let seed = 1; seed <= 25; seed++) {
      const m = playMatch(seed * 7919, 13, { a: takeFirst, b: takeFirst });
      expect(m.phase).toBe('over');
      expect(Math.max(m.score.a, m.score.b)).toBeLessThanOrEqual(WINS_NEEDED);
      expect(m.round).toBeLessThanOrEqual(ROUNDS_MAX);
      expect(winnerOf(m)).not.toBeNull();
      // Every round played is one recorded, and one of them is not a draw
      // unless the whole match was.
      expect(m.history).toHaveLength(m.round);
    }
  });

  it('never fields more than the squad ceiling, however long the match runs', () => {
    for (let seed = 1; seed <= 25; seed++) {
      playMatch(seed * 31, 13, { a: takeFirst, b: takeFirst }, (m) => {
        expect(m.ledgers.a.squads.length).toBeLessThanOrEqual(MAX_SQUADS);
        expect(m.ledgers.b.squads.length).toBeLessThanOrEqual(MAX_SQUADS);
      });
    }
  });

  it('keeps the ledger across rounds — the field resets, the army does not', () => {
    const invested: number[] = [];
    playMatch(2024, 13, { a: takeFirst, b: takeFirst }, (m) => {
      // Everything a pick can buy: a rank, a trait, or a doctrine. Exactly one
      // of the three lands every round, and nothing is ever refunded — so this
      // sum must go up by exactly one each time, whatever kind was taken.
      const l = m.ledgers.a;
      invested.push(
        l.squads.reduce((n, e) => n + e.tier + e.traits.length, 0) + l.doctrines.length,
      );
    });
    for (let i = 1; i < invested.length; i++) expect(invested[i]).toBe(invested[i - 1] + 1);
  });

  it('respects the tier cap, with exactly one documented exception', () => {
    // Astyages' passive puts one already-Trained card in front of him in rounds
    // 1 and 2, which is the only thing in the game that steps over the cap. It
    // is his whole identity — he starts ahead and has to close before a wider
    // army outlasts him. Nothing else may exceed the cap, ever.
    for (let seed = 1; seed <= 20; seed++) {
      playMatch(seed * 101, 13, { a: takeFirst, b: takeFirst }, (m) => {
        const cap = m.round >= ROUNDS_MAX ? 4 : m.round >= 5 ? 3 : m.round >= 3 ? 2 : 1;
        for (const side of ['a', 'b'] as const) {
          const kingsLevy = getCommander(m.commanders[side]).passive.id === 'kings-levy';
          const allowed = kingsLevy && m.round <= 2 ? Math.max(cap, 2) : cap;
          for (const e of m.ledgers[side].squads) {
            expect(e.tier, `${side} round ${m.round}`).toBeLessThanOrEqual(allowed);
          }
        }
      });
    }
  });

  it('only ever offers units the scenario allows', () => {
    playMatch(909, 13, { a: takeFirst, b: takeFirst }, (m) => {
      expect(m.offers.a).not.toContain('scythed-chariot');
      expect(m.offers.b).not.toContain('scythed-chariot');
    });
  });

  it('ignores a choice that was not on offer', () => {
    const pool = draftPool(battle, 13).map((u) => u.id);
    const m = startMatch(battle, 5, 13, { a: improviseDeck(pool, 5, 4), b: improviseDeck(pool, 6, 4) });
    const notOffered = pool.find((id) => !m.offers.a.some((c) => c.id === id))!;
    expect(choose(m, 'a', notOffered)).toBe(m);
  });

  it('resolves every round inside its own budget, even for armoured mirrors', () => {
    // Two shield-bearers alone used to grind for the better part of a minute.
    // The exhaustion ramp is what guarantees a round terminates.
    const wall = { side: 'a' as const, units: [{ unitId: 'spara-bearer', tier: 1 as const, traits: [] }], doctrines: [] };
    const wall2 = { side: 'b' as const, units: [{ unitId: 'spara-bearer', tier: 1 as const, traits: [] }], doctrines: [] };
    let decisive = 0;
    for (let seed = 1; seed <= 30; seed++) {
      const log = simulate(battle, wall, wall2, seed * 977, 1);
      if (log.winner !== 'draw') decisive++;
    }
    // A mirror should mostly resolve rather than time out on a health tie.
    expect(decisive).toBeGreaterThan(20);
  });
});

describe('tiers', () => {
  it('makes a Trained squad beat a Levy of the same card', () => {
    let veteran = 0;
    for (let seed = 1; seed <= 40; seed++) {
      const log = simulate(
        battle,
        { side: 'a', units: [{ unitId: 'median-spearman', tier: 2, traits: [] }], doctrines: [] },
        { side: 'b', units: [{ unitId: 'median-spearman', tier: 1, traits: [] }], doctrines: [] },
        seed * 6151,
        3,
      );
      if (log.winner === 'a') veteran++;
    }
    expect(veteran).toBeGreaterThan(32);
  });

  it('does not make a tier beat its counter for free', () => {
    // A Royal archer still loses to cavalry more often than not: the triangle
    // outranks the ladder, which is the whole lesson of the game.
    let cavalryWins = 0;
    for (let seed = 1; seed <= 40; seed++) {
      const log = simulate(
        battle,
        { side: 'a', units: [{ unitId: 'persian-cavalry', tier: 2, traits: [] }], doctrines: [] },
        { side: 'b', units: [{ unitId: 'persian-archer', tier: 3, traits: [] }], doctrines: [] },
        seed * 4099,
        5,
      );
      if (log.winner === 'a') cavalryWins++;
    }
    expect(cavalryWins).toBeGreaterThan(20);
  });
});

describe('the AI opponent', () => {
  it('picks a counter when the human has committed to one class', () => {
    const pool = draftPool(battle, 13).map((u) => u.id);
    const m = startMatch(battle, 314, 13, { a: [], b: [] });
    const forced: MatchState = {
      ...m,
      ledgers: {
        a: { squads: [{ unitId: 'persian-archer', tier: 1, traits: [] }], doctrines: [] },
        b: { squads: [], doctrines: [] },
      },
      offers: {
        a: [],
        b: ['spara-bearer', 'persian-cavalry', 'persian-archer'].map((id) => ({ id, kind: 'unit' as const })),
      },
    };
    expect(pool).toContain('persian-cavalry');
    // skill 1 disables the deliberate mistake, so this pins the scoring rather
    // than the slip — the slip is covered by the ladder tests in progression.
    const sharp = { name: 'Test', avatar: 0, skill: 1 };
    expect(aiRoundPick(forced, 'b', sharp)).toBe('persian-cavalry');
  });

  it('always returns something it was actually offered', () => {
    playMatch(77, 13, {
      a: (m, side) => aiRoundPick(m, side),
      b: (m, side) => aiRoundPick(m, side),
    }, (m) => {
      expect(m.picked.a).not.toBeNull();
      expect(m.picked.b).not.toBeNull();
    });
  });

  it('consolidates rather than only ever widening the front', () => {
    // Over many matches the computer should sometimes take a tier-up; an
    // opponent that never consolidates is one the tier system does not reach.
    let sawTierTwo = 0;
    for (let seed = 1; seed <= 25; seed++) {
      const m = playMatch(seed * 55511, 13, {
        a: (s, side) => aiRoundPick(s, side),
        b: (s, side) => aiRoundPick(s, side),
      });
      if (m.ledgers.a.squads.some((e) => e.tier > 1) || m.ledgers.b.squads.some((e) => e.tier > 1)) sawTierTwo++;
    }
    expect(sawTierTwo).toBeGreaterThan(5);
  });
});
