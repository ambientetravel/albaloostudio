import { describe, expect, it } from 'vitest';
import { draftPool, getBattle } from '../content';
import { aiRoundPick } from './ai';
import { simulate } from './battle';
import { bothChosen, choose, commitPicks, improviseDeck, nextRound, scoreRound, startMatch } from './match';
import { ROUNDS_MAX, WINS_NEEDED, roundTickLimit } from './roundCore.ts';
import { TICK_RATE } from './types';

/**
 * Match pace — Concept v0.2 §1.1 and §12.
 *
 * The concept promised four-to-six-minute matches. Working the arithmetic
 * through showed that first-to-4 actually produces roughly three to six, and
 * these tests hold the simulation to that. They measure combat seconds only;
 * the offer window, the placement step and the round banner sit on top.
 */

const battle = getBattle('pasargadae-550');
const ARENA = 13;

interface Played {
  rounds: number;
  combatSeconds: number;
  ranToBudget: number;
  /** Picks that were an upgrade or a doctrine rather than a unit. */
  rulePicks: number;
}

function playToEnd(seed: number): Played {
  const pool = draftPool(battle, ARENA).map((u) => u.id);
  let m = startMatch(battle, seed, ARENA, {
    a: improviseDeck(pool, seed, 4),
    b: improviseDeck(pool, seed ^ 0x51ed, 4),
  });
  let ticks = 0;
  let ranToBudget = 0;
  let rulePicks = 0;
  let guard = 0;

  while (m.phase !== 'over' && guard++ < 20) {
    m = choose(m, 'a', aiRoundPick(m, 'a'));
    m = choose(m, 'b', aiRoundPick(m, 'b'));
    expect(bothChosen(m)).toBe(true);
    if (m.picked.a!.kind !== 'unit') rulePicks++;
    if (m.picked.b!.kind !== 'unit') rulePicks++;
    m = commitPicks(m);
    const roundSeed = (m.seed ^ ((m.round * 0x5bf03635) >>> 0)) >>> 0;
    const log = simulate(
      battle,
      { side: 'a', units: m.ledgers.a.squads, doctrines: m.ledgers.a.doctrines },
      { side: 'b', units: m.ledgers.b.squads, doctrines: m.ledgers.b.doctrines },
      roundSeed,
      m.round,
    );
    ticks += log.ticks;
    if (log.ticks >= roundTickLimit(m.round, TICK_RATE)) ranToBudget++;
    m = scoreRound(m, log.winner, log.remaining);
    if (m.phase !== 'over') m = nextRound(m);
  }
  return { rounds: m.history.length, combatSeconds: ticks / TICK_RATE, ranToBudget, rulePicks };
}

describe('match pace', () => {
  const runs = Array.from({ length: 120 }, (_, i) => playToEnd((i + 1) * 7919));

  it('always ends between four and seven rounds', () => {
    for (const r of runs) {
      expect(r.rounds).toBeGreaterThanOrEqual(WINS_NEEDED);
      expect(r.rounds).toBeLessThanOrEqual(ROUNDS_MAX);
    }
  });

  it('keeps total combat inside the budget a six-minute match allows', () => {
    // Offer + banner overhead is roughly 14s a round. Combat alone must leave
    // room for that inside 6:30, so the ceiling here is 5 minutes of fighting.
    const worst = Math.max(...runs.map((r) => r.combatSeconds));
    expect(worst, `worst match had ${Math.round(worst)}s of combat`).toBeLessThan(300);
  });

  it('resolves every round on the field, not on a health comparison', () => {
    // A round that runs to its ceiling is decided by comparing health bars,
    // which is a coin flip wearing a uniform. The exhaustion ramp exists to
    // stop that. Measured across ~1,000 rounds: none of them time out.
    const total = runs.reduce((n, r) => n + r.rounds, 0);
    const capped = runs.reduce((n, r) => n + r.ranToBudget, 0);
    expect(capped / total, `${capped}/${total} rounds ran to the ceiling`).toBeLessThan(0.05);
  });

  /**
   * The snowball measurement — Concept v0.2 finding 1.2.
   *
   * Between evenly matched players a first-to-4 should produce a 4–0 sweep
   * about 12.5% of the time. Two equally skilled computers currently sweep far
   * more often than that, because a composition that beats the other one keeps
   * beating it and nothing in M1 pushes back hard enough.
   *
   * This is the number M3's comeback system has to move. The bound records
   * where the game actually is rather than pretending the problem is solved,
   * and it fails loudly if a later change makes it worse.
   *
   * Measured: M1 43% · M2 34% · M3 28%. The card kinds moved it first, by giving
   * a player being beaten more ways to answer than "draft another unit"; the
   * comeback systems took another six points. The ideal between two evenly
   * matched players is 12.5%, and the gap that remains is the AI drafting
   * consistently rather than the format snowballing.
   */
  it('records the sweep rate that the comeback system has to fix', () => {
    const sweeps = runs.filter((r) => r.rounds === WINS_NEEDED).length / runs.length;
    expect(sweeps, `${(sweeps * 100).toFixed(0)}% of matches were 4-0 sweeps`).toBeLessThan(0.35);
    expect(sweeps).toBeGreaterThan(0.05);
  });

  /**
   * Two thirds of the card system would be dead weight if the offer never put
   * traits and doctrines in front of a player often enough to take them.
   */
  it('makes upgrades and doctrines a real part of a match, not decoration', () => {
    const rules = runs.reduce((n, r) => n + r.rulePicks, 0);
    const all = runs.reduce((n, r) => n + r.rounds * 2, 0);
    expect(rules / all, `${((rules / all) * 100).toFixed(0)}% of picks were traits or doctrines`)
      .toBeGreaterThan(0.1);
    expect(rules / all).toBeLessThan(0.5);
  });
});
