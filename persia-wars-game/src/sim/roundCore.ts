import { makeRng } from './rng.ts';

/**
 * The round loop, in the form the browser and the matchmaking server must agree
 * on exactly.
 *
 * Kept free of content and DOM imports so Node can load it straight from source
 * via type stripping, sharing one copy of the rules rather than keeping a
 * second, drifting one on the server. Both sides derive every offer from the
 * seed and the public match state rather than sending card lists over the wire,
 * so the server can validate a pick against the same three cards the client was
 * looking at without either trusting the other.
 *
 * Concept v0.2 §2. Replaces the single eight-pick draft.
 */

export type Side = 'a' | 'b';
export type Tier = 1 | 2 | 3 | 4;

/** First to this many round wins takes the match. Ranked always uses this. */
export const WINS_NEEDED = 4;
/** Hard ceiling. 3–3 makes round 7 the Final Clash. */
export const ROUNDS_MAX = 7;

/**
 * A campaign mission can be shorter than a ranked match — an early teaching beat
 * is first-to-2, the finale is the full first-to-4. Everything downstream is
 * derived from the target so a first-to-2 cannot run past three rounds.
 */
/**
 * The seed a single round's simulation runs on.
 *
 * Was copy-pasted in nine places — the store, four sim tests, three net tests.
 * A recorder replays a match by re-running these rounds, so any drift between
 * two copies of this expression would produce a replay that diverges from the
 * match it claims to be, silently. One definition, imported.
 */
export function roundSeedFor(seed: number, round: number): number {
  return (seed ^ ((round * 0x5bf03635) >>> 0)) >>> 0;
}

export function roundsMaxFor(winsNeeded: number): number {
  return Math.max(1, winsNeeded * 2 - 1);
}
export const OFFER_SIZE = 3;

// ------------------------------------------------------------- the comeback
/*
 * Concept v0.2 §3, systems A + B + C together.
 *
 * All three are visible and none of them touches damage: v0.1 §8 forbids a
 * secret bonus and forbids weakening the leader, and a rule the player can read
 * in the Scrolls is not a rubber band.
 *
 * Triggered by SCORE DEFICIT, not by consecutive losses — finding 1.7. The
 * deficit is what the player actually feels, and consecutive-loss triggers
 * arrive at the point where they can least change the result.
 */

/** A — the offer widens as you fall behind. More choice, never more power. */
export function offerSizeForDeficit(deficit: number): number {
  if (deficit >= 2) return 5;
  if (deficit >= 1) return 4;
  return OFFER_SIZE;
}

/** B — rounds lost since your last win. At RALLY_AT you hold a reroll. */
export const RALLY_AT = 2;

// ------------------------------------------------------------- the wildcard
/**
 * The Wildcard.
 *
 * Some rounds, whatever you take this round counts DOUBLE. It is announced
 * before you choose, which is the whole point: you decide what to double, so it
 * rewards reading the board rather than just handing out a bigger number.
 *
 * **It is seeded, never random.** `Math.random()` here would break two things
 * silently — the recorder replays a match byte-identically from a few hundred
 * bytes of decisions, and the server detects desync by comparing both clients.
 * A genuinely random multiplier would surface as players being disconnected
 * mid-match for no visible reason. Everything below derives from
 * (seed, round, side, deficit), all of which both clients already agree on.
 *
 * The chance rises with how far behind you are, so it pulls the same direction
 * as the three existing comebacks (wider offer, the Rally, counter-weighting)
 * instead of against them. It is deliberately non-zero at level pegging — a
 * comeback you can only ever get by losing is not a surprise, and the surprise
 * is half of why this exists.
 */
export const WILDCARD_MULT = 2;
export const WILDCARD_BASE = 0.08;
export const WILDCARD_PER_DEFICIT = 0.17;
export const WILDCARD_MAX = 0.46;
/** Never on the opening round — there is no board to read yet, and no deficit. */
export const WILDCARD_FROM_ROUND = 2;

export function wildcardChance(deficit: number): number {
  return Math.min(WILDCARD_MAX, WILDCARD_BASE + Math.max(0, deficit) * WILDCARD_PER_DEFICIT);
}

/**
 * Whether this side's pick is doubled this round. Pure, and derived only from
 * values both clients hold — see the note above on why that is not optional.
 */
