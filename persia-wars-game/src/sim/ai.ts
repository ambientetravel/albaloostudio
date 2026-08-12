import type { Unit } from '../content/types';
import { getUnit } from '../content';
import { counterMultiplier } from './battle';
import type { MatchState } from './match';
import { TIER_MULT, tierOf, type OfferCard, type Side } from './roundCore.ts';
import { makeRng } from './rng.ts';

/**
 * The offline opponent.
 *
 * Until there are enough real players online, almost every match is against
 * this. So it is built to behave like a person rather than a solver: it has a
 * name and a badge, it takes an uneven amount of time to decide, and it makes
 * mistakes at a rate that falls as the player climbs the ladder.
 *
 * It is still always LABELLED as the computer. A child should never be misled
 * about whether the thing across the board is a person — that costs us nothing
 * and is the kind of thing a game for nine-year-olds should get right.
 */

export interface AiOpponent {
  name: string;
  avatar: number;
  /** 0 = plays badly on purpose, 1 = plays the best pick it can see. */
  skill: number;
}

/**
 * Names are drawn from Achaemenid-era history and the satrapy lists, so the
 * roster teaches something even when it is only a nameplate. No modern names,
 * nothing that could read as a real player's handle.
 */
const AI_NAMES = [
  'Aryabard', 'Vishtaspa', 'Gobryas', 'Otanes', 'Datis', 'Mardonius',
  'Artabazos', 'Hydarnes', 'Bagabigna', 'Spitamenes', 'Tiribazos', 'Pharnabaz',
  'Roxane', 'Atossa', 'Parysatis', 'Artystone', 'Amestris', 'Irdabama',
  'Zopyros', 'Megabyzos', 'Ariaramnes', 'Kambujiya', 'Bardiya', 'Vahyazdata',
];

/**
 * A stable opponent for a given match seed: the same seed always produces the
 * same name and badge, so a replay shows the same face.
 */
export function makeOpponent(seed: number, playerArena: number): AiOpponent {
  const rng = makeRng((seed ^ 0x7f4a7c15) >>> 0);
  // Skill climbs with the ladder: forgiving in Anshan, sharp by the Persian Gates.
  const base = 0.35 + Math.min(1, (playerArena - 1) / 12) * 0.5;
  return {
    name: AI_NAMES[rng.int(AI_NAMES.length)],
    avatar: rng.int(8),
    skill: Math.min(0.95, base + rng.range(-0.08, 0.08)),
  };
}

/**
 * How long the opponent "thinks" before picking, in milliseconds.
 *
 * A fixed delay reads as a machine immediately. Real people hesitate more on
 * the first pick of a round and on close calls, and sometimes just tap fast.
 */
export function thinkTime(step: number, seed: number, skill: number): number {
  const rng = makeRng((seed ^ ((step + 31) * 0x85ebca6b)) >>> 0);
  const snap = rng.next() < 0.18; // sometimes they just go
  if (snap) return rng.range(320, 620);
  // Later picks take longer — there is more board to read.
  const base = 700 + step * 90;
  const spread = rng.range(0.65, 1.7);
  // Stronger opponents deliberate a touch longer; it reads as care.
  return Math.round(base * spread * (0.85 + skill * 0.3));
}

/**
 * Picks a card for one round.
 *
 * Weights counters heavily and raw stats lightly, so a player who understands
 * the triangle beats it and a player who does not, does not. It values a rank
 * on something it already fields, and it values a trait or a doctrine — an
 * opponent that only ever took new units would leave two thirds of the card
 * system untested.
 */
export function aiRoundPick(m: MatchState, side: Side, opponent?: AiOpponent): string {
  const offer = m.offers[side];
  if (offer.length === 0) return '';
  const enemy: Side = side === 'a' ? 'b' : 'a';
  const enemyUnits = m.ledgers[enemy].squads.map((e) => getUnit(e.unitId));
  const ownUnits = m.ledgers[side].squads.map((e) => getUnit(e.unitId));
  const ownStrength = m.ledgers[side].squads.reduce(
    (n, e) => n + getUnit(e.unitId).atk * TIER_MULT[e.tier - 1],
    0,
  );

  const ranked = offer
    .map((card) => ({ card, score: scoreOffer(card, m, side, enemyUnits, ownUnits, ownStrength) }))
    .sort((a, b) => b.score - a.score);

  const skill = opponent?.skill ?? 0.8;
  const rng = makeRng((m.seed ^ ((m.round * 41 + (side === 'a' ? 0 : 17)) * 0xc2b2ae35)) >>> 0);

  // The mistake. A weaker opponent sometimes takes the second- or third-best
  // card — which is exactly what a person does when a card simply looks cool.
  if (ranked.length > 1 && rng.next() > skill) {
    const slip = rng.next() < 0.75 ? 1 : Math.min(2, ranked.length - 1);
    return ranked[slip].card.id;
  }
  return ranked[0].card.id;
}

function scoreOffer(
  card: OfferCard,
  m: MatchState,
  side: Side,
  enemyUnits: Unit[],
  ownUnits: Unit[],
  ownStrength: number,
): number {
  if (card.kind === 'doctrine') {
    // A doctrine multiplies the army it is applied to, so it is worth more the
    // more army there is — and close to nothing on an empty field in round 1.
    return 14 + ownStrength * 0.9;
  }

  if (card.kind === 'upgrade') {
    const target = card.target ? getUnit(card.target) : null;
    if (!target) return 0;
    // A trait is worth roughly what a rank is worth on the same squad, which
    // makes slot B a real choice between going up and going sideways.
    return scoreCandidate(target, enemyUnits, ownUnits) * 0.55 + 10;
  }

  const unit = getUnit(card.id);
  const tier = tierOf(m.ledgers[side], card.id);
  let score = scoreCandidate(unit, enemyUnits, ownUnits);
  // A rank is worth roughly what the extra multiplier buys, plus a little for
  // not widening the front — but never enough to always take it.
  if (tier > 0) score *= TIER_MULT[Math.min(tier, TIER_MULT.length - 1)] / TIER_MULT[tier - 1];
  return score;
}

function scoreCandidate(candidate: Unit, enemy: Unit[], own: Unit[]): number {
  const base = candidate.atk * 1.5 + candidate.def + candidate.hp * 0.1;

  // How well it matches up against what the opponent has already taken.
  let matchup = 0;
  for (const e of enemy) {
    matchup += (counterMultiplier(candidate, e.class) - 1) * 14;
    matchup -= (counterMultiplier(e, candidate.class) - 1) * 10;
  }

  // Mild pressure toward a mixed front — an army of one class loses to its counter.
  const sameClass = own.filter((u) => u.class === candidate.class).length;
  return base + matchup + sameClass * -6;
}
