import { describe, expect, it } from 'vitest';
import { content, draftPool, getBattle, getCommander } from '../content';
import { aiRoundPick } from './ai';
import { simulate, type Squad } from './battle';
import {
  choose,
  commitPicks,
  deficitOf,
  holdsRally,
  improviseDeck,
  nextRound,
  scoreRound,
  spendRally,
  startMatch,
  type MatchState,
} from './match';
import { RALLY_AT, offerSizeForDeficit, type Side, type Tier } from './roundCore.ts';

const battle = getBattle('pasargadae-550');
const ARENA = 13;
const SEEDS = Array.from({ length: 60 }, (_, i) => (i + 1) * 7919);

const squad = (
  side: Side,
  units: { unitId: string; tier?: Tier }[],
  commanderId?: string,
): Squad => {
  const c = commanderId ? getCommander(commanderId) : null;
  return {
    side,
    units: units.map((u) => ({ unitId: u.unitId, tier: u.tier ?? 1, traits: [] })),
    doctrines: [],
    passive: c?.passive.id,
    order: c?.order.id,
  };
};

/** Runs a whole match with both sides played by the computer. */
function playMatch(seed: number, commanders: Record<Side, string>) {
  const pool = draftPool(battle, ARENA).map((u) => u.id);
  let m = startMatch(
    battle,
    seed,
    ARENA,
    { a: improviseDeck(pool, seed, 4), b: improviseDeck(pool, seed ^ 0x51ed, 4) },
    commanders,
  );
  let guard = 0;
  const widened: number[] = [];
  while (m.phase !== 'over' && guard++ < 20) {
    widened.push(m.offers.a.length);
    m = choose(m, 'a', aiRoundPick(m, 'a'));
    m = choose(m, 'b', aiRoundPick(m, 'b'));
    m = commitPicks(m);
    const rs = (m.seed ^ ((m.round * 0x5bf03635) >>> 0)) >>> 0;
    const toSquad = (side: Side): Squad => {
      const c = getCommander(m.commanders[side]);
      return {
        side,
        units: m.ledgers[side].squads,
        doctrines: m.ledgers[side].doctrines,
        passive: c.passive.id,
        order: c.order.id,
      };
    };
    const log = simulate(battle, toSquad('a'), toSquad('b'), rs, m.round);
    m = scoreRound(m, log.winner, log.remaining);
    if (m.phase !== 'over') m = nextRound(m);
  }
  return { state: m, widened };
}