export function wildcardFor(seed: number, round: number, side: Side, deficit: number): boolean {
  if (round < WILDCARD_FROM_ROUND) return false;
  // Salted per side, or both players would always roll the wildcard together.
  const salt = side === 'a' ? 0x9e3779b9 : 0x85ebca6b;
  const rng = makeRng((roundSeedFor(seed, round) ^ salt) >>> 0);
  return rng.next() < wildcardChance(deficit);
}

/** C — how hard slot C leans toward an answer. Capped; never a guarantee. */
export const COUNTER_WEIGHT = 2;
export const COUNTER_WEIGHT_TRAILING = 3;

/**
 * Distinct squads one side may field. Concept v0.2 §2.4 — a seventh pick has to
 * be a tier-up, which is what keeps round 7 legible on a phone.
 */
export const MAX_SQUADS = 6;

/** Levy → Trained → Veteran → Royal. Concept v0.1 §6.3. */
export const TIER_NAME = ['Levy', 'Trained', 'Veteran', 'Royal'] as const;
/** Applied to atk, def and hp alike, so a tier reads as "more of the same". */
export const TIER_MULT = [1, 1.25, 1.55, 1.9] as const;

export type CardKind = 'unit' | 'upgrade' | 'doctrine';

/** One squad on the field: what it is, how good it is, and what it has learned. */
export interface LedgerEntry {
  unitId: string;
  tier: Tier;
  /** Trait ids granted by Upgrade cards. Never affects rank. */
  traits: string[];
  /**
   * Taken on a Wildcard round, so this squad counts double. Sticky: a doubled
   * squad stays doubled when it is later ranked up, or the reward would quietly
   * evaporate the moment you improved it.
   */
  doubled?: boolean;
}

/**
 * Everything a side has drafted this match. Survives the round; the field does
 * not. Concept v0.1 §6.2 calls this the Army Ledger and it holds *all* drafted
 * choices, which is why doctrines live here beside the squads rather than in a
 * separate bag.
 */
export interface Ledger {
  squads: LedgerEntry[];
  doctrines: string[];
}

export function emptyLedger(): Ledger {
  return { squads: [], doctrines: [] };
}

/** One card on offer. The kind decides how it is drawn and what taking it does. */
export interface OfferCard {
  id: string;
  kind: CardKind;
  /**
   * Rank this card enters at if it is new. Only Astyages' passive sets it, and
   * it is the one thing that steps over `tierCapForRound`.
   */
  startTier?: Tier;
  /**
   * For an upgrade, the squad it would attach to — decided here so both clients
   * agree and so the offer screen can name it. Null for units and doctrines.
   */
  target?: string;
}

/**
 * The facts about a card that the offer logic needs, with content kept out of
 * this file so Node can still load it from source.
 */
export interface CardFacts {
  kind: CardKind;
  /** Units only. */
  cls?: string;
  counters?: string[];
  /** Upgrades only: squad classes this trait can attach to. */
  appliesTo?: string[];
  /** Upgrades only: the trait it grants. */
  trait?: string;
}
export type CardIndex = Record<string, CardFacts>;

/**
 * Highest tier reachable in this round. Tier II from round 3, III from 5, IV
 * from 7 — Concept v0.2 §2.4, so an early lead cannot compound into an
 * unanswerable Royal squad by round three.
 */
export function tierCapForRound(round: number, wins = WINS_NEEDED): Tier {
  const last = roundsMaxFor(wins);
  // Scaled to the match length, so a short campaign mission still gets a rank
  // ladder rather than being stuck at Levy the whole way through.
  if (round >= last) return 4;
  if (round >= Math.ceil(last * 0.7)) return 3;
  if (round >= Math.ceil(last * 0.4)) return 2;
  return 1;
}

export function tierOf(ledger: Ledger, unitId: string): Tier | 0 {
  return ledger.squads.find((e) => e.unitId === unitId)?.tier ?? 0;
}

/**
 * The squad an Upgrade would attach to: the first fielded squad of an eligible
 * class that does not already have the trait, in draft order.
 *
 * Chosen here rather than by the player so that both clients — and the server —
 * reach the same ledger from the same pick. The offer screen names the target so
 * the choice is never a surprise.
 */
export function upgradeTarget(ledger: Ledger, upgradeId: string, cards: CardIndex): string | null {
  const facts = cards[upgradeId];
  if (!facts || facts.kind !== 'upgrade') return null;
  const applies = facts.appliesTo ?? [];
  const trait = facts.trait ?? upgradeId;
  const hit = ledger.squads.find(
    (e) => applies.includes(cards[e.unitId]?.cls ?? '') && !e.traits.includes(trait),
  );
  return hit?.unitId ?? null;
}

