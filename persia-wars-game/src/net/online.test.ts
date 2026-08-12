import { describe, expect, it } from 'vitest';
import { content, draftPool, getBattle, isPlayable } from '../content';
import { isValidName, sanitizeName } from './protocol';
import {
  OFFER_SIZE,
  ROUNDS_MAX,
  addPick,
  emptyLedger,
  matchWinner,
  offersFor,
  type CardIndex,
  type Ledger,
  type Side,
} from '../sim/roundCore.ts';
import { bothChosen, choose, commitPicks, nextRound, scoreRound, startMatch } from '../sim/match';
import { simulate, type Squad } from '../sim/battle';

/**
 * The online mode's whole safety rests on three properties, all pinned here:
 *
 *  1. client and server derive the same pool from the same scenario and arena;
 *  2. client and server derive the same three cards for a given round;
 *  3. two clients replaying the same pick stream reach the same result.
 *
 * If any of them breaks, an online match desyncs and the two players watch
 * different games.
 */

const battle = getBattle('pasargadae-550');

/**
 * The filter the server applies in server/index.ts, restated independently here.
 * If the two ever drift the draft desyncs mid-match, so this is asserted against
 * the client's own `draftPool` for every arena and every scenario below.
 */
function serverPool(b: typeof battle, arena: number): string[] {
  return content.units
    .filter(
      (u) =>
        isPlayable(u.confidence) &&
        u.era === b.era &&
        u.arena <= arena &&
        (u.earliestAttested === null || u.earliestAttested <= b.yearNumeric),
    )
    .map((u) => u.id);
}

/** The card facts the server hands to the offer logic, built the server's way. */
const serverCards = (poolIds: string[], arena: number): CardIndex => ({
  ...Object.fromEntries(
    content.units
      .filter((u) => poolIds.includes(u.id))
      .map((u) => [u.id, { kind: 'unit' as const, cls: u.class, counters: u.counters }]),
  ),
  ...Object.fromEntries(
    content.upgrades
      .filter((u) => u.arena <= arena)
      .map((u) => [u.id, { kind: 'upgrade' as const, appliesTo: u.appliesTo, trait: u.trait }]),
  ),
  ...Object.fromEntries(
    content.doctrines.filter((d) => d.arena <= arena).map((d) => [d.id, { kind: 'doctrine' as const }]),
  ),
});

