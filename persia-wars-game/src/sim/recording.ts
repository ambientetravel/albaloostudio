import { getBattle, getCommander } from '../content';
import { simulate, type Squad } from './battle';
import {
  choose,
  commitPicks,
  nextRound,
  scoreRound,
  spendRally,
  startMatch,
  type MatchState,
} from './match';
import { makeRng } from './rng.ts';
import { roundSeedFor, type Side } from './roundCore.ts';

/**
 * Match recordings.
 *
 * A match here is fully determined by its inputs: the battle, the seed, the
 * arena, both decks, both commanders, and then, each round, what each side
 * rerolled and what each side took. The simulation is a pure function of those
 * — `sim/` imports neither React nor Pixi and never reads a clock — so there is
 * no need to store what HAPPENED. Store the decisions and re-run them.
 *
 * That is the difference between a few hundred bytes and a log of every blow
 * struck, and it is the reason `replay` can be asserted equal to the original
 * state rather than merely similar to it.
 *
 * The recorder exists because M6's `RecordedRivalDecisionProvider` was specified
 * as "reading the existing replay log" and no such log was ever built. It is
 * also independently useful: a bug in a real match becomes reproducible instead
 * of a guess at a seed.
 */

/** Bumped whenever the shape below changes. Old recordings are then dropped. */
export const RECORDING_VERSION = 1;

export interface RecordedRound {
  /**
   * Rallies spent before choosing. These feed the offer seed, so a replay that
   * skipped them would derive a different offer and reject the recorded pick.
   */
  rerolls: Record<Side, number>;
  /** The card id each side took. */
  picks: Record<Side, string>;
}

export interface MatchRecording {
  v: number;
  battleId: string;
  seed: number;
  arena: number;
  decks: Record<Side, string[]>;
  commanders: Record<Side, string>;
  winsNeeded: number;
  missionId: string | null;
  rounds: RecordedRound[];
  /** Which side, if either, a human was playing. Null for AI-vs-AI. */
  human: Side | null;
}

/** Opens a recording from a match that has just started. */
export function beginRecording(m: MatchState, human: Side | null = 'a'): MatchRecording {
  return {
    v: RECORDING_VERSION,
    battleId: m.battleId,
    seed: m.seed,
    arena: m.arena,
    decks: { a: [...m.decks.a], b: [...m.decks.b] },
    commanders: { ...m.commanders },
    winsNeeded: m.winsNeeded,
    missionId: m.missionId,
    rounds: [],
    human,
  };
}

/**
 * Appends the round that is about to be committed.
 *
 * Call this while both sides have chosen and BEFORE `commitPicks`, which is the
 * only moment when the picks and the reroll counts that produced them are both
 * still on the state — `nextRound` clears the rerolls.
 */
export function recordRound(rec: MatchRecording, m: MatchState): MatchRecording {
  if (m.picked.a === null || m.picked.b === null) return rec;
  // Re-recording the same round would desync a replay by one, and a resumed or
  // re-entered round is not a new decision.
  if (rec.rounds.length >= m.round) return rec;
  return {
    ...rec,
    rounds: [
      ...rec.rounds,
      {
        rerolls: { ...m.rerolls },
        picks: { a: m.picked.a.id, b: m.picked.b.id },
      },
    ],
  };
}

/** One round's squad, exactly as the live game builds it. */
function squadFor(m: MatchState, side: Side): Squad {
  const c = getCommander(m.commanders[side]);
  return {
    side,
    units: m.ledgers[side].squads,
    doctrines: m.ledgers[side].doctrines,
    passive: c.passive.id,
    order: c.order.id,
  };
}

/**
 * Re-runs a recording and returns the state it ends in.
 *
 * Throws rather than limping if a recorded pick is not on the offer it faces.
 * A replay that quietly substituted a different card would still produce a
 * plausible-looking match, and a plausible-looking wrong answer is worse here
 * than a crash: the whole value of a recording is that it IS the match.
 */