/**
 * Whether taking this card would do anything. A dead pick is never offered:
 * a squad already at the round's tier cap, an upgrade with nothing to attach
 * to, a doctrine already in force, or a new unit when the field is full.
 */
export function pickIsUseful(
  ledger: Ledger,
  card: OfferCard,
  round: number,
  cards: CardIndex,
  wins = WINS_NEEDED,
): boolean {
  if (card.kind === 'doctrine') return !ledger.doctrines.includes(card.id);
  if (card.kind === 'upgrade') return upgradeTarget(ledger, card.id, cards) !== null;
  const tier = tierOf(ledger, card.id);
  if (tier === 0) return ledger.squads.length < MAX_SQUADS;
  return tier < tierCapForRound(round, wins);
}

/**
 * Take a card. Pure — the caller keeps the old ledger if it wants it.
 *
 * The three kinds cannot do each other's job, which is the whole point of
 * Concept v0.2 finding 1.3:
 *   a duplicate unit raises RANK — numbers, upward;
 *   an upgrade grants a TRAIT — behaviour, sideways, and never a rank;
 *   a doctrine changes the whole army.
 */
export function addPick(
  ledger: Ledger,
  card: OfferCard,
  round: number,
  cards: CardIndex,
  wins = WINS_NEEDED,
  wild = false,
): Ledger {
  if (card.kind === 'doctrine') {
    if (ledger.doctrines.includes(card.id)) return ledger;
    return { ...ledger, doctrines: [...ledger.doctrines, card.id] };
  }

  if (card.kind === 'upgrade') {
    const target = card.target ?? upgradeTarget(ledger, card.id, cards);
    const trait = cards[card.id]?.trait ?? card.id;
    if (!target) return ledger;
    return {
      ...ledger,
      squads: ledger.squads.map((e) =>
        e.unitId === target && !e.traits.includes(trait)
          ? { ...e, traits: [...e.traits, trait] }
          : e,
      ),
    };
  }

  const cap = tierCapForRound(round, wins);
  const existing = ledger.squads.find((e) => e.unitId === card.id);
  if (existing) {
    return {
      ...ledger,
      squads: ledger.squads.map((e) =>
        e.unitId === card.id
          ? { ...e, tier: Math.min(cap, e.tier + 1) as Tier, ...(wild || e.doubled ? { doubled: true } : {}) }
          : e,
      ),
    };
  }
  if (ledger.squads.length >= MAX_SQUADS) return ledger;
  // A new squad arrives one rank BELOW what the round allows, not at Levy.
  //
  // It used to arrive at Levy always, so a squad recruited in round 7 was worth
  // exactly what one recruited in round 1 was worth: every round added the same
  // amount and the match grew arithmetically, measured at a constant +2.3 power
  // per round. Men who join a war in its sixth month are not raw levies.
  //
  // One rank BELOW the cap rather than at it, because arriving at the cap
  // leaves a squad no headroom — it can never be ranked up, every duplicate
  // card becomes useless, and the whole rank mechanic dies in exactly the
  // rounds it was built for. A test caught that: `pickIsUseful` went false for
  // a full ledger at round 7.
  const arrives = Math.max(1, cap - 1) as Tier;
  return {
    ...ledger,
    squads: [
      ...ledger.squads,
      { unitId: card.id, tier: card.startTier ?? arrives, traits: [], ...(wild ? { doubled: true } : {}) },
    ],
  };
}

// ---------------------------------------------------------------- round timing

/**
 * Ticks of combat a round may run for. Grows with the round because the army
 * does: round 1 is one squad a side, round 7 is up to seven. Concept v0.2 §2.2,
 * revised upward from the paper figures after measuring the actual sim — two
 * shield-bearers alone need far longer to resolve than the paper allowed.
 */
export function roundTickLimit(round: number, tickRate: number): number {
  return Math.round((20 + round * 2) * tickRate);
}

/**
 * When lines start to break.
 *
 * Without this, two heavily-armoured squads grind for a minute and the round
 * times out on a health comparison, which is a coin flip wearing a uniform. Past
 * this point every strike lands harder, rising to `EXHAUSTION_PEAK` by the end
 * of the round, so a round always resolves and usually resolves early.
 *
 * It is also the honest reading of ancient battle: lines broke through
 * exhaustion and loss of cohesion, not by fighting to the last man.
 */
export const EXHAUSTION_AT = 0.55;
export const EXHAUSTION_PEAK = 3;