describe('the comeback, all three systems', () => {
  it('A — widens the offer as the deficit grows, and only then', () => {
    expect(offerSizeForDeficit(0)).toBe(3);
    expect(offerSizeForDeficit(1)).toBe(4);
    expect(offerSizeForDeficit(2)).toBe(5);
    expect(offerSizeForDeficit(3)).toBe(5);
  });

  it('A — actually reaches the player who is behind', () => {
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    let m = startMatch(battle, 4242, ARENA, { a: pool.slice(0, 4), b: pool.slice(0, 4) });
    expect(m.offers.a).toHaveLength(3);
    // Put side a two rounds down and reopen the offer.
    m = { ...m, score: { a: 0, b: 2 } };
    m = nextRound({ ...m, phase: 'roundResult' });
    expect(deficitOf(m, 'a')).toBe(2);
    expect(m.offers.a).toHaveLength(5);
    expect(m.offers.b).toHaveLength(3);
  });

  it('B — the Rally arrives on a deficit and clears on a win', () => {
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    const base = startMatch(battle, 77, ARENA, { a: pool.slice(0, 4), b: pool.slice(0, 4) });
    expect(holdsRally(base, 'a')).toBe(false);

    let m: MatchState = { ...base, rallyMeter: { a: RALLY_AT, b: 0 } };
    expect(holdsRally(m, 'a')).toBe(true);

    // Spending it redraws the offer, once.
    const before = m.offers.a.map((c) => c.id);
    m = spendRally(m, 'a');
    expect(m.offers.a.map((c) => c.id)).not.toEqual(before);
    expect(holdsRally(m, 'a')).toBe(false);
    // And a second attempt does nothing at all.
    expect(spendRally(m, 'a')).toBe(m);
  });

  it('B — winning a round empties the meter, so it cannot bank', () => {
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    let m = startMatch(battle, 99, ARENA, { a: pool.slice(0, 4), b: pool.slice(0, 4) });
    m = choose(choose(m, 'a', m.offers.a[0].id), 'b', m.offers.b[0].id);
    m = commitPicks(m);
    m = { ...m, rallyMeter: { a: 3, b: 0 } };
    m = scoreRound(m, 'a', { a: 1, b: 0 });
    expect(m.rallyMeter.a).toBe(0);
    expect(m.rallyMeter.b).toBe(1);
  });

  it('B — a reroll is deterministic, so both machines see the same new offer', () => {
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    const base = startMatch(battle, 31337, ARENA, { a: pool.slice(0, 4), b: pool.slice(0, 4) });
    const seeded: MatchState = { ...base, rallyMeter: { a: RALLY_AT, b: 0 } };
    const host = spendRally(seeded, 'a');
    const guest = spendRally(seeded, 'a');
    expect(host.offers.a).toEqual(guest.offers.a);
  });

  it('C — leans harder toward an answer when behind, without ever guaranteeing one', () => {
    // Measured through the offer itself: a trailing player sees a counter to
    // the opponent's cavalry more often than a level one does — but not always.
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    const rate = (score: Record<Side, number>) => {
      let hits = 0;
      for (const seed of SEEDS) {
        let m = startMatch(battle, seed, ARENA, { a: pool.slice(0, 4), b: pool.slice(0, 4) });
        m = {
          ...m,
          score,
          ledgers: {
            ...m.ledgers,
            b: { squads: [{ unitId: 'persian-cavalry', tier: 1, traits: [] }], doctrines: [] },
          },
        };
        m = nextRound({ ...m, phase: 'roundResult' });
        if (m.offers.a.some((c) => c.id === 'median-spearman' || c.id === 'spara-bearer')) hits++;
      }
      return hits / SEEDS.length;
    };
    expect(rate({ a: 0, b: 2 })).toBeGreaterThanOrEqual(rate({ a: 1, b: 1 }));
    expect(rate({ a: 0, b: 2 })).toBeLessThan(1);
  });

  it('never touches damage — §8 forbids a secret bonus, enforced mechanically', async () => {
    // The simulation must have no way to know the score. If this ever fails,
    // someone has wired the comeback into the fight instead of into the offer.
    const src = await import('node:fs').then((fs) =>
      fs.readFileSync(new URL('./battle.ts', import.meta.url), 'utf8'),
    );
    expect(src).not.toMatch(/\bscore\b/);
    expect(src).not.toMatch(/\bdeficit\b/);
    expect(src).not.toMatch(/\brally\b/i);
  });
});

