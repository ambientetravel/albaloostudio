/**
 * Every player's display name, chosen from a closed set.
 *
 * Nobody types a name in this game, and there is no age gate deciding who may.
 * An earlier pass built one — a birth-year question, three brackets, a typed
 * name for adults only — and it was the wrong shape for this game:
 *
 *  - The audience is nine to fourteen. An adult path serves almost nobody, and
 *    it existed only to grant the one privilege that carries all of the risk.
 *  - The bracket was read for exactly one decision. Nothing else in the game
 *    ever needed to know a player's age.
 *  - §17 rules out chat, clans and subscriptions, so nothing else ever will.
 *
 * A gate manages a risk. Removing the free-text field deletes it. What is left
 * is smaller in every direction that matters: one screen fewer before a child
 * can play, no birth year asked, no age stored even as a bracket, and no
 * user-generated text anywhere in the product — which means no profanity list
 * to build, maintain, or fail to keep current in every language it ships in.
 *
 * The set is closed on purpose, so the SERVER can check membership rather than
 * shape. A modified client cannot send a name that is not on this list.
 *
 * This is not a loss of expression. A player still picks their title from 144,
 * plus a badge and a banner, and 'Quiet Falcon' is a better name for a
 * nine-year-old's warband than anything they would have typed.
 */

/** Every combination must fit the 14-character wire limit — asserted by a test. */
const ADJECTIVES = [
  'Swift', 'Bright', 'Bold', 'Quiet', 'Gold', 'Iron',
  'Steady', 'Clever', 'Keen', 'Sudden', 'Silver', 'True',
];

const NOUNS = [
  'Lion', 'Falcon', 'Archer', 'Rider', 'Shield', 'Spear',
  'Bull', 'Ibex', 'Griffin', 'Banner', 'Cedar', 'River',
];

export const ASSIGNED_NAME_COUNT = ADJECTIVES.length * NOUNS.length;

/**
 * The step is coprime with the total so consecutive numbers walk the whole set
 * rather than marching along one row. Stepping by 1 changed only the noun, so a
 * child tapping 'give me a different name' saw Swift Lion, Swift Falcon, Swift
 * Archer... twelve times before the adjective ever moved.
 */
const STRIDE = 37;

/** A stable name for a number — same input, same name. */
export function assignedName(n: number): string {
  const i = (Math.abs(Math.trunc(n)) * STRIDE) % ASSIGNED_NAME_COUNT;
  return `${ADJECTIVES[Math.floor(i / NOUNS.length)]} ${NOUNS[i % NOUNS.length]}`;
}

export function allAssignedNames(): string[] {
  return ADJECTIVES.flatMap((a) => NOUNS.map((n) => `${a} ${n}`));
}

const ASSIGNED_SET = new Set(allAssignedNames());

/**
 * Whether a name is one this module hands out.
 *
 * Used by the store to keep the name a player actually chose from the shuffle,
 * and by the SERVER to reject anything else outright. That second use is the
 * reason the set is closed: membership is checkable, a shape is not.
 */
export function isAssignedName(name: string): boolean {
  return ASSIGNED_SET.has(name);
}
