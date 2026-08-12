import { describe, expect, it } from 'vitest';
import {
  EXHAUSTION_PEAK,
  MAX_SQUADS,
  OFFER_SIZE,
  ROUNDS_MAX,
  WINS_NEEDED,
  addPick,
  exhaustionMultiplier,
  isFinalClash,
  matchWinner,
  offersFor,
  pickIsUseful,
  roundTickLimit,
  roundsMaxFor,
  tierCapForRound,
  tierOf,
  emptyLedger,
  upgradeTarget,
  type CardIndex,
  type Ledger,
  type OfferCard,
} from './roundCore.ts';

/** A miniature content set, so these tests never depend on the real JSON. */
const CARDS: CardIndex = {
  spear: { kind: 'unit', cls: 'infantry', counters: ['cavalry'] },
  shield: { kind: 'unit', cls: 'infantry', counters: ['cavalry'] },
  bow: { kind: 'unit', cls: 'archer', counters: ['infantry', 'heavy-infantry'] },
  horse: { kind: 'unit', cls: 'cavalry', counters: ['archer'] },
  heavy: { kind: 'unit', cls: 'heavy-infantry', counters: ['infantry'] },
  camel: { kind: 'unit', cls: 'cavalry', counters: ['archer'] },
  volley: { kind: 'upgrade', appliesTo: ['archer'], trait: 'ready-volley' },
  wall: { kind: 'upgrade', appliesTo: ['infantry', 'heavy-infantry'], trait: 'locked-shields' },
  centre: { kind: 'doctrine' },
  horses: { kind: 'doctrine' },
};
const POOL = ['spear', 'shield', 'bow', 'horse', 'heavy', 'camel'];
const UPGRADES = ['volley', 'wall'];
const DOCTRINES = ['centre', 'horses'];

const ledgerOf = (...squads: { unitId: string; tier: 1 | 2 | 3 | 4; traits?: string[] }[]): Ledger => ({
  squads: squads.map((sq) => ({ ...sq, traits: sq.traits ?? [] })),
  doctrines: [],
});

const base = {
  seed: 12345,
  poolIds: POOL,
  upgradeIds: UPGRADES,
  doctrineIds: DOCTRINES,
  deck: ['spear', 'bow'],
  ledgerSelf: emptyLedger(),
  ledgerOpponent: emptyLedger(),
  cards: CARDS,
};

const unit = (id: string): OfferCard => ({ id, kind: 'unit' });
const ids = (offer: OfferCard[]): string[] => offer.map((c) => c.id);

describe('tiers', () => {
  it('caps at II until round 3, III until 5, IV only in the final round', () => {
    // Called explicitly, not point-free: `.map(tierCapForRound)` would hand the
    // array index in as the match-length argument and quietly test nothing.
    expect([1, 2, 3, 4, 5, 6, 7].map((r) => tierCapForRound(r))).toEqual([1, 1, 2, 2, 3, 3, 4]);
  });

  it('scales the rank ladder to a short campaign mission', () => {
    // First-to-2 is a three-round mission. A fixed ladder would leave it stuck
    // at Levy the whole way, so the caps compress with the match.
    expect([1, 2, 3].map((r) => tierCapForRound(r, 2))).toEqual([1, 2, 4]);
    // And the ceiling shortens with it, so a first-to-2 cannot run to seven.
    expect(roundsMaxFor(2)).toBe(3);
    expect(roundsMaxFor(4)).toBe(ROUNDS_MAX);
  });

  it('a duplicate raises the tier; a new unit joins the field', () => {
    let l = emptyLedger();
    l = addPick(l, unit('spear'), 1, CARDS);
    expect(l.squads).toEqual([{ unitId: 'spear', tier: 1, traits: [] }]);
    l = addPick(l, unit('bow'), 2, CARDS);
    expect(l.squads).toHaveLength(2);
    l = addPick(l, unit('spear'), 3, CARDS);
    expect(tierOf(l, 'spear')).toBe(2);
    expect(l.squads).toHaveLength(2);
  });

  it('never lets a pick exceed the round cap', () => {
    let l = emptyLedger();
    for (let r = 1; r <= ROUNDS_MAX; r++) {
      l = addPick(l, unit('spear'), r, CARDS);
      expect(tierOf(l, 'spear')).toBeLessThanOrEqual(tierCapForRound(r));
    }
    expect(tierOf(l, 'spear')).toBe(4);
  });

  it('refuses a seventh distinct squad', () => {
    let l = emptyLedger();
    for (const id of POOL) l = addPick(l, unit(id), ROUNDS_MAX, CARDS);
    expect(l.squads.length).toBe(MAX_SQUADS);
    expect(pickIsUseful(l, unit('spear'), ROUNDS_MAX, CARDS)).toBe(true); // can still tier
  });

  it('calls a pick useless when it can neither tier nor join', () => {
    const full = ledgerOf(...POOL.slice(0, MAX_SQUADS).map((unitId) => ({ unitId, tier: 1 as const })));
    expect(pickIsUseful(full, unit('spear'), 1, CARDS)).toBe(false);
    expect(pickIsUseful(full, unit('spear'), 3, CARDS)).toBe(true);
  });
});

