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
  style: RivalStyle;
}

/**
 * How a rival builds an army.
 *
 * Skill alone made every opponent the same opponent — a single number is a hit
 * rate, not a habit, so twenty-four differently-named rivals all drafted
 * identically and the offline game had one shape.
 *
 * The three styles were FIRST written as tall / counter-picking / wide, and
 * measuring them threw both of those ideas out:
 *
 *  - Counter-weighting is not a personality, it is competence. The rival that
 *    weighted the matchup triangle highest beat the one that weighted it lowest
 *    90% of the time. All three now weight it identically, and only then did
 *    every pairing settle inside 35-65%.
 *
 * What survives is a difference in which KIND of card a rival spends its pick
 * on — the three kinds M2 built — and, with it, a real difference in rank.
 * Measured over 90 matches each, all against the same opponent:
 *
 *   massing  — deepens. Highest average rank (1.36 against planning's 1.16)
 *              and almost no doctrines (0.17). It stacks what it has.
 *   drilling — drills. Roughly twice the traits of anyone else (1.09 against
 *              0.61 and 0.44), bought with the picks it does not spend on rank.
 *   planning — spreads. Nearly six times massing's doctrines (0.99 against
 *              0.17), the widest class spread, and the lowest rank of the three.
 *
 * One caution for anyone tuning this. An earlier pass ALSO stopped charging a
 * rank-up the mixed-front penalty, on the reasoning that deepening a squad does
 * not widen the front. It is a fair reading of the scorer, and it was reverted:
 * it changes what the AI picks under NEUTRAL weights too, and it broke the
 * 200-match commander sweep M3 was accepted on. It also flattened the rank
 * difference above to nothing (1.42/1.39/1.40) and briefly made 'goes tall'
 * look impossible, which it is not. See DECISIONS.md.
 */
export type RivalStyle = 'massing' | 'drilling' | 'planning';

/** Shown on the nameplate, so a rival's habit is learnable rather than hidden. */
export const STYLE_LABEL: Record<RivalStyle, string> = {
  massing: 'masses its ranks',
  drilling: 'drills its troops',
  planning: 'plans the whole line',
};

interface StyleWeights {
  /**
   * Multiplies the counter/countered term. Deliberately IDENTICAL across all
   * three — see above; varying it produced a 90/10 matchup, not a personality.
   */
  matchup: number;
  /** Multiplies what a rank-up on an existing squad is worth. */
  rank: number;
  /** How much a class it already fields is penalised. */
  sameClass: number;
  /** Multiplies a Doctrine's worth, which scales with army size. */
  doctrine: number;
  /** Multiplies an Upgrade's worth. */
  upgrade: number;
}

/**
 * The weights the AI used before styles existed.
 *
 * Kept as an explicit centre, and used whenever no opponent is supplied, so
 * that every balance figure already measured against this AI — the 200-match
 * commander sweep in M3, the exhaustion and pace numbers — still means what it
 * meant. A style is a deviation FROM something, and this is the something.
 */
const NEUTRAL: StyleWeights = { matchup: 1, rank: 1, sameClass: -6, doctrine: 1, upgrade: 1 };

const STYLE: Record<RivalStyle, StyleWeights> = {
  massing: { matchup: 1.6, rank: 2.8, sameClass: -2.5, doctrine: 0.7, upgrade: 0.95 },
  drilling: { matchup: 1.6, rank: 1.0, sameClass: -6, doctrine: 0.9, upgrade: 1.32 },
  planning: { matchup: 1.6, rank: 0.5, sameClass: -14, doctrine: 1.8, upgrade: 0.85 },
};

const STYLES: RivalStyle[] = ['massing', 'drilling', 'planning'];

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
    style: STYLES[rng.int(STYLES.length)],
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

  const w = opponent ? STYLE[opponent.style] : NEUTRAL;
  const ranked = offer
    .map((card) => ({ card, score: scoreOffer(card, m, side, enemyUnits, ownUnits, ownStrength, w) }))
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
  w: StyleWeights,
): number {
  if (card.kind === 'doctrine') {
    // A doctrine multiplies the army it is applied to, so it is worth more the
    // more army there is — and close to nothing on an empty field in round 1.
    return (14 + ownStrength * 0.9) * w.doctrine;
  }

  if (card.kind === 'upgrade') {
    const target = card.target ? getUnit(card.target) : null;
    if (!target) return 0;
    // A trait is worth roughly what a rank is worth on the same squad, which
    // makes slot B a real choice between going up and going sideways.
    return (scoreCandidate(target, enemyUnits, ownUnits, w) * 0.55 + 10) * w.upgrade;
  }

  const unit = getUnit(card.id);
  const tier = tierOf(m.ledgers[side], card.id);
  // NOTE: a rank-up is charged the mixed-front penalty even though it adds no
  // squad to the front, which is arguably double-counting. Lifting it was tried
  // and reverted: it changes what the AI picks with NEUTRAL weights too, and
  // the 200-match commander sweep in M3 was measured against those. It is a
  // real observation about the scorer, not a free fix — see DECISIONS.md.
  let score = scoreCandidate(unit, enemyUnits, ownUnits, w);
  // A rank is worth roughly what the extra multiplier buys, plus a little for
  // not widening the front — but never enough to always take it. The style
  // scales the SURPLUS rather than the whole score, so 'broad' still ranks up
  // when the alternative is bad rather than refusing on principle.
  if (tier > 0) {
    const gain = TIER_MULT[Math.min(tier, TIER_MULT.length - 1)] / TIER_MULT[tier - 1];
    score *= 1 + (gain - 1) * w.rank;
  }
  return score;
}

function scoreCandidate(candidate: Unit, enemy: Unit[], own: Unit[], w: StyleWeights): number {
  const base = candidate.atk * 1.5 + candidate.def + candidate.hp * 0.1;

  // How well it matches up against what the opponent has already taken.
  let matchup = 0;
  for (const e of enemy) {
    matchup += (counterMultiplier(candidate, e.class) - 1) * 14;
    matchup -= (counterMultiplier(e, candidate.class) - 1) * 10;
  }

  // Pressure toward — or away from — a mixed front. An army of one class loses
  // to its counter, but 'massing' is willing to take that bet.
  const sameClass = own.filter((u) => u.class === candidate.class).length;
  return base + matchup * w.matchup + sameClass * w.sameClass;
}
