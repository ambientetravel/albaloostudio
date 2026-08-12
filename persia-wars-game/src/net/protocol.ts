/**
 * Wire protocol between the browser and the matchmaking server.
 *
 * Design note: the server never simulates a battle and never sends card lists.
 * Both clients derive every offer from the seed and the public match state with
 * the shared code in sim/roundCore.ts, and both run the same deterministic sim
 * on the same seed, so they reach the same result independently. The server's
 * job is matchmaking, round order, and relaying picks it has validated against
 * that same derivation.
 *
 * Picks inside a round are SIMULTANEOUS, so the server holds both and releases
 * them together — otherwise relaying the first would tell the second player what
 * they were up against before they had chosen.
 *
 * Because the server does not simulate, it learns each round's winner from the
 * clients. Both must report the same winner. If they disagree the match is a
 * desync and is ended rather than allowed to drift — which makes this the
 * cheapest desync detector we have.
 */

export type Side = 'a' | 'b';

export interface PlayerInfo {
  name: string;
  /** Index into the avatar table in ui/avatars.ts. */
  avatar: number;
}

export type ClientMessage =
  // `arena` is the player's ladder rung. The server takes the LOWER of the two
  // in a match, so nobody ever faces a card they have not unlocked.
  // `deck` is the warband, which seeds slot A of each offer — the server needs
  // it to derive, and therefore to validate, the same three cards.
  | { t: 'hello'; name: string; avatar: number; arena: number; deck: string[]; commander: string }
  | { t: 'queue' }
  | { t: 'cancelQueue' }
  | { t: 'pick'; unitId: string }
  // Comeback B. The server checks the meter itself and echoes to both, so the
  // reroll is visible to the opponent — a rule, not a rubber band.
  | { t: 'rally' }
  | { t: 'roundResult'; round: number; winner: Side | 'draw' }
  | { t: 'leaveMatch' }
  | { t: 'pong' };

export type ServerMessage =
  | { t: 'welcome'; playerId: string; online: number; queued: number }
  | { t: 'stats'; online: number; queued: number }
  | { t: 'queued' }
  | { t: 'queueCancelled' }
  | {
      t: 'match';
      matchId: string;
      battleId: string;
      seed: number;
      you: Side;
      opponent: PlayerInfo;
      /** The arena this match is fought in — gates the draft pool for both. */
      arena: number;
      /** The opponent's warband, so this client can derive their offers too. */
      opponentDeck: string[];
      /** The opponent's commander — decides their affinity and their passive. */
      opponentCommander: string;
    }
  // Both choices, released together once both have arrived.
  | { t: 'roundPicks'; round: number; picks: Record<Side, string> }
  | { t: 'rallied'; side: Side; round: number }
  // A new round's offer window is open. `deadline` is a wall clock the client
  // counts down to; the server picks for anyone who misses it.
  | { t: 'roundOpen'; round: number; deadline: number }
  | { t: 'opponentLeft' }
  | { t: 'error'; message: string }
  | { t: 'ping' };

/** Seconds a player gets per round to choose before the server chooses for them. */
export const TURN_SECONDS = 25;

export const NAME_MIN = 2;
export const NAME_MAX = 14;

/**
 * Names are shown to strangers, so they are restricted to letters, digits and a
 * couple of separators. This is a shape check, not a profanity filter — a
 * moderation list is still outstanding before any public launch.
 */
export function sanitizeName(raw: string): string {
  return raw
    .replace(/[^\p{L}\p{N} _-]/gu, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, NAME_MAX);
}

export function isValidName(raw: string): boolean {
  const n = sanitizeName(raw);
  return n.length >= NAME_MIN && n.length <= NAME_MAX;
}