/*
 * M2's acceptance criterion, from Concept v0.2 finding 1.3: a rank and a trait
 * must not be able to do each other's job.
 */
describe('the three card kinds stay in their lanes', () => {
  const upgrade = (id: string, target?: string): OfferCard => ({ id, kind: 'upgrade', target });
  const doctrine = (id: string): OfferCard => ({ id, kind: 'doctrine' });

  it('gives an upgrade a trait and NEVER a rank', () => {
    const before = ledgerOf({ unitId: 'bow', tier: 2 });
    const after = addPick(before, upgrade('volley', 'bow'), 5, CARDS);
    expect(after.squads[0].traits).toEqual(['ready-volley']);
    // The rank did not move. This is the whole distinction.
    expect(after.squads[0].tier).toBe(2);
  });

  it('gives a duplicate a rank and NEVER a trait', () => {
    const before = ledgerOf({ unitId: 'bow', tier: 1, traits: ['ready-volley'] });
    const after = addPick(before, unit('bow'), 3, CARDS);
    expect(after.squads[0].tier).toBe(2);
    expect(after.squads[0].traits).toEqual(['ready-volley']);
  });

  it('adds a doctrine to the army rather than to a squad', () => {
    const after = addPick(ledgerOf({ unitId: 'bow', tier: 1 }), doctrine('centre'), 2, CARDS);
    expect(after.doctrines).toEqual(['centre']);
    expect(after.squads[0]).toEqual({ unitId: 'bow', tier: 1, traits: [] });
  });

  it('picks the upgrade target deterministically, by class and draft order', () => {
    const l = ledgerOf({ unitId: 'horse', tier: 1 }, { unitId: 'bow', tier: 1 });
    expect(upgradeTarget(l, 'volley', CARDS)).toBe('bow');
    // Nothing of an eligible class: no target, so the card is a dead pick.
    expect(upgradeTarget(ledgerOf({ unitId: 'horse', tier: 1 }), 'volley', CARDS)).toBeNull();
  });

  it('never offers an upgrade with nothing to attach to', () => {
    for (let seed = 0; seed < 120; seed++) {
      // A cavalry-only ledger: neither the archer nor the infantry upgrade applies.
      const offer = offersFor({
        ...base,
        seed,
        round: 3,
        side: 'a',
        ledgerSelf: ledgerOf({ unitId: 'horse', tier: 1 }),
      });
      expect(ids(offer)).not.toContain('volley');
      expect(ids(offer)).not.toContain('wall');
    }
  });

  it('never offers a doctrine twice', () => {
    const held: Ledger = { ...emptyLedger(), doctrines: ['centre'] };
    for (let seed = 0; seed < 120; seed++) {
      const offer = offersFor({ ...base, seed, round: 4, side: 'a', ledgerSelf: held });
      expect(ids(offer)).not.toContain('centre');
    }
  });

  it('never offers a trait the squad already has', () => {
    const l = ledgerOf({ unitId: 'bow', tier: 1, traits: ['ready-volley'] });
    for (let seed = 0; seed < 120; seed++) {
      const offer = offersFor({ ...base, seed, round: 3, side: 'a', ledgerSelf: l });
      expect(ids(offer)).not.toContain('volley');
    }
  });

  it('puts traits and doctrines in front of the player often enough to matter', () => {
    // An opponent that never sees them would leave two thirds of the card system
    // untested; one that sees nothing else would drown out the units.
    const l = ledgerOf({ unitId: 'bow', tier: 1 }, { unitId: 'spear', tier: 1 });
    let withRule = 0;
    const RUNS = 300;
    for (let seed = 0; seed < RUNS; seed++) {
      const offer = offersFor({ ...base, seed, round: 4, side: 'a', ledgerSelf: l });
      if (offer.some((c) => c.kind !== 'unit')) withRule++;
    }
    expect(withRule).toBeGreaterThan(RUNS * 0.25);
    expect(withRule).toBeLessThan(RUNS * 0.95);
  });
});

