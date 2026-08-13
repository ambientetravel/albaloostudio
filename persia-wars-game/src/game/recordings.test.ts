import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RECORDING_VERSION, type MatchRecording } from '../sim/recording';
import {
  clearRecordings,
  loadRecordings,
  recordingsBytes,
  saveRecording,
  MAX_KEPT,
} from './recordings';

/**
 * Recording storage.
 *
 * These run in Node, where there is no localStorage, so the tests install one.
 * That is not a workaround — the absence is itself a case worth covering, and
 * the last block below removes the stub again to prove the module no-ops
 * instead of throwing when storage is missing (a hardened browser profile, or
 * this very test environment).
 */

class FakeStorage implements Storage {
  private map = new Map<string, string>();
  /** Set to make setItem throw, the way a full quota does. */
  full = false;

  get length(): number {
    return this.map.size;
  }
  clear(): void {
    this.map.clear();
  }
  getItem(k: string): string | null {
    return this.map.get(k) ?? null;
  }
  key(i: number): string | null {
    return [...this.map.keys()][i] ?? null;
  }
  removeItem(k: string): void {
    this.map.delete(k);
  }
  setItem(k: string, v: string): void {
    if (this.full) throw new Error('QuotaExceededError');
    this.map.set(k, v);
  }
}

const tape = (seed: number, rounds = 3): MatchRecording => ({
  v: RECORDING_VERSION,
  battleId: 'pasargadae-550',
  seed,
  arena: 13,
  decks: { a: ['persian-archer'], b: ['median-spearman'] },
  commanders: { a: 'cyrus', b: 'astyages' },
  winsNeeded: 4,
  missionId: null,
  human: 'a',
  rounds: Array.from({ length: rounds }, () => ({
    rerolls: { a: 0, b: 0 },
    picks: { a: 'persian-archer', b: 'median-spearman' },
  })),
});

let fake: FakeStorage;

beforeEach(() => {
  fake = new FakeStorage();
  vi.stubGlobal('localStorage', fake);
  clearRecordings();
});

describe('keeping recordings', () => {
  it('stores and reads one back', () => {
    saveRecording(tape(1));
    expect(loadRecordings()).toHaveLength(1);
    expect(loadRecordings()[0].seed).toBe(1);
  });

  it('puts the newest first', () => {
    saveRecording(tape(1));
    saveRecording(tape(2));
    saveRecording(tape(3));
    expect(loadRecordings().map((r) => r.seed)).toEqual([3, 2, 1]);
  });

  it(`keeps at most ${MAX_KEPT} and drops the oldest`, () => {
    for (let i = 1; i <= MAX_KEPT + 6; i += 1) saveRecording(tape(i));
    const kept = loadRecordings();
    expect(kept).toHaveLength(MAX_KEPT);
    expect(kept[0].seed).toBe(MAX_KEPT + 6);
    // The six oldest are gone rather than silently accumulating.
    expect(kept.some((r) => r.seed === 1)).toBe(false);
  });

  it('refuses a match that never played a round', () => {
    // Leaving before the first commit would otherwise fill the store with empty
    // tapes a recorded rival can never play from.
    saveRecording(tape(9, 0));
    expect(loadRecordings()).toEqual([]);
  });

  it('drops tapes from another version rather than half-reading them', () => {
    localStorage.setItem(
      'persia-at-war/recordings/v1',
      JSON.stringify([{ ...tape(1), v: RECORDING_VERSION + 1 }, tape(2)]),
    );
    expect(loadRecordings().map((r) => r.seed)).toEqual([2]);
  });
});

describe('storage that fails', () => {
  it('survives a full quota without losing what was already kept', () => {
    saveRecording(tape(1));
    fake.full = true;
    const after = saveRecording(tape(2));
    // The new one is lost — recordings are the one thing here safe to lose —
    // but the existing tape and, crucially, the rest of the save are intact.
    expect(after.map((r) => r.seed)).toEqual([1]);
  });

  it('survives corrupt JSON', () => {
    localStorage.setItem('persia-at-war/recordings/v1', '{not json');
    expect(loadRecordings()).toEqual([]);
  });

  it('survives a stored value that is not an array', () => {
    localStorage.setItem('persia-at-war/recordings/v1', '{"v":1}');
    expect(loadRecordings()).toEqual([]);
  });

  it('reports the bytes held', () => {
    saveRecording(tape(1));
    saveRecording(tape(2));
    expect(recordingsBytes()).toBeGreaterThan(0);
  });
});

describe('no storage at all', () => {
  it('no-ops instead of throwing', () => {
    // A hardened browser profile, or any non-browser runtime. The game must
    // still play; it just does not remember matches.
    vi.stubGlobal('localStorage', undefined);
    expect(() => saveRecording(tape(1))).not.toThrow();
    expect(loadRecordings()).toEqual([]);
    expect(recordingsBytes()).toBe(0);
    expect(() => clearRecordings()).not.toThrow();
  });
});