describe('commander kits', () => {
  it('Cyrus holds a wide army together longer than a narrow one', () => {
    // Many Peoples blunts the exhaustion ramp per distinct class. Four different
    // squads should outlast four copies of a comparable one.
    const wide = squad(
      'a',
      [
        { unitId: 'median-spearman' },
        { unitId: 'persian-archer' },
        { unitId: 'persian-cavalry' },
        { unitId: 'immortal' },
      ],
      'cyrus',
    );
    const narrow = squad(
      'a',
      [
        { unitId: 'median-spearman' },
        { unitId: 'median-spearman' },
        { unitId: 'median-spearman' },
        { unitId: 'median-spearman' },
      ],
      'cyrus',
    );
    const foe = squad('b', [
      { unitId: 'spara-bearer' },
      { unitId: 'persian-archer' },
      { unitId: 'kissian-levy' },
      { unitId: 'bactrian-archer' },
    ]);
    const rate = (me: Squad) =>
      SEEDS.filter((s) => simulate(battle, me, foe, s, 7).winner === 'a').length / SEEDS.length;
    expect(rate(wide)).toBeGreaterThan(rate(narrow));
  });

  it("Cyrus' order puts the first fallen squad back up, exactly once", () => {
    const log = simulate(
      battle,
      squad('a', [{ unitId: 'persian-archer' }, { unitId: 'kissian-levy' }], 'cyrus'),
      squad('b', [{ unitId: 'persian-cavalry', tier: 4 }, { unitId: 'immortal', tier: 3 }]),
      1234,
      7,
    );
    const orders = log.frames.flatMap((f) =>
      f.events.filter((e) => e.t === 'order' && e.order === 'the-line-reforms'),
    );
    expect(orders.length).toBeLessThanOrEqual(1);
  });

  it('Astyages starts ahead — one card in rounds 1 and 2 arrives Trained', () => {
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    const m = startMatch(battle, 555, ARENA, { a: pool.slice(0, 4), b: pool.slice(0, 4) }, {
      a: 'astyages',
      b: 'cyrus',
    });
    expect(m.offers.a.some((c) => c.startTier === 2)).toBe(true);
    expect(m.offers.b.some((c) => c.startTier === 2)).toBe(false);
  });

  it('and that lead runs out — no Trained card from round 3 on', () => {
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    let m = startMatch(battle, 555, ARENA, { a: pool.slice(0, 4), b: pool.slice(0, 4) }, {
      a: 'astyages',
      b: 'cyrus',
    });
    for (let r = 0; r < 2; r++) {
      m = commitPicks(choose(choose(m, 'a', m.offers.a[0].id), 'b', m.offers.b[0].id));
      m = nextRound(scoreRound(m, 'draw', { a: 1, b: 1 }));
    }
    expect(m.round).toBe(3);
    expect(m.offers.a.some((c) => c.startTier === 2)).toBe(false);
  });

  it('leans the two commanders in opposite drafting directions', () => {
    // Cyrus is offered classes he does not hold; Astyages the ones he does.
    const held = { squads: [{ unitId: 'persian-archer', tier: 1 as const, traits: [] }], doctrines: [] };
    const sameClassRate = (commander: string) => {
      let same = 0;
      for (const seed of SEEDS) {
        let m = startMatch(battle, seed, ARENA, { a: [], b: [] }, { a: commander, b: 'cyrus' });
        m = { ...m, ledgers: { ...m.ledgers, a: held } };
        m = nextRound({ ...m, phase: 'roundResult' });
        const archers = m.offers.a.filter(
          (c) => c.kind === 'unit' && content.units.find((u) => u.id === c.id)?.class === 'archer',
        );
        if (archers.length > 0) same++;
      }
      return same / SEEDS.length;
    };
    expect(sameClassRate('astyages')).toBeGreaterThan(sameClassRate('cyrus'));
  });
});

/**
 * M3's acceptance criterion, from Concept v0.2 §11 and §5: two hundred matches
 * at equal skill must put neither commander above 55%.
 */
describe('commander balance', () => {
  const runs = SEEDS.concat(Array.from({ length: 140 }, (_, i) => (i + 100) * 104729));

  it('puts neither commander above 55% across 200 matches', () => {
    let cyrusWins = 0;
    let played = 0;
    for (const [i, seed] of runs.entries()) {
      // Alternate sides so the result is not measuring who drafts as side a.
      const commanders: Record<Side, string> =
        i % 2 === 0 ? { a: 'cyrus', b: 'astyages' } : { a: 'astyages', b: 'cyrus' };
      const { state } = playMatch(seed, commanders);
      const winner = state.score.a > state.score.b ? 'a' : state.score.b > state.score.a ? 'b' : null;
      if (!winner) continue;
      played++;
      if (state.commanders[winner] === 'cyrus') cyrusWins++;
    }
    const rate = cyrusWins / played;
    expect(played).toBeGreaterThan(150);
    expect(rate, `Cyrus won ${(rate * 100).toFixed(1)}% of ${played} decided matches`).toBeGreaterThan(0.45);
    expect(rate, `Cyrus won ${(rate * 100).toFixed(1)}% of ${played} decided matches`).toBeLessThan(0.55);
  });
});
