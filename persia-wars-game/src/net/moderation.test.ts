import { describe, expect, it } from 'vitest';
import { checkName, normalizeForMatch } from '../../server/moderation.ts';
import { sanitizeName } from './protocol';

/**
 * Names are the one piece of free text one player shows another, and the
 * audience is nine to fourteen. These pin the behaviour that matters: the
 * normalisation, not the word list, which is meant to be replaced.
 */
describe('name normalisation', () => {
  it('sees through padding, case and repeats', () => {
    expect(normalizeForMatch('F-U-C-K')).toBe('fuck');
    expect(normalizeForMatch('f u c k')).toBe('fuck');
    expect(normalizeForMatch('fuuuuuck')).toBe('fuck');
    expect(normalizeForMatch('F.U_C-K')).toBe('fuck');
  });

  it('sees through common character substitution', () => {
    expect(normalizeForMatch('M0derat0r')).toBe('moderator');
    expect(normalizeForMatch('4dm1n')).toBe('admin');
    expect(normalizeForMatch('$hit')).toBe('shit');
  });

  it('leaves ordinary names recognisable', () => {
    expect(normalizeForMatch('Darius_92')).toBe('darius');
    expect(normalizeForMatch('Cyrus')).toBe('cyrus');
  });
});

describe('name moderation', () => {
  it('accepts ordinary names', () => {
    for (const n of ['Cyrus', 'Darius_92', 'Roxane', 'Ali Reza', 'Bardiya']) {
      expect(checkName(n).ok, n).toBe(true);
    }
  });

  it('rejects profanity however it is padded', () => {
    for (const n of ['fuck', 'F-U-C-K', 'sh1t', 'Fuuuck']) {
      expect(checkName(n).ok, n).toBe(false);
    }
  });

  it('rejects impersonation of the game or its staff', () => {
    for (const n of ['admin', 'Admin', 'M0derator', 'official', 'SystemBot']) {
      expect(checkName(n).ok, n).toBe(false);
    }
  });

  it('rejects a name with no letters at all', () => {
    expect(checkName('___').ok).toBe(false);
  });

  it('runs after the shape check, on the sanitised name', () => {
    // sanitizeName strips markup first; moderation then sees the real string.
    const cleaned = sanitizeName('<b>admin</b>');
    expect(cleaned).toBe('badminb');
    expect(checkName('admin').ok).toBe(false);
  });
});

describe('the word lists are normalised too', () => {
  // Regression: the normaliser collapses repeats, so a raw list entry with a
  // double letter could never match its own normalised input. That silently
  // disabled several of the worst entries.
  it('catches banned words that contain double letters', () => {
    for (const n of ['nigger', 'n1gg3r', 'faggot', 'bitch']) {
      expect(checkName(n).ok, n).toBe(false);
    }
  });

  it('catches reserved words that contain double letters', () => {
    for (const n of ['official', '0ff1c1al', 'staff']) {
      expect(checkName(n).ok, n).toBe(false);
    }
  });
});