describe('offers are derived, not transmitted', () => {
  it('server and client compute the same pool for every scenario AND every arena', () => {
    for (const b of content.battles) {
      for (const arena of content.arenas) {
        expect(serverPool(b, arena.id), `${b.id} @ arena ${arena.id}`).toEqual(
          draftPool(b, arena.id).map((u) => u.id),
        );
      }
    }
  });

  it('widens the pool as the ladder climbs, and never narrows it', () => {
    for (const b of content.battles) {
      let last = -1;
      for (const arena of content.arenas) {
        const n = draftPool(b, arena.id).length;
        expect(n).toBeGreaterThanOrEqual(last);
        last = n;
      }
    }
  });

  it('leaves a real choice at the very bottom of the ladder', () => {
    // An offer is three cards. A pool of three would make every offer identical.
    for (const b of content.battles) {
      expect(draftPool(b, 1).length, `${b.id} @ arena 1`).toBeGreaterThan(OFFER_SIZE);
    }
  });

  it("matches the client match's own offer in every round of a full match", () => {
    // This is the property the server's pick validation depends on: it derives
    // the three cards independently and refuses anything else.
    const arena = 13;
    const poolIds = serverPool(battle, arena);
    const cards = serverCards(poolIds, arena);
    const upgradeIds = content.upgrades.filter((u) => u.arena <= arena).map((u) => u.id);
    const doctrineIds = content.doctrines.filter((d) => d.arena <= arena).map((d) => d.id);
    const decks = { a: ['persian-archer', 'immortal'], b: ['persian-cavalry', 'spara-bearer'] };

    let client = startMatch(battle, 31337, arena, decks);
    const serverLedgers: Record<Side, Ledger> = { a: emptyLedger(), b: emptyLedger() };
    const serverScore: Record<Side, number> = { a: 0, b: 0 };
    let serverRound = 1;

    let guard = 0;
    while (client.phase !== 'over' && guard++ < 20) {
      for (const side of ['a', 'b'] as Side[]) {
        // Everything the real server passes, restated independently here. If the
        // two ever drift, an online match desyncs mid-round — which is exactly
        // what this test exists to catch.
        const commander = content.commanders.find((c) => c.id === client.commanders[side])!;
        const other: Side = side === 'a' ? 'b' : 'a';
        const fromServer = offersFor({
          seed: client.seed,
          round: serverRound,
          side,
          deficit: Math.max(0, serverScore[other] - serverScore[side]),
          rerolls: 0,
          affinity: commander.affinity,
          startsTrained: commander.passive.id === 'kings-levy',
          poolIds,
          upgradeIds,
          doctrineIds,
          deck: decks[side],
          ledgerSelf: serverLedgers[side],
          ledgerOpponent: serverLedgers[side === 'a' ? 'b' : 'a'],
          cards,
        });
        expect(fromServer, `round ${serverRound} side ${side}`).toEqual(client.offers[side]);
      }

      const picks = { a: client.offers.a[0], b: client.offers.b[0] };
      client = choose(choose(client, 'a', picks.a.id), 'b', picks.b.id);
      client = commitPicks(client);
      serverLedgers.a = addPick(serverLedgers.a, picks.a, serverRound, cards);
      serverLedgers.b = addPick(serverLedgers.b, picks.b, serverRound, cards);
      expect(serverLedgers.a).toEqual(client.ledgers.a);
      expect(serverLedgers.b).toEqual(client.ledgers.b);

      const roundSeed = (client.seed ^ ((client.round * 0x5bf03635) >>> 0)) >>> 0;
      const log = simulate(
        battle,
        { side: 'a', units: client.ledgers.a.squads, doctrines: client.ledgers.a.doctrines },
        { side: 'b', units: client.ledgers.b.squads, doctrines: client.ledgers.b.doctrines },
        roundSeed,
        client.round,
      );
      client = scoreRound(client, log.winner, log.remaining);
      if (log.winner !== 'draw') serverScore[log.winner] += 1;
      serverRound += 1;
      if (client.phase !== 'over') client = nextRound(client);
    }
    expect(client.phase).toBe('over');
    expect(serverRound - 1).toBeLessThanOrEqual(ROUNDS_MAX);
  });

  /*
   * The wire carries a card's ID and nothing else. Each side then recovers the
   * FULL card from its own derived offer — which matters because two fields
   * never cross the wire: Astyages' `startTier`, and an upgrade's `target`.
   *
   * Rebuilding a card from a bare id looks harmless and silently desyncs the
   * ledgers a round or two later. It cost an hour of debugging to find, so it
   * is pinned here.
   */
  it('recovers the whole card from an id, not just its kind', () => {
    const pool = draftPool(battle, 13).map((u) => u.id);
    const m = startMatch(battle, 555, 13, { a: pool.slice(0, 4), b: pool.slice(0, 4) }, {
      a: 'astyages',
      b: 'cyrus',
    });
    const trained = m.offers.a.find((c) => c.startTier === 2)!;
    expect(trained, 'Astyages should be offered a Trained card in round 1').toBeDefined();

    // What choose() puts in `picked` must be the full card, startTier included.
    const chosen = choose(m, 'a', trained.id).picked.a!;
    expect(chosen.startTier).toBe(2);

    // And the ledger must reflect it: rank 2 in round 1, where the cap is 1.
    const withCard = addPick(emptyLedger(), chosen, 1, m.cards);
    expect(withCard.squads[0].tier).toBe(2);

    // A card rebuilt from the id alone loses it, and lands at rank 1 instead —
    // the exact divergence this test exists to stop.
    const rebuilt = addPick(emptyLedger(), { id: trained.id, kind: 'unit' }, 1, m.cards);
    expect(rebuilt.squads[0].tier).toBe(1);
  });

  it('never reveals a pick before both are in — the offers are side-private', () => {
    const m = startMatch(battle, 8080, 13, { a: ['persian-archer'], b: ['persian-cavalry'] });
    const oneIn = choose(m, 'a', m.offers.a[0].id);
    // One choice made is not both: the round does not advance, so nothing about
    // side a's card can reach side b before they have chosen.
    expect(bothChosen(oneIn)).toBe(false);
    expect(commitPicks(oneIn)).toBe(oneIn);
    expect(oneIn.phase).toBe('offer');
  });
});