export function exhaustionMultiplier(tick: number, limit: number): number {
  const start = limit * EXHAUSTION_AT;
  if (tick <= start) return 1;
  const through = Math.min(1, (tick - start) / (limit - start));
  return 1 + through * (EXHAUSTION_PEAK - 1);
}

// ----------------------------------------------------------------- the offer

export interface OfferParams {
  seed: number;
  round: number;
  side: Side;
  /** How many round wins this side is behind by. Drives all three comebacks. */
  deficit?: number;
  /** Rerolls already spent this round — a reroll must not repeat the offer. */
  rerolls?: number;
  /** 'wide' leans slot C toward classes you do not field; 'deep' toward yours. */
  affinity?: 'wide' | 'deep';
  /** Astyages' passive: one card in rounds 1–2 arrives already Trained. */
  startsTrained?: boolean;
  /** Every UNIT legal in this match: arena rung AND scenario date. */
  poolIds: string[];
  /** Upgrade and doctrine ids the match's arena has unlocked. */
  upgradeIds: string[];
  doctrineIds: string[];
  /** The player's warband. Concept v0.2 §1.4 — the deck seeds slot A, it is not the offer pool. */
  deck: string[];
  ledgerSelf: Ledger;
  ledgerOpponent: Ledger;
  cards: CardIndex;
  /** Match length. A campaign mission can be shorter than a ranked match. */
  winsNeeded?: number;
}

/**
 * The three cards on offer, from three different sources so no offer is ever
 * three of a kind (Concept v0.2 §2.3):
 *
 *   A — one card from the player's own warband, so the deck matters;
 *   B — an improvement to something already fielded: either a rank, or an
 *       Upgrade's trait. This is the slot where the two mechanisms sit side by
 *       side and the player chooses between going up and going sideways;
 *   C — a wildcard from the arena — a unit weighted toward answers to what the
 *       opponent is fielding, or occasionally a doctrine for the whole army.
 *
 * Slot C's counter weighting is capped at 2×: v0.1 §8 forbids handing the losing
 * player a guaranteed counter, and this is a thumb on the scale, not a gift.
 *
 * Resolution order is B, A, C — B is the most constrained, and each later slot
 * avoids what the earlier ones took, so the same card never appears twice.
 */
