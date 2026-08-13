import { RECORDING_VERSION, recordingBytes, type MatchRecording } from '../sim/recording';

/**
 * Where finished match recordings are kept.
 *
 * Its own localStorage key rather than the save file, for two reasons. The save
 * is written on nearly every action and a corrupt or oversized tape must never
 * be able to take a child's collection down with it; and recordings are the one
 * thing here that is safe to drop, so they get a bucket that can be cleared
 * without touching progress.
 *
 * Newest first, hard-capped. A recording measured at 905 bytes for a full match,
 * so the cap below is a few tens of kilobytes rather than a real constraint —
 * it exists because localStorage has a quota and an unbounded list of anything
 * eventually finds it.
 */

const KEY = 'persia-at-war/recordings/v1';
/** Enough to seed recorded rivals from a session's play, not a career archive. */
const MAX_KEPT = 24;

function storage(): Storage | null {
  try {
    // Absent in the Node test environment and in a hardened browser profile.
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

export function loadRecordings(): MatchRecording[] {
  const store = storage();
  if (!store) return [];
  try {
    const raw = store.getItem(KEY);
    if (!raw) return [];
    const all = JSON.parse(raw) as MatchRecording[];
    if (!Array.isArray(all)) return [];
    // A tape from an older build cannot be replayed by this one, and a replay
    // that half-works is worse than none — drop rather than migrate.
    return all.filter((r) => r && r.v === RECORDING_VERSION);
  } catch {
    return [];
  }
}

/**
 * Keeps a finished recording. Returns the list as stored.
 *
 * A match with no rounds is not a match — leaving early would otherwise fill the
 * store with empty tapes that a recorded rival can never play from.
 */
export function saveRecording(rec: MatchRecording): MatchRecording[] {
  const store = storage();
  if (!store || rec.rounds.length === 0) return loadRecordings();
  const next = [rec, ...loadRecordings()].slice(0, MAX_KEPT);
  try {
    store.setItem(KEY, JSON.stringify(next));
  } catch {
    // Quota, private mode, or a full disk. Recordings are the one thing here
    // that is safe to lose, so this is silent by design rather than by neglect.
    return loadRecordings();
  }
  return next;
}

export function clearRecordings(): void {
  storage()?.removeItem(KEY);
}

/** Total bytes on disk — surfaced in the dev overlay so growth is visible. */
export function recordingsBytes(): number {
  return loadRecordings().reduce((n, r) => n + recordingBytes(r), 0);
}

export { MAX_KEPT };