export function replay(rec: MatchRecording): MatchState {
  if (rec.v !== RECORDING_VERSION) {
    throw new Error(`recording is version ${rec.v}, this build reads ${RECORDING_VERSION}`);
  }
  const battle = getBattle(rec.battleId);
  let m = startMatch(battle, rec.seed, rec.arena, rec.decks, rec.commanders, {
    winsNeeded: rec.winsNeeded,
    missionId: rec.missionId ?? undefined,
  });

  for (const [i, r] of rec.rounds.entries()) {
    for (const side of ['a', 'b'] as const) {
      for (let n = 0; n < r.rerolls[side]; n += 1) {
        const before = m.rerolls[side];
        m = spendRally(m, side);
        if (m.rerolls[side] === before) {
          throw new Error(`round ${i + 1}: side ${side} could not spend a recorded rally`);
        }
      }
      const chosen = choose(m, side, r.picks[side]);
      if (chosen === m) {
        throw new Error(`round ${i + 1}: side ${side} cannot take "${r.picks[side]}" — not on offer`);
      }
      m = chosen;
    }
    m = commitPicks(m);
    const log = simulate(battle, squadFor(m, 'a'), squadFor(m, 'b'), roundSeedFor(m.seed, m.round), m.round);
    m = scoreRound(m, log.winner, log.remaining);
    if (m.phase !== 'over') m = nextRound(m);
  }
  return m;
}

/**
 * A rival that plays back what a person actually did.
 *
 * Returns `recorded: false` when it had to fall back, which is not a detail:
 * §10's honesty rule means a rival that is part recording and part scoring
 * function must never be presented as a person, and the caller cannot know
 * which it got unless this says so.
 *
 * Falling back is normal rather than exceptional. A recording is a decision
 * SEQUENCE, not a script for the whole world — face it with a different seed,
 * a different opponent, or a longer match and the offer it meets will often not
 * contain the card it took.
 */
export interface RivalDecision {
  cardId: string;
  /** True only if the card came from the recording AND was legal here. */
  recorded: boolean;
}

export function recordedRivalPick(
  rec: MatchRecording,
  m: MatchState,
  playing: Side,
  fallback: () => string,
): RivalDecision {
  // Copy the HUMAN's decisions, not whatever sat opposite them. A recorded
  // rival exists to play like a person; reading the side it happens to occupy
  // would replay the old match's bot instead, which is the AI it is replacing.
  const from = rec.human ?? 'a';
  const wanted = rec.rounds[m.round - 1]?.picks[from];
  if (wanted && m.offers[playing].some((c) => c.id === wanted)) {
    return { cardId: wanted, recorded: true };
  }
  return { cardId: fallback(), recorded: false };
}

/**
 * Chooses a tape to drive a rival, or null.
 *
 * Only a tape from the same battle and the same arena is eligible. Offers are
 * derived from the draft pool, which is a function of both, so a tape from
 * elsewhere would miss on nearly every round — the rival would be the ordinary
 * scoring function wearing a recorded rival's label, which is exactly the kind
 * of claim §10 exists to stop.
 *
 * It also declines about half the time, from the match seed, so a player who
 * has recordings does not face their own last draft every single match.
 */
export function chooseTape(
  all: MatchRecording[],
  battleId: string,
  arena: number,
  seed: number,
): MatchRecording | null {
  const eligible = all.filter(
    (r) => r.v === RECORDING_VERSION && r.battleId === battleId && r.arena === arena && r.rounds.length > 0,
  );
  if (eligible.length === 0) return null;
  const rng = makeRng((seed ^ 0x2545f491) >>> 0);
  if (rng.next() < 0.5) return null;
  return eligible[rng.int(eligible.length)];
}

/** Serialised size in bytes — the claim that a recording is small, checked. */
export function recordingBytes(rec: MatchRecording): number {
  return JSON.stringify(rec).length;
}