export function offersFor(p: OfferParams): OfferCard[] {
  const deficit = p.deficit ?? 0;
  const size = offerSizeForDeficit(deficit);
  const rng = makeRng(
    (p.seed ^
      ((p.round * 0x9e3779b1) >>> 0) ^
      (p.side === 'a' ? 0 : 0x85ebca6b) ^
      // A reroll must produce a different offer, and the same different offer on
      // both machines — so the count goes into the seed rather than into state.
      (((p.rerolls ?? 0) * 0x27d4eb2f) >>> 0)) >>>
      0,
  );

  const card = (id: string): OfferCard => {
    const kind = p.cards[id]?.kind ?? 'unit';
    if (kind !== 'upgrade') return { id, kind };
    return { id, kind, target: upgradeTarget(p.ledgerSelf, id, p.cards) ?? undefined };
  };
  const wins = p.winsNeeded ?? WINS_NEEDED;
  const useful = (id: string): boolean =>
    pickIsUseful(p.ledgerSelf, card(id), p.round, p.cards, wins);

  const units = p.poolIds.filter(useful);
  // Everything is a dead pick — the field is full and every squad is capped.
  // Fall back to the raw pool so an offer is never empty.
  const legalUnits = units.length > 0 ? units : p.poolIds;
  const legalUpgrades = p.upgradeIds.filter(useful);
  const legalDoctrines = p.doctrineIds.filter(useful);
  const taken: string[] = [];

  const draw = (from: string[], weight?: (id: string) => number): string | null => {
    const candidates = from.filter((id) => !taken.includes(id));
    if (candidates.length === 0) return null;
    if (!weight) return candidates[rng.int(candidates.length)];
    const weights = candidates.map(weight);
    const total = weights.reduce((s, w) => s + w, 0);
    let roll = rng.next() * total;
    for (let i = 0; i < candidates.length; i++) {
      roll -= weights[i];
      if (roll <= 0) return candidates[i];
    }
    return candidates[candidates.length - 1];
  };

  // --- B: improve something already fielded ----------------------------------
  // Ranks and traits share this slot deliberately. A player who always takes the
  // rank and never the trait is making a choice, not missing a mechanic.
  const rankable = p.ledgerSelf.squads
    .filter((e) => e.tier < tierCapForRound(p.round, wins))
    .map((e) => e.unitId)
    .filter((id) => legalUnits.includes(id));
  const improvements = [...rankable, ...legalUpgrades];
  const slotB = improvements.length > 0 ? draw(improvements) : null;
  if (slotB) taken.push(slotB);

  // --- A: from the player's own warband --------------------------------------
  const fromDeck = p.deck.filter((id) => legalUnits.includes(id));
  const slotA = draw(fromDeck.length > 0 ? fromDeck : legalUnits) ?? draw(legalUnits);
  if (slotA) taken.push(slotA);

  // --- C: arena wildcard, or a doctrine --------------------------------------
  const enemyClasses = new Set(
    p.ledgerOpponent.squads
      .map((e) => p.cards[e.unitId]?.cls)
      .filter((c): c is string => Boolean(c)),
  );
  // Doctrines are army-wide and there are few of them, so they are weighted to
  // show up as an occasional real option rather than as noise or as a flood.
  const wildcards = [...legalUnits, ...legalDoctrines];
  // A commander's affinity decides which way this slot leans when it is not
  // busy answering the opponent: Cyrus toward classes he does not yet field,
  // Astyages toward the ones he does.
  const ownClasses = new Set(
    p.ledgerSelf.squads.map((e) => p.cards[e.unitId]?.cls).filter((c): c is string => Boolean(c)),
  );
  const counterWeight = deficit > 0 ? COUNTER_WEIGHT_TRAILING : COUNTER_WEIGHT;
  const slotC = draw(wildcards, (id) => {
    const facts = p.cards[id];
    if (facts?.kind === 'doctrine') return DOCTRINE_WEIGHT;
    let w = (facts?.counters ?? []).some((c) => enemyClasses.has(c)) ? counterWeight : 1;
    if (p.affinity && facts?.cls) {
      const held = ownClasses.has(facts.cls);
      if (p.affinity === 'wide' && !held) w *= AFFINITY_WEIGHT;
      if (p.affinity === 'deep' && held) w *= AFFINITY_WEIGHT;
    }
    return w;
  });
  if (slotC) taken.push(slotC);

  // Widened by the comeback, or narrowed by a pool smaller than three cards —
  // which is a legitimate state at Anshan on a date-restricted scenario. Offer
  // what exists rather than padding it.
  while (taken.length < size) {
    const filler = draw([...legalUnits, ...legalUpgrades, ...legalDoctrines]);
    if (!filler) break;
    taken.push(filler);
  }

  const cards = taken.map(card);
  // Astyages starts ahead: in the first two rounds one card he is offered
  // arrives already Trained. It is the only thing in the game that steps over
  // the round's rank cap, and it is his whole identity — he must close early or
  // lose late to a wider army.
  if (p.startsTrained && p.round <= 2) {
    const first = cards.findIndex((c) => c.kind === 'unit');
    if (first >= 0) cards[first] = { ...cards[first], startTier: 2 };
  }
  return cards;
}

/** How hard a commander's affinity leans slot C. Smaller than a counter. */
export const AFFINITY_WEIGHT = 1.8;

/**
 * How heavily a doctrine is weighted against a single unit in the wildcard slot.
 * With three doctrines against twenty-odd units, a weight of 1 would make them
 * almost never appear; this puts a doctrine in roughly one offer in five at the
 * top of the ladder, which is often enough to be a real choice.
 */
export const DOCTRINE_WEIGHT = 3;

// ------------------------------------------------------------------ the match

export function isMatchOver(score: Record<Side, number>, round: number, wins = WINS_NEEDED): boolean {
  return score.a >= wins || score.b >= wins || round > roundsMaxFor(wins);
}

/** Who has won, or null while it is still live. A full-length tie goes to more wins. */
export function matchWinner(
  score: Record<Side, number>,
  round: number,
  wins = WINS_NEEDED,
): Side | 'draw' | null {
  if (score.a >= wins) return 'a';
  if (score.b >= wins) return 'b';
  if (round > roundsMaxFor(wins)) {
    if (score.a > score.b) return 'a';
    if (score.b > score.a) return 'b';
    return 'draw';
  }
  return null;
}

/** The announced last round — v0.1 §6.1. */
export function isFinalClash(
  score: Record<Side, number>,
  round: number,
  wins = WINS_NEEDED,
): boolean {
  return round === roundsMaxFor(wins) && score.a === wins - 1 && score.b === wins - 1;
}
