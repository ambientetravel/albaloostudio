import { describe, expect, it } from 'vitest';
import { isValidName, sanitizeName } from '../net/protocol';
import {
  allAssignedNames,
  assignedName,
  isAssignedName,
  ASSIGNED_NAME_COUNT,
} from './playerNames';

/**
 * Player names.
 *
 * There is no age gate any more, and these tests are why the removal is safe
 * rather than merely simpler: nobody can put arbitrary text in front of another
 * player, whatever their age and whatever client they are running.
 */

describe('names come from a closed set', () => {
  it('offers enough that a lobby is not all one name', () => {
    expect(ASSIGNED_NAME_COUNT).toBeGreaterThanOrEqual(100);
    expect(new Set(allAssignedNames()).size).toBe(ASSIGNED_NAME_COUNT);
  });

  it('gives the same name for the same number', () => {
    expect(assignedName(42)).toBe(assignedName(42));
  });

  it('wraps rather than crashing on any integer', () => {
    for (const n of [0, -1, -999, 1e9, ASSIGNED_NAME_COUNT, ASSIGNED_NAME_COUNT * 3 + 5]) {
      expect(typeof assignedName(n)).toBe('string');
      expect(assignedName(n).length).toBeGreaterThan(0);
    }
  });

  it('changes the adjective, not just the noun, on consecutive shuffles', () => {
    // Stepping by 1 walked one row: Swift Lion, Swift Falcon, Swift Archer...
    // twelve times before the adjective moved. A child tapping 'give me a
    // different name' must see a different NAME, not a different noun.
    const first = Array.from({ length: 5 }, (_, i) => assignedName(i));
    expect(new Set(first.map((n) => n.split(' ')[0])).size).toBeGreaterThan(1);
  });

  it('reaches every name before repeating any', () => {
    const seen = new Set(Array.from({ length: ASSIGNED_NAME_COUNT }, (_, i) => assignedName(i)));
    expect(seen.size).toBe(ASSIGNED_NAME_COUNT);
  });
});

describe('the set is what makes the server able to check membership', () => {
  it('recognises its own names, so a chosen one is not silently replaced', () => {
    // The store keeps a name the player picked from the shuffle. When it
    // recomputed instead, the screen showed 'Swift Spear' and the save recorded
    // 'Swift River'.
    for (const n of allAssignedNames()) expect(isAssignedName(n)).toBe(true);
  });

  it('rejects anything else, including things a shape check would pass', () => {
    // This is the whole reason the set is closed. Every string below is letters
    // and spaces — a sanitiser that strips disallowed characters and truncates
    // would have waved all of them through.
    for (const n of ['Alireza', 'Swift', '', 'swift lion', 'Swift  Lion', 'Hate Speech']) {
      expect(isAssignedName(n)).toBe(false);
    }
  });

  it('survives the wire rules the server also applies', () => {
    // A name the transport rejects would lock a player out of online play —
    // the restriction must not become a ban. 'Far-seeing' and 'Patient' were in
    // the first adjective list and pushed names past the 14-character limit.
    const bad = allAssignedNames().filter((n) => !isValidName(n) || sanitizeName(n) !== n);
    expect(bad).toEqual([]);
  });

  it('contains nothing that reads as a real person', () => {
    // Assigned names must not overlap the AI opponent roster, which is real
    // historical people naming the computer. A human wearing one would blur the
    // single distinction the game works hardest to keep.
    const aiNames = [
      'Aryabard', 'Vishtaspa', 'Gobryas', 'Otanes', 'Datis', 'Mardonius',
      'Artabazos', 'Hydarnes', 'Bagabigna', 'Spitamenes', 'Tiribazos', 'Pharnabaz',
      'Roxane', 'Atossa', 'Parysatis', 'Artystone', 'Amestris', 'Irdabama',
      'Zopyros', 'Megabyzos', 'Ariaramnes', 'Kambujiya', 'Bardiya', 'Vahyazdata',
    ];
    expect(allAssignedNames().filter((n) => aiNames.some((ai) => n.includes(ai)))).toEqual([]);
  });
});