describe('offers', () => {
  it('are identical for the same seed, round and side — the lockstep guarantee', () => {
    const a = offersFor({ ...base, round: 3, side: 'a' });
    const b = offersFor({ ...base, round: 3, side: 'a' });
    expect(a).toEqual(b);
  });

  it('differ between the two sides and between rounds', () => {
    const r3a = offersFor({ ...base, round: 3, side: 'a' });
    const r3b = offersFor({ ...base, round: 3, side: 'b' });
    const r4a = offersFor({ ...base, round: 4, side: 'a' });
    expect(r3a).not.toEqual(r3b);
    expect(r3a).not.toEqual(r4a);
  });

  it('never repeats a card inside one offer', () => {
    for (let round = 1; round <= ROUNDS_MAX; round++) {
      for (const side of ['a', 'b'] as const) {
        for (let seed = 0; seed < 40; seed++) {
          const offer = offersFor({
            ...base,
            seed,
            round,
            side,
            ledgerSelf: ledgerOf({ unitId: 'spear', tier: 1 }),
          });
          expect(new Set(ids(offer)).size).toBe(offer.length);
        }
      }
    }
  });

  it('offers three cards whenever the pool can supply three', () => {
    for (let seed = 0; seed < 60; seed++) {
      expect(offersFor({ ...base, seed, round: 2, side: 'a' })).toHaveLength(OFFER_SIZE);
    }
  });

  it('does not pad when the pool is smaller than the offer', () => {
    const tiny = offersFor({
      ...base,
      poolIds: ['spear', 'bow'],
      upgradeIds: [],
      doctrineIds: [],
      deck: ['spear'],
      round: 1,
      side: 'a',
    });
    expect(tiny.length).toBeLessThanOrEqual(2);
    expect(new Set(ids(tiny)).size).toBe(tiny.length);
  });

  it('always includes a tier-up once something is fielded and the cap allows it', () => {
    // Round 3 lifts the cap to II, and 'wall' is the only other improvement, so
    // slot B is always one of those two.
    const ledgerSelf = ledgerOf({ unitId: 'heavy', tier: 1 });
    let sawImprovement = 0;
    for (let seed = 0; seed < 40; seed++) {
      const offer = ids(offersFor({ ...base, seed, round: 3, side: 'a', ledgerSelf }));
      if (offer.includes('heavy') || offer.includes('wall')) sawImprovement++;
    }
    expect(sawImprovement).toBe(40);
  });

  it('leans toward counters of what the opponent fields, without guaranteeing them', () => {
    const ledgerOpponent = ledgerOf({ unitId: 'horse', tier: 1 });
    // 'spear' and 'shield' counter cavalry. Over many seeds they should appear
    // more often than the base rate — but not every time.
    let withCounter = 0;
    const RUNS = 300;
    for (let seed = 0; seed < RUNS; seed++) {
      const offer = ids(
        offersFor({ ...base, seed, round: 2, side: 'a', ledgerOpponent, deck: ['bow'], doctrineIds: [] }),
      );
      if (offer.includes('spear') || offer.includes('shield')) withCounter++;
    }
    expect(withCounter).toBeGreaterThan(RUNS * 0.5);
    // v0.1 §8: never a guaranteed perfect counter.
    expect(withCounter).toBeLessThan(RUNS);
  });

  it('draws slot A from the warband when the warband is legal here', () => {
    let fromDeck = 0;
    const RUNS = 200;
    for (let seed = 0; seed < RUNS; seed++) {
      const offer = ids(offersFor({ ...base, seed, round: 1, side: 'a', deck: ['camel'] }));
      if (offer.includes('camel')) fromDeck++;
    }
    // Slot A is always the deck when the deck is legal; C may also draw it.
    expect(fromDeck).toBe(RUNS);
  });

  it('survives a warband that is entirely illegal in this match', () => {
    const offer = offersFor({
      ...base,
      round: 2,
      side: 'a',
      deck: ['scythed-chariot', 'elephant'],
      upgradeIds: [],
      doctrineIds: [],
    });
    expect(offer).toHaveLength(OFFER_SIZE);
    for (const c of offer) expect(POOL).toContain(c.id);
  });
});

