/**
 * The age gate, and the one thing that actually follows from it.
 *
 * NOT legal advice, and the thresholds below need a lawyer's eye before any
 * store submission — COPPA draws its line at 13, GDPR-K lets each member state
 * choose anywhere from 13 to 16, and the UK Age Appropriate Design Code applies
 * to under-18s regardless. What this module provides is the mechanism and a
 * defensible default; the numbers are a starting position, not a ruling.
 *
 * The substantive risk in this game is small and specific. Almost everything is
 * local — collection, trophies, settings, match recordings all live in
 * localStorage and never leave the device. Exactly one thing is broadcast to a
 * stranger: the display name. And the first screen on a fresh install currently
 * says "Choose your name — other players will see this when you play online",
 * with the placeholder "Your name", to an audience of nine-to-fourteen-year-olds.
 * That is the hole. A gate that did not close it would be theatre.
 *
 * Two deliberate choices:
 *
 * 1. **Ask for a birth YEAR, not "are you over 13?"** A yes/no question with an
 *    obvious right answer teaches a child to lie to it. A neutral question does
 *    not signal which answer unlocks more.
 * 2. **Store only the bracket, never the date.** A birth date is precisely the
 *    kind of personal data a children's app should not be holding, and nothing
 *    here needs it. The cost is that a child who turns 13 stays in the younger
 *    bracket until they clear the app's data, which is the safe direction to
 *    err in.
 */

export type AgeBracket = 'child' | 'teen' | 'adult';

/** COPPA's line. Under this, no free-text name reaches another player. */
export const CHILD_UNDER = 13;
/**
 * GDPR-K's ceiling. Between the two lines a member state may or may not require
 * parental consent, so this bracket is treated as a child for the name rule and
 * separated only so a later, better-informed decision has somewhere to land.
 */
export const TEEN_UNDER = 16;

/** A year clearly out of range, so a mistyped 19 or 202 cannot pass as valid. */
export const EARLIEST_YEAR = 1900;

export function bracketFor(birthYear: number, thisYear: number): AgeBracket {
  const age = thisYear - birthYear;
  if (age < CHILD_UNDER) return 'child';
  if (age < TEEN_UNDER) return 'teen';
  return 'adult';
}

export function isPlausibleYear(birthYear: number, thisYear: number): boolean {
  return (
    Number.isInteger(birthYear) && birthYear >= EARLIEST_YEAR && birthYear <= thisYear
  );
}

/**
 * Whether this player may broadcast a name they typed themselves.
 *
 * Only adults. A teen is included in the restriction on purpose: the GDPR-K
 * line moves between 13 and 16 depending on the country, and the safe reading is
 * the one that does not depend on knowing where the player is.
 */
export function mayTypeOwnName(bracket: AgeBracket): boolean {
  return bracket === 'adult';
}

/**
 * Names for players who may not type their own.
 *
 * Adjective plus noun, both drawn from the game's own world, so an assigned
 * name is still part of the fiction rather than a serial number — 'Swift
 * Immortal' reads as a title a child would happily wear, 'Player_4417' does not.
 *
 * Every combination must fit NAME_MAX (14). 'Far-seeing' and 'Patient' were in
 * the first list and pushed 'Far-seeing Griffin' to 18 characters — the server
 * would have rejected it and a child would have been locked out of online play
 * altogether, turning a restriction into a ban. The test measures this rather
 * than trusting the eye.
 *
 * Deliberately NOT the AI opponent list in sim/ai.ts. Those are real historical
 * people and they name the computer; a human wearing one would blur the single
 * distinction the game works hardest to keep.
 */
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
 * A stable assigned name for a number — same input, same name.
 *
 * The step is coprime with the total so consecutive numbers walk the whole set
 * rather than marching along one row. Stepping by 1 changed only the noun, so a
 * child tapping 'give me a different name' got Swift Lion, Swift Falcon, Swift
 * Archer, Swift Rider... twelve times before the adjective ever moved.
 */
const STRIDE = 37;

export function assignedName(n: number): string {
  const i = (Math.abs(Math.trunc(n)) * STRIDE) % ASSIGNED_NAME_COUNT;
  return `${ADJECTIVES[Math.floor(i / NOUNS.length)]} ${NOUNS[i % NOUNS.length]}`;
}

/**
 * Whether a name is one this module would hand out.
 *
 * The store uses it to accept the name a restricted player actually chose from
 * the shuffle, instead of recomputing a different one — which is what it did at
 * first, so the screen showed 'Swift Spear' and the save recorded 'Swift River'.
 */
export function isAssignedName(name: string): boolean {
  return ASSIGNED_SET.has(name);
}

/** Every assigned name, for the test that checks they all pass name validation. */
export function allAssignedNames(): string[] {
  return ADJECTIVES.flatMap((a) => NOUNS.map((n) => `${a} ${n}`));
}

const ASSIGNED_SET = new Set(allAssignedNames());
