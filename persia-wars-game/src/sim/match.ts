import type { Battle } from '../content/types';
import { content, doctrinesUnlockedAt, draftPool, getCommander, upgradesUnlockedAt } from '../content';
import { makeRng } from './rng';
import {
  RALLY_AT,
  ROUNDS_MAX,
  WINS_NEEDED,
  addPick,
  emptyLedger,
  isFinalClash,
  matchWinner,
  offersFor,
  type CardIndex,
  type Ledger,
  type OfferCard,
  type Side,
  wildcardFor,
} from './roundCore.ts';

/**
 * A match: up to seven rounds, first to four.
 *
 * Replaces the single eight-pick draft. The battlefield resets every round but
 * the **Army Ledger does not** — Concept v0.1 §6.2 — so a card taken in round 1
 * is still fighting in round 7, and a card taken twice is fighting harder.
 *
 * Picks are **simultaneous**. Concept v0.2 §2.5 proposed that the round's loser
 * pick second and see the winner's card; that is a comeback mechanic and it
 * lands with the rest of them in M3. Simultaneous picks halve the round and
 * remove the dead "waiting for your opponent" window the old draft had. Recorded
 * in DECISIONS.md.
 */

export type Phase = 'offer' | 'battle' | 'roundResult' | 'over';

export interface RoundOutcome {
  round: number;
  picks: Record<Side, OfferCard>;
  winner: Side | 'draw';
  /** Fraction of starting health each side finished the round with. */
  remaining: Record<Side, number>;
}

export interface MatchState {
  battleId: string;
  arena: number;
  seed: number;
  /** 1-based. Never exceeds ROUNDS_MAX while the match is live. */
  round: number;
  phase: Phase;
  ledgers: Record<Side, Ledger>;
  score: Record<Side, number>;
  offers: Record<Side, OfferCard[]>;
  /** This round's choice, null until made. */
  picked: Record<Side, OfferCard | null>;
  history: RoundOutcome[];
  poolIds: string[];
  upgradeIds: string[];
  doctrineIds: string[];
  cards: CardIndex;
  decks: Record<Side, string[]>;
  /** Commander ids. Decide the passive, the order and the drafting affinity. */
  commanders: Record<Side, string>;
  /**
   * Comeback B — the Rally. Rounds lost since this side's last win. At
   * `RALLY_AT` the side holds one reroll; winning a round empties it. The meter
   * is on the score, not on a streak: Concept v0.2 finding 1.7.
   */
  rallyMeter: Record<Side, number>;
  /** Rerolls spent this round. Feeds the offer seed, so both clients agree. */
  rerolls: Record<Side, number>;
  /** Orders are one use a match, fired at a stated trigger. */
  orderSpent: Record<Side, boolean>;
  /**
   * Rounds needed to take the match. Ranked is always `WINS_NEEDED`; a campaign
   * mission can be shorter, and everything downstream — the rank cap, the final
   * round, the ceiling — is derived from it.
   */
  winsNeeded: number;
  /** Set when this match is a campaign mission. Null for ranked and practice. */
  missionId: string | null;
}

/**
 * Whether this side's pick is doubled this round.
 *
 * Recomputed from the match rather than stored, so it cannot drift out of sync
 * with the score, and so a replay derives the same answer without the recording
 * having to carry it. Called by the draft screen to announce it BEFORE the
 * choice — a doubling nobody knew about is not a decision, it is a surprise
 * bill.
 */
export function holdsWildcard(m: MatchState, side: Side): boolean {
  return wildcardFor(m.seed, m.round, side, deficitOf(m, side));
}

/** Whether this side is holding a Rally reroll right now. */
export function holdsRally(m: MatchState, side: Side): boolean {
  return m.rallyMeter[side] >= RALLY_AT && m.rerolls[side] === 0;
}

/** How many round wins this side is behind by. Drives all three comebacks. */
export function deficitOf(m: MatchState, side: Side): number {
  return Math.max(0, m.score[side === 'a' ? 'b' : 'a'] - m.score[side]);
}

/**
 * The facts the offer logic needs about every card in this match, with content
 * kept out of `roundCore` so the server can still load it from source.
 */
export function cardIndexFor(poolIds: string[], arena: number): CardIndex {
  const index: CardIndex = {};
  for (const u of content.units) {
    if (poolIds.includes(u.id)) index[u.id] = { kind: 'unit', cls: u.class, counters: u.counters };
  }
  for (const u of upgradesUnlockedAt(arena)) {
    index[u.id] = { kind: 'upgrade', appliesTo: u.appliesTo, trait: u.trait };
  }
  for (const d of doctrinesUnlockedAt(arena)) {
    index[d.id] = { kind: 'doctrine' };
  }
  return index;
}

/**
 * A warband for an opponent that has no collection — the computer, or a player
 * whose deck did not arrive. Deterministic from the seed so a replay shows the
 * same opponent making the same kind of choices.
 */
export function improviseDeck(poolIds: string[], seed: number, size: number): string[] {
  const rng = makeRng((seed ^ 0x3c6ef372) >>> 0);
  const bag = [...poolIds];
  const out: string[] = [];
  while (out.length < size && bag.length > 0) out.push(bag.splice(rng.int(bag.length), 1)[0]);
  return out;
}

