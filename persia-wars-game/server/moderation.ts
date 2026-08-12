/**
 * Player-name moderation.
 *
 * On a LAN test this did not matter — everyone in the room knew each other. On
 * the open internet it does: names are shown to strangers, and the audience is
 * nine to fourteen. This is the minimum that should exist before the game is
 * reachable from outside the office.
 *
 * IMPORTANT — this is a MECHANISM with a starter list, not a finished filter.
 * The normalisation below is the part worth keeping; the word list needs
 * replacing with a maintained multi-language one before any public launch.
 * It currently covers English only, and the audience includes Farsi speakers.
 */

/**
 * Collapses the tricks used to slip a word past a literal match: character
 * substitution, padding, repeats and mixed case. "s_p-a-m" and "5paaam" both
 * normalise to "spam".
 */
export function normalizeForMatch(raw: string): string {
  return raw
    .toLowerCase()
    .replace(/[àáâãäå]/g, 'a')
    .replace(/[èéêë]/g, 'e')
    .replace(/[ìíîï]/g, 'i')
    .replace(/[òóôõö]/g, 'o')
    .replace(/[ùúûü]/g, 'u')
    .replace(/[4@]/g, 'a')
    .replace(/[3€]/g, 'e')
    .replace(/[1!|]/g, 'i')
    .replace(/[0]/g, 'o')
    .replace(/[5$]/g, 's')
    .replace(/[7]/g, 't')
    .replace(/[^a-z]/g, '')
    // Collapse runs so "fuuuuck" matches "fuck".
    .replace(/(.)\1{1,}/g, '$1');
}

/** Clearly offensive terms. Starter set — replace with a maintained list. */
const BANNED = [
  'fuck', 'shit', 'cunt', 'bitch', 'dick', 'cock', 'pussy', 'whore', 'slut',
  'rape', 'nigger', 'nigga', 'faggot', 'retard', 'nazi', 'hitler', 'kys',
  'porn', 'sex', 'penis', 'vagina', 'anal',
];

/**
 * Names that would let someone pose as the game, a moderator, or another
 * player's authority. Distinct from profanity: this is impersonation, and in a
 * children's product it is the more dangerous of the two.
 */
const RESERVED = [
  'admin', 'administrator', 'moderator', 'mod', 'staff', 'official',
  'support', 'system', 'server', 'persiaatwar', 'gamemaster', 'owner',
];

/**
 * The lists must be normalised too, or entries never match.
 *
 * `normalizeForMatch` collapses repeated letters, so an input of "nigger"
 * arrives as "niger" and a raw list entry of "nigger" would never fire — the
 * filter silently passed several of the worst words it exists to catch. Both
 * sides go through the same function so that cannot happen again.
 */
const BANNED_N = [...new Set(BANNED.map(normalizeForMatch))].filter(Boolean);
const RESERVED_N = [...new Set(RESERVED.map(normalizeForMatch))].filter(Boolean);

export type NameVerdict = { ok: true } | { ok: false; reason: string };

export function checkName(raw: string): NameVerdict {
  const norm = normalizeForMatch(raw);
  if (norm.length === 0) return { ok: false, reason: 'Pick a name with some letters in it.' };

  for (const word of BANNED_N) {
    if (norm.includes(word)) return { ok: false, reason: 'That name is not allowed here.' };
  }
  for (const word of RESERVED_N) {
    if (norm === word || norm.startsWith(word)) {
      return { ok: false, reason: 'That name is reserved.' };
    }
  }
  return { ok: true };
}
