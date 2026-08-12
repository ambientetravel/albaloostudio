import { content, isPlayable } from '../content';

/**
 * Progression, the soft economy, and card levels.
 *
 * Deliberately contains no real-money logic. Coins and gems are earned by
 * playing; the shop's real-money tiers are a display-only shell (see
 * src/ui/Shop.tsx and DECISIONS.md).
 */

export const MAX_CARD_LEVEL = 8;
export const DECK_SIZE = 4;

/** Duplicates needed to take a card from level N to N+1. */
const UPGRADE_COST: number[] = [0, 2, 4, 8, 16, 32, 64, 128];
/** Coins needed alongside the duplicates. */
const UPGRADE_COINS: number[] = [0, 50, 150, 400, 1000, 2200, 5000, 12000];

export interface CardState {
  count: number;
  level: number;
}

export function cardsToUpgrade(level: number): number {
  return UPGRADE_COST[Math.min(level, UPGRADE_COST.length - 1)] ?? Infinity;
}

export function coinsToUpgrade(level: number): number {
  return UPGRADE_COINS[Math.min(level, UPGRADE_COINS.length - 1)] ?? Infinity;
}

export function canUpgrade(card: CardState, coins: number): boolean {
  if (card.level >= MAX_CARD_LEVEL) return false;
  return card.count >= cardsToUpgrade(card.level) && coins >= coinsToUpgrade(card.level);
}

/**
 * Card levels are DELIBERATELY NOT APPLIED to the battle simulation.
 *
 * Two reasons, and both matter more than the extra progression hook:
 *  1. Online matches stay in lockstep because both clients simulate from the
 *     same seed and the same squads. Feeding a private collection into the sim
 *     would desync them unless levels were sent and trusted over the wire.
 *  2. A card you ground for should not beat a card you understood. The game
 *     teaches the counter triangle; letting levels override it teaches
 *     spending instead.
 *
 * Levels drive collection progress and the codex. If that ever changes, the
 * server has to become authoritative over stats first.
 */
export function levelMultiplier(level: number): number {
  return 1 + (level - 1) * 0.06;
}

/** Highest arena whose trophy requirement this player has met. */
export function arenaForTrophies(trophies: number): number {
  let arena = 1;
  for (const a of content.arenas) if (trophies >= a.trophies) arena = a.id;
  return arena;
}

/** Trophies needed for the next arena, or null at the top of the ladder. */
export function nextArenaAt(trophies: number): { id: number; trophies: number } | null {
  const next = content.arenas.find((a) => a.trophies > trophies);
  return next ? { id: next.id, trophies: next.trophies } : null;
}

/** Progress through the current arena band, 0–1, for the lobby's trophy bar. */
export function arenaProgress(trophies: number): { current: number; target: number; frac: number } {
  const arena = arenaForTrophies(trophies);
  const floor = content.arenas.find((a) => a.id === arena)?.trophies ?? 0;
  const next = nextArenaAt(trophies);
  if (!next) return { current: trophies, target: trophies, frac: 1 };
  const span = next.trophies - floor;
  return { current: trophies, target: next.trophies, frac: span > 0 ? (trophies - floor) / span : 1 };
}

export const TROPHY_WIN = 30;
export const TROPHY_LOSS = -20;
export const COINS_WIN = 180;
export const COINS_LOSS = 60;

/** Trophies never go below zero — a beginner should not be able to get stuck. */
export function applyTrophyDelta(trophies: number, won: boolean): number {
  return Math.max(0, trophies + (won ? TROPHY_WIN : TROPHY_LOSS));
}

/**
 * Cards awarded after a battle, drawn from what the player's arena has unlocked.
 * Seeded so the reward for a given match is the same if it is ever replayed.
 */
export function rollCardReward(arena: number, seed: number, howMany: number): string[] {
  const pool = content.units.filter((u) => isPlayable(u.confidence) && u.arena <= arena).map((u) => u.id);
  if (pool.length === 0) return [];
  const out: string[] = [];
  let s = seed >>> 0;
  for (let i = 0; i < howMany; i++) {
    s = (s * 1664525 + 1013904223) >>> 0;
    out.push(pool[s % pool.length]);
  }
  return out;
}
