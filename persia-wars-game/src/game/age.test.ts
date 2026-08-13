import { describe, expect, it } from 'vitest';
import { isValidName, sanitizeName } from '../net/protocol';
import {
  allAssignedNames,
  assignedName,
  isAssignedName,
  bracketFor,
  isPlausibleYear,
  mayTypeOwnName,
  ASSIGNED_NAME_COUNT,
  CHILD_UNDER,
  EARLIEST_YEAR,
  TEEN_UNDER,
} from './age';

const YEAR = 2026;

describe('the bracket', () => {
  it('puts anyone under 13 in the child bracket', () => {
    expect(bracketFor(YEAR - 9, YEAR)).toBe('child');
    expect(bracketFor(YEAR - 12, YEAR)).toBe('child');
  });

  it('puts 13 to 15 in the teen bracket', () => {
    expect(bracketFor(YEAR - CHILD_UNDER, YEAR)).toBe('teen');
    expect(bracketFor(YEAR - 15, YEAR)).toBe('teen');
  });

  it('puts 16 and over in the adult bracket', () => {
    expect(bracketFor(YEAR - TEEN_UNDER, YEAR)).toBe('adult');
    expect(bracketFor(YEAR - 40, YEAR)).toBe('adult');
  });

  it('treats the boundaries as exact', () => {
    // Off-by-one here decides whether a twelve-year-old broadcasts a typed name.
    expect(bracketFor(YEAR - 12, YEAR)).toBe('child');
    expect(bracketFor(YEAR - 13, YEAR)).toBe('teen');
    expect(bracketFor(YEAR - 15, YEAR)).toBe('teen');
    expect(bracketFor(YEAR - 16, YEAR)).toBe('adult');
  });
});

describe('the year is checked before it is trusted', () => {
  it('rejects a year in the future', () => {
    expect(isPlausibleYear(YEAR + 1, YEAR)).toBe(false);
  });

  it('rejects a mistyped fragment', () => {
    // A child typing their age instead of a year, or half a year.
    expect(isPlausibleYear(9, YEAR)).toBe(false);
    expect(isPlausibleYear(202, YEAR)).toBe(false);
  });

  it('rejects a non-integer', () => {
    expect(isPlausibleYear(Number.NaN, YEAR)).toBe(false);
    expect(isPlausibleYear(2010.5, YEAR)).toBe(false);
  });

  it('accepts the ends of the range', () => {
    expect(isPlausibleYear(EARLIEST_YEAR, YEAR)).toBe(true);
    expect(isPlausibleYear(YEAR, YEAR)).toBe(true);
  });
});

describe('who may broadcast a name they typed', () => {
  it('allows only adults', () => {
    expect(mayTypeOwnName('adult')).toBe(true);
    expect(mayTypeOwnName('teen')).toBe(false);
    expect(mayTypeOwnName('child')).toBe(false);
  });

  it('keeps teens restricted, because the line moves by country', () => {
    // GDPR-K lets a member state set the age anywhere from 13 to 16. The safe
    // reading is the one that does not depend on knowing where the player is.
    expect(mayTypeOwnName('teen')).toBe(false);
  });
});

describe('assigned names', () => {
  it('gives the same name for the same number', () => {
    expect(assignedName(42)).toBe(assignedName(42));
  });

  it('wraps rather than crashing on any integer', () => {
    for (const n of [0, -1, -999, 1e9, ASSIGNED_NAME_COUNT, ASSIGNED_NAME_COUNT * 3 + 5]) {
      expect(typeof assignedName(n)).toBe('string');
      expect(assignedName(n).length).toBeGreaterThan(0);
    }
  });

  it('offers enough of them that a lobby is not all one name', () => {
    expect(ASSIGNED_NAME_COUNT).toBeGreaterThanOrEqual(100);
    expect(new Set(allAssignedNames()).size).toBe(ASSIGNED_NAME_COUNT);
  });

  it('survives the name rules that the server also applies', () => {
    // An assigned name that failed validation would lock a child out of online
    // play entirely — the restriction must not become a ban.
    const bad = allAssignedNames().filter((n) => !isValidName(n) || sanitizeName(n) !== n);
    expect(bad).toEqual([]);
  });

  it('changes the adjective, not just the noun, on consecutive shuffles', () => {
    // Stepping by 1 walked one row: Swift Lion, Swift Falcon, Swift Archer...
    // twelve times before the adjective moved. A child tapping 'give me a
    // different name' must see a different NAME, not a different noun.
    const first = Array.from({ length: 5 }, (_, i) => assignedName(i));
    const adjectives = new Set(first.map((n) => n.split(' ')[0]));
    expect(adjectives.size).toBeGreaterThan(1);
  });

  it('reaches every name before repeating any', () => {
    const seen = new Set(Array.from({ length: ASSIGNED_NAME_COUNT }, (_, i) => assignedName(i)));
    expect(seen.size).toBe(ASSIGNED_NAME_COUNT);
  });

  it('recognises its own names, so a chosen one is not silently replaced', () => {
    // The store keeps a name a restricted player picked from the shuffle. When
    // it recomputed instead, the screen showed 'Swift Spear' and the save
    // recorded 'Swift River'.
    for (const n of allAssignedNames()) expect(isAssignedName(n)).toBe(true);
    expect(isAssignedName('Alireza')).toBe(false);
    expect(isAssignedName('Swift')).toBe(false);
    expect(isAssignedName('')).toBe(false);
  });

  it('contains nothing that looks like a real person', () => {
    // Assigned names must not overlap the AI opponent roster, which is real
    // historical people naming the computer. A human wearing one would blur the
    // single distinction the game works hardest to keep.
    const aiNames = [
      'Aryabard', 'Vishtaspa', 'Gobryas', 'Otanes', 'Datis', 'Mardonius',
      'Artabazos', 'Hydarnes', 'Bagabigna', 'Spitamenes', 'Tiribazos', 'Pharnabaz',
      'Roxane', 'Atossa', 'Parysatis', 'Artystone', 'Amestris', 'Irdabama',
      'Zopyros', 'Megabyzos', 'Ariaramnes', 'Kambujiya', 'Bardiya', 'Vahyazdata',
    ];
    const clash = allAssignedNames().filter((n) => aiNames.some((ai) => n.includes(ai)));
    expect(clash).toEqual([]);
  });
});
