import { bookOne, capitalOrder, getMission } from '../content';
import type { Mission, MissionReward } from '../content/types';
import type { Side } from '../sim/roundCore.ts';

/**
 * The Chronicle campaign — Book One, Rise of Cyrus.
 *
 * Two chapters of seven missions. Concept v0.2 §9.
 *
 * The rule that shapes everything here is v0.1 §5.1: **campaign rewards unlock
 * breadth of choice, and must never create a statistical advantage in ranked.**
 * So a mission can give you a card you did not have, a trait, a doctrine, a
 * commander or a piece of your capital — and nothing else. There is no reward
 * in this file that makes a card you already own hit harder.
 */

export interface CampaignState {
  /** Mission ids finished, in any order. */
  completed: string[];
  /**
   * Counter-History: the book replayed from the Median side. v0.1 §4 — it opens
   * only after the historical path is finished, so nobody meets the alternate
   * version before the documented one.
   */
  counterHistory: boolean;
  /** Missions finished on the Median side. Kept apart from the real book. */
  counterCompleted: string[];
  /** For `choice` missions: which branch was taken. */
  choices: Record<string, string>;
  /** Capital pieces built. */
  capital: string[];
  /** Commanders the campaign has opened, on top of whatever the ladder opens. */
  commanders: string[];
}

export function freshCampaign(): CampaignState {
  return {
    completed: [],
    counterHistory: false,
    counterCompleted: [],
    choices: {},
    capital: [],
    commanders: [],
  };
}

/** The book is finished on its historical path — Counter-History may open. */
export function bookFinished(c: CampaignState): boolean {
  return bookOne.every((m) => c.completed.includes(m.id));
}

/** Which list of finished missions applies, given the mode being played. */
function doneList(c: CampaignState): string[] {
  return c.counterHistory ? c.counterCompleted : c.completed;
}

/**
 * Missions unlock strictly in order. A book that can be played out of sequence
 * cannot tell a story, and this one is a story before it is a ladder.
 *
 * Counter-History runs the same order over its own progress list, so finishing
 * the historical book does not hand the player a finished Median one.
 */
export function isUnlocked(mission: Mission, c: CampaignState): boolean {
  if (mission.number === 1) return true;
  const previous = bookOne.find((m) => m.number === mission.number - 1);
  return previous ? doneList(c).includes(previous.id) : false;
}

export function isComplete(mission: Mission, c: CampaignState): boolean {
  return doneList(c).includes(mission.id);
}

/** Turn Counter-History on or off. Refuses to open before the book is finished. */
export function setCounterHistory(c: CampaignState, on: boolean): CampaignState {
  if (on && !bookFinished(c)) return c;
  return { ...c, counterHistory: on };
}

/** The next mission to play, or null when the book is finished. */
export function nextMission(c: CampaignState): Mission | null {
  const done = doneList(c);
  return bookOne.find((m) => !done.includes(m.id)) ?? null;
}

export function bookProgress(c: CampaignState): { done: number; total: number } {
  const done = doneList(c);
  return {
    done: done.filter((id) => bookOne.some((m) => m.id === id)).length,
    total: bookOne.length,
  };
}

export function chapterOf(chapter: 1 | 2): Mission[] {
  return bookOne.filter((m) => m.chapter === chapter);
}

/**
 * Did the mission's objective get met?
 *
 * `survive` is the one that matters. Mission 10 asks the player to get their
 * army out rather than to destroy anybody, and taking a single round is enough —
 * a campaign that only ever rewards annihilation cannot teach that a retreat
 * was sometimes the right answer, which is most of what actually happened.
 */
export function missionSucceeded(
  mission: Mission,
  score: Record<Side, number>,
  mySide: Side,
): boolean {
  if (mission.objective === 'choice') return true;
  if (mission.objective === 'survive') return score[mySide] >= 1;
  return score[mySide] >= mission.winsNeeded;
}

/** What a mission hands over. A `choice` mission's reward depends on the branch. */
export function rewardFor(mission: Mission, choiceId?: string): MissionReward | null {
  if (mission.objective === 'choice') {
    return mission.choices?.find((c) => c.id === choiceId)?.reward ?? null;
  }
  return mission.reward;
}

/** Applies a finished mission. Pure — the caller decides whether to keep it. */
export function completeMission(
  c: CampaignState,
  missionId: string,
  choiceId?: string,
): CampaignState {
  if (doneList(c).includes(missionId)) return c;

  // Counter-History records progress separately and awards nothing. It is a
  // second reading of the same book, not a second helping of rewards — and its
  // outcomes are alternate history, which should not pay.
  if (c.counterHistory) {
    return { ...c, counterCompleted: [...c.counterCompleted, missionId] };
  }

  const mission = getMission(missionId);
  const reward = rewardFor(mission, choiceId);
  const next: CampaignState = {
    ...c,
    completed: [...c.completed, missionId],
    choices: choiceId ? { ...c.choices, [missionId]: choiceId } : c.choices,
    capital: [...c.capital],
    commanders: [...c.commanders],
  };
  if (reward?.kind === 'capital' && !next.capital.includes(reward.id)) next.capital.push(reward.id);
  if (reward?.kind === 'commander' && !next.commanders.includes(reward.id)) {
    next.commanders.push(reward.id);
  }
  return next;
}

/**
 * Capital pieces in build order, with what has been built.
 *
 * The camp becomes Pasargadae as the book runs — v0.1 §3.3. It is a narrative
 * and cosmetic layer and nothing here is ever read by the simulation.
 */
export function capitalState(c: CampaignState): { id: string; built: boolean }[] {
  return capitalOrder.map((piece) => ({ id: piece.id, built: c.capital.includes(piece.id) }));
}

/** How far the capital has come, 0–1, for the lobby's progress line. */
export function capitalProgress(c: CampaignState): number {
  return capitalOrder.length === 0 ? 0 : c.capital.length / capitalOrder.length;
}
