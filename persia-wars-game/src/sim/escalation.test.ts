import { describe, expect, it } from 'vitest';
import { draftPool, getBattle, getCommander, getUnit } from '../content';
import { aiRoundPick } from './ai';
import { simulate, type Squad } from './battle';
import { choose, commitPicks, improviseDeck, nextRound, scoreRound, startMatch } from './match';
import { TIER_MULT, roundSeedFor, type Side } from './roundCore.ts';

/**
 * How much bigger does an army get, round by round?
 *
 * Measured because of a specific outside observation. The mobile game this one
 * takes its shape from offers cards worth +2 to +5 units in its first round and
 * +5 to +8 by its last, and both armies end up forty-plus strong — which is why
 * its round six reads as a climax. Ours caps at six squads and multiplies a
 * squad by at most 1.9, so the suspicion is that our late rounds feel like our
 * early ones.
 *
 * This test does not assert a target. It PRINTS the curve, so the number is on
 * the record before anybody argues about it.
 */

const battle = getBattle('pasargadae-550');
const ARENA = 13;
const SEEDS = Array.from({ length: 60 }, (_, i) => (i + 1) * 4231);

/** Raw fighting weight of a ledger: what actually walks onto the field. */
function power(squads: { unitId: string; tier: number }[]): number {
  return squads.reduce((n, e) => {
    const u = getUnit(e.unitId);
    const t = TIER_MULT[e.tier - 1] ?? 1;
    // atk and hp together, because a tier multiplies both and the pair is what
    // decides a fight rather than either alone.
    return n + u.atk * t * (u.hp * t) * 0.01;
  }, 0);
}

describe('our escalation curve', () => {
  it('reports army size and power by round', () => {
    const bySquads: number[][] = Array.from({ length: 8 }, () => []);
    const byPower: number[][] = Array.from({ length: 8 }, () => []);

    for (const seed of SEEDS) {
      const pool = draftPool(battle, ARENA).map((u) => u.id);
      let m = startMatch(battle, seed, ARENA, {
        a: improviseDeck(pool, seed, 4),
        b: improviseDeck(pool, seed ^ 0x51ed, 4),
      });
      let guard = 0;
      while (m.phase !== 'over' && guard++ < 20) {
        m = choose(m, 'a', aiRoundPick(m, 'a'));
        m = choose(m, 'b', aiRoundPick(m, 'b'));
        m = commitPicks(m);
        const r = m.round;
        if (r <= 7) {
          bySquads[r].push(m.ledgers.a.squads.length);
          byPower[r].push(power(m.ledgers.a.squads));
        }
        const sq = (side: Side): Squad => {
          const c = getCommander(m.commanders[side]);
          return {
            side,
            units: m.ledgers[side].squads,
            doctrines: m.ledgers[side].doctrines,
            passive: c.passive.id,
            order: c.order.id,
          };
        };
        const log = simulate(battle, sq('a'), sq('b'), roundSeedFor(m.seed, m.round), m.round);
        m = scoreRound(m, log.winner, log.remaining);
        if (m.phase !== 'over') m = nextRound(m);
      }
    }

    const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
    console.log('round | squads | power | matches');
    for (let r = 1; r <= 7; r += 1) {
      if (!bySquads[r].length) continue;
      console.log(
        `  ${r}   |  ${avg(bySquads[r]).toFixed(2)}  | ${avg(byPower[r]).toFixed(1).padStart(5)} | ${bySquads[r].length}`,
      );
    }
    const first = avg(byPower[1]);
    const last = avg(byPower[7]) || avg(byPower[6]) || avg(byPower[5]);
    console.log(`\nescalation across the match: ${(last / first).toFixed(2)}x`);
    expect(first).toBeGreaterThan(0);
  });
});