describe('round timing', () => {
  it('grows the combat budget with the round', () => {
    const limits = [1, 2, 3, 4, 5, 6, 7].map((r) => roundTickLimit(r, 20));
    for (let i = 1; i < limits.length; i++) expect(limits[i]).toBeGreaterThan(limits[i - 1]);
  });

  it('leaves damage alone early and ramps it to the peak by the end', () => {
    const limit = roundTickLimit(1, 20);
    expect(exhaustionMultiplier(0, limit)).toBe(1);
    expect(exhaustionMultiplier(Math.floor(limit * 0.5), limit)).toBe(1);
    expect(exhaustionMultiplier(limit, limit)).toBeCloseTo(EXHAUSTION_PEAK, 5);
    // Monotonic, so a round can never get easier to survive as it drags on.
    let prev = 0;
    for (let t = 0; t <= limit; t += 10) {
      const m = exhaustionMultiplier(t, limit);
      expect(m).toBeGreaterThanOrEqual(prev);
      prev = m;
    }
  });
});

describe('the match', () => {
  it('ends at exactly four round wins', () => {
    expect(matchWinner({ a: 3, b: 0 }, 4)).toBeNull();
    expect(matchWinner({ a: WINS_NEEDED, b: 2 }, 6)).toBe('a');
    expect(matchWinner({ a: 1, b: WINS_NEEDED }, 5)).toBe('b');
  });

  it('never runs past seven rounds', () => {
    // 3–3 after seven played rounds with round 7 drawn: more wins takes it, and
    // an exact tie is a draw rather than an eighth round.
    expect(matchWinner({ a: 3, b: 3 }, ROUNDS_MAX + 1)).toBe('draw');
    expect(matchWinner({ a: 3, b: 2 }, ROUNDS_MAX + 1)).toBe('a');
  });

  it('flags the Final Clash only at 3–3 in round seven', () => {
    expect(isFinalClash({ a: 3, b: 3 }, ROUNDS_MAX)).toBe(true);
    expect(isFinalClash({ a: 3, b: 3 }, 6)).toBe(false);
    expect(isFinalClash({ a: 3, b: 2 }, ROUNDS_MAX)).toBe(false);
  });

  it('cannot reach round seven without both players on three', () => {
    // If either side had four we would have stopped; so any live round 7 is 3–3.
    for (let a = 0; a <= 3; a++) {
      for (let b = 0; b <= 3; b++) {
        const live = matchWinner({ a, b }, ROUNDS_MAX) === null;
        if (live && a + b === ROUNDS_MAX - 1) expect(isFinalClash({ a, b }, ROUNDS_MAX)).toBe(true);
      }
    }
  });
});