export function startMatch(
  battle: Battle,
  seed: number,
  arena: number,
  decks: Record<Side, string[]>,
  commanders: Record<Side, string> = { a: 'cyrus', b: 'astyages' },
  opts: { winsNeeded?: number; missionId?: string } = {},
): MatchState {
  const poolIds = draftPool(battle, arena).map((u) => u.id);
  const state: MatchState = {
    battleId: battle.id,
    arena,
    seed,
    round: 1,
    phase: 'offer',
    ledgers: { a: emptyLedger(), b: emptyLedger() },
    score: { a: 0, b: 0 },
    offers: { a: [], b: [] },
    picked: { a: null, b: null },
    history: [],
    poolIds,
    upgradeIds: upgradesUnlockedAt(arena).map((u) => u.id),
    doctrineIds: doctrinesUnlockedAt(arena).map((d) => d.id),
    cards: cardIndexFor(poolIds, arena),
    decks,
    commanders,
    rallyMeter: { a: 0, b: 0 },
    rerolls: { a: 0, b: 0 },
    orderSpent: { a: false, b: false },
    winsNeeded: opts.winsNeeded ?? WINS_NEEDED,
    missionId: opts.missionId ?? null,
  };
  return refreshOffers(state);
}

export function offersForSide(m: MatchState, side: Side): OfferCard[] {
  const commander = getCommander(m.commanders[side]);
  return offersFor({
    seed: m.seed,
    round: m.round,
    side,
    deficit: deficitOf(m, side),
    rerolls: m.rerolls[side],
    affinity: commander.affinity,
    startsTrained: commander.passive.id === 'kings-levy',
    poolIds: m.poolIds,
    upgradeIds: m.upgradeIds,
    doctrineIds: m.doctrineIds,
    deck: m.decks[side],
    ledgerSelf: m.ledgers[side],
    ledgerOpponent: m.ledgers[side === 'a' ? 'b' : 'a'],
    cards: m.cards,
    winsNeeded: m.winsNeeded,
  });
}

export function refreshOffers(m: MatchState): MatchState {
  return {
    ...m,
    offers: { a: offersForSide(m, 'a'), b: offersForSide(m, 'b') },
    picked: { a: null, b: null },
  };
}

/**
 * Comeback B — spend the Rally.
 *
 * Redraws this side's offer, once, visibly. The count goes into the offer seed
 * rather than into any hidden state, so the redrawn offer is the same on both
 * machines and the server can validate a pick against it without being told.
 */
export function spendRally(m: MatchState, side: Side): MatchState {
  if (m.phase !== 'offer') return m;
  if (m.picked[side] !== null) return m;
  if (!holdsRally(m, side)) return m;
  const next: MatchState = { ...m, rerolls: { ...m.rerolls, [side]: m.rerolls[side] + 1 } };
  return { ...next, offers: { ...next.offers, [side]: offersForSide(next, side) } };
}

/** Records one side's choice. Refuses anything that was not on that side's offer. */
export function choose(m: MatchState, side: Side, cardId: string): MatchState {
  if (m.phase !== 'offer') return m;
  if (m.picked[side] !== null) return m;
  const card = m.offers[side].find((c) => c.id === cardId);
  if (!card) return m;
  return { ...m, picked: { ...m.picked, [side]: card } };
}

export function bothChosen(m: MatchState): boolean {
  return m.picked.a !== null && m.picked.b !== null;
}

/**
 * Both cards are in: fold them into the ledgers and move to the field.
 *
 * The pick lands **before** the battle, so the card you just took fights in the
 * round you took it — which is what makes a pick feel like a decision rather
 * than an investment.
 */
export function commitPicks(m: MatchState): MatchState {
  if (!bothChosen(m)) return m;
  return {
    ...m,
    phase: 'battle',
    ledgers: {
      a: addPick(m.ledgers.a, m.picked.a!, m.round, m.cards, m.winsNeeded, holdsWildcard(m, 'a')),
      b: addPick(m.ledgers.b, m.picked.b!, m.round, m.cards, m.winsNeeded, holdsWildcard(m, 'b')),
    },
  };
}

/** The round is fought. Score it, and either set up the next one or end the match. */
export function scoreRound(
  m: MatchState,
  winner: Side | 'draw',
  remaining: Record<Side, number>,
): MatchState {
  const score = {
    a: m.score.a + (winner === 'a' ? 1 : 0),
    b: m.score.b + (winner === 'b' ? 1 : 0),
  };
  const outcome: RoundOutcome = {
    round: m.round,
    picks: { a: m.picked.a!, b: m.picked.b! },
    winner,
    remaining,
  };
  // The Rally meter climbs on a loss and empties on a win, so it can never bank
  // into a runaway. A drawn round moves neither.
  const rallyMeter = {
    a: winner === 'a' ? 0 : winner === 'b' ? m.rallyMeter.a + 1 : m.rallyMeter.a,
    b: winner === 'b' ? 0 : winner === 'a' ? m.rallyMeter.b + 1 : m.rallyMeter.b,
  };
  const scored: MatchState = {
    ...m,
    score,
    rallyMeter,
    history: [...m.history, outcome],
    phase: 'roundResult',
  };

  // A drawn round costs both players a round without moving the score, which is
  // why the match can reach round 7 at less than 3–3 and must still terminate.
  if (matchWinner(score, m.round + 1, m.winsNeeded) !== null) return { ...scored, phase: 'over' };
  return scored;
}

/** Leaves the round-result banner and opens the next round's offer. */
export function nextRound(m: MatchState): MatchState {
  if (m.phase === 'over') return m;
  return refreshOffers({ ...m, round: m.round + 1, phase: 'offer', rerolls: { a: 0, b: 0 } });
}

export function winnerOf(m: MatchState): Side | 'draw' | null {
  return matchWinner(m.score, m.round + (m.phase === 'over' ? 1 : 0), m.winsNeeded);
}

export function finalClash(m: MatchState): boolean {
  return isFinalClash(m.score, m.round, m.winsNeeded);
}

/** Every distinct unit either side has fielded — what the codex unlocks from. */
export function allFielded(m: MatchState): string[] {
  return [...new Set([...m.ledgers.a.squads, ...m.ledgers.b.squads].map((e) => e.unitId))];
}

export { ROUNDS_MAX };