describe('two clients stay in lockstep', () => {
  it('reaches identical ledgers when replaying the same pick stream', () => {
    // What the server relays is both picks of a round, together; each client
    // applies them to its own state built from the shared seed.
    const seed = 90210;
    const decks = { a: ['immortal'], b: ['saka-horse-archer'] };
    let host = startMatch(battle, seed, 13, decks);
    let guest = startMatch(battle, seed, 13, decks);

    const stream: { a: string; b: string }[] = [];
    let guard = 0;
    while (host.phase !== 'over' && guard++ < 20) {
      const picks = { a: host.offers.a[0].id, b: (host.offers.b[1] ?? host.offers.b[0]).id };
      stream.push(picks);
      host = commitPicks(choose(choose(host, 'a', picks.a), 'b', picks.b));
      const roundSeed = (host.seed ^ ((host.round * 0x5bf03635) >>> 0)) >>> 0;
      const log = simulate(
        battle,
        { side: 'a', units: host.ledgers.a.squads, doctrines: host.ledgers.a.doctrines },
        { side: 'b', units: host.ledgers.b.squads, doctrines: host.ledgers.b.doctrines },
        roundSeed,
        host.round,
      );
      host = scoreRound(host, log.winner, log.remaining);
      if (host.phase !== 'over') host = nextRound(host);
    }

    for (const picks of stream) {
      guest = commitPicks(choose(choose(guest, 'a', picks.a), 'b', picks.b));
      const roundSeed = (guest.seed ^ ((guest.round * 0x5bf03635) >>> 0)) >>> 0;
      const log = simulate(
        battle,
        { side: 'a', units: guest.ledgers.a.squads, doctrines: guest.ledgers.a.doctrines },
        { side: 'b', units: guest.ledgers.b.squads, doctrines: guest.ledgers.b.doctrines },
        roundSeed,
        guest.round,
      );
      guest = scoreRound(guest, log.winner, log.remaining);
      if (guest.phase !== 'over') guest = nextRound(guest);
    }

    expect(guest.ledgers).toEqual(host.ledgers);
    expect(guest.score).toEqual(host.score);
    expect(matchWinner(guest.score, guest.round + 1)).toBe(matchWinner(host.score, host.round + 1));
  });

  it('produces the identical battle on both sides from the shared seed', () => {
    const ledger = (ids: string[]) => ids.map((unitId) => ({ unitId, tier: 1 as const, traits: [] }));
    const a: Squad = { side: 'a', units: ledger(['immortal', 'persian-archer', 'persian-cavalry', 'spara-bearer']), doctrines: [] };
    const b: Squad = { side: 'b', units: ledger(['saka-horse-archer', 'immortal', 'persian-archer', 'persian-cavalry']), doctrines: [] };
    const seed = (90210 ^ 0x5bf03635) >>> 0;

    const onHost = simulate(battle, a, b, seed, 4);
    const onGuest = simulate(battle, a, b, seed, 4);

    expect(onGuest.winner).toBe(onHost.winner);
    expect(onGuest.ticks).toBe(onHost.ticks);
    expect(onGuest.remaining).toEqual(onHost.remaining);
    expect(JSON.stringify(onGuest.frames)).toBe(JSON.stringify(onHost.frames));
  });

  it('gives a long grind a longer rope in a later round', () => {
    // The round only changes a battle that actually runs long enough to meet
    // the exhaustion ramp — a quick decisive fight is identical in every round,
    // which is correct. An armoured mirror is the case that tests it.
    const wall = (side: 'a' | 'b'): Squad => ({
      side,
      units: [
        { unitId: 'spara-bearer', tier: 1, traits: [] },
        { unitId: 'kissian-levy', tier: 1, traits: [] },
      ],
      doctrines: [],
    });
    const r1 = simulate(battle, wall('a'), wall('b'), 555, 1);
    const r7 = simulate(battle, wall('a'), wall('b'), 555, 7);
    // Round 1 breaks the line sooner, because its whole budget is shorter.
    expect(r1.ticks).toBeLessThan(r7.ticks);
    expect(r7.frames.length).toBeGreaterThan(r1.frames.length);
  });
});

describe('the arena gate', () => {
  it('keeps arena-locked cards out of the pool', () => {
    const pool = draftPool(battle, 1).map((u) => u.id);
    // Arena 1 is the four starter cards; the Immortal is an arena-2 reward.
    expect(pool).toContain('persian-archer');
    expect(pool).not.toContain('immortal');
    expect(pool).not.toContain('melophoros');
  });

  it('opens the whole roster at the top of the ladder', () => {
    const pool = draftPool(getBattle('persian-gates-330'), 13);
    expect(pool.length).toBe(content.units.filter((u) => isPlayable(u.confidence)).length);
  });

  it('stacks with the date gate rather than replacing it', () => {
    // The chariot is an arena-11 card AND is not attested before 401 BCE.
    expect(draftPool(getBattle('pasargadae-550'), 13).map((u) => u.id)).not.toContain('scythed-chariot');
    expect(draftPool(getBattle('persian-gates-330'), 10).map((u) => u.id)).not.toContain('scythed-chariot');
    expect(draftPool(getBattle('persian-gates-330'), 11).map((u) => u.id)).toContain('scythed-chariot');
  });
});

describe('player names', () => {
  it('strips anything that is not a letter, digit, space, dash or underscore', () => {
    expect(sanitizeName('  Cy<script>rus  ')).toBe('Cyscriptrus');
    expect(sanitizeName('Ali_Reza-92')).toBe('Ali_Reza-92');
  });

  it('caps the length so nobody can flood the other player\'s screen', () => {
    expect(sanitizeName('x'.repeat(200))).toHaveLength(14);
  });

  it('rejects names that are too short', () => {
    expect(isValidName('a')).toBe(false);
    expect(isValidName('  ')).toBe(false);
    expect(isValidName('Ali')).toBe(true);
  });
});
