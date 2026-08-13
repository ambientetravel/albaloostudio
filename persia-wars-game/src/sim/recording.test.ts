import { describe, expect, it } from 'vitest';
import { draftPool, getBattle, getCommander } from '../content';
import { aiRoundPick, type AiOpponent, type RivalStyle } from './ai';
import { simulate, type Squad } from './battle';
import {
  beginRecording,
  recordRound,
  recordedRivalPick,
  recordingBytes,
  replay,
  RECORDING_VERSION,
  type MatchRecording,
} from './recording';
import { choose, commitPicks, improviseDeck, nextRound, scoreRound, startMatch } from './match';
import { roundSeedFor, type Side } from './roundCore.ts';

/**
 * The recorder.
 *
 * The claim under test is strong and worth stating plainly: a match is its
 * inputs, so a few hundred bytes of decisions replayed through the same pure
 * simulation reproduce it EXACTLY — not approximately. Every assertion below is
 * an equality rather than a similarity, because anything weaker would let a
 * replay drift and still pass.
 */

const battle = getBattle('pasargadae-550');
const ARENA = 13;
const SEEDS = Array.from({ length: 40 }, (_, i) => (i + 1) * 3571);

const rival = (style: RivalStyle): AiOpponent => ({ name: style, avatar: 0, skill: 0.9, style });

/** Plays a match, recording it as it goes. Returns the final state and the tape. */
function playAndRecord(seed: number, styles: Record<Side, RivalStyle>) {
  const pool = draftPool(battle, ARENA).map((u) => u.id);
  let m = startMatch(battle, seed, ARENA, {
    a: improviseDeck(pool, seed, 4),
    b: improviseDeck(pool, seed ^ 0x51ed, 4),
  });
  let rec = beginRecording(m, 'a');
  const opponents = { a: rival(styles.a), b: rival(styles.b) };

  let guard = 0;
  while (m.phase !== 'over' && guard++ < 20) {
    m = choose(m, 'a', aiRoundPick(m, 'a', opponents.a));
    m = choose(m, 'b', aiRoundPick(m, 'b', opponents.b));
    // Before commitPicks — the only moment picks and rerolls are both present.
    rec = recordRound(rec, m);
    m = commitPicks(m);
    const sq = (side: Side): Squad => {
      const c = getCommander(m.commanders[side]);
      return {
        side,
        units: m.ledgers[side].squads,
        doctrines: m.ledgers[side].doctrines,
        passive: c.passive.id,
        order: c.order.id,
      };
    };
    const log = simulate(battle, sq('a'), sq('b'), roundSeedFor(m.seed, m.round), m.round);
    m = scoreRound(m, log.winner, log.remaining);
    if (m.phase !== 'over') m = nextRound(m);
  }
  return { state: m, rec };
}

describe('a recording reproduces its match exactly', () => {
  it('replays to an identical final state across 40 matches', () => {
    const diverged: string[] = [];
    for (const seed of SEEDS) {
      const { state, rec } = playAndRecord(seed, { a: 'massing', b: 'planning' });
      const back = replay(rec);
      if (JSON.stringify(back) !== JSON.stringify(state)) diverged.push(String(seed));
    }
    expect(diverged).toEqual([]);
  });

  it('reproduces the score, the ledgers and every round outcome', () => {
    const { state, rec } = playAndRecord(90210, { a: 'drilling', b: 'massing' });
    const back = replay(rec);
    expect(back.score).toEqual(state.score);
    expect(back.ledgers).toEqual(state.ledgers);
    expect(back.history).toEqual(state.history);
    expect(back.phase).toBe(state.phase);
    expect(back.round).toBe(state.round);
  });

  it('records exactly one entry per round played', () => {
    const { state, rec } = playAndRecord(4242, { a: 'planning', b: 'drilling' });
    expect(rec.rounds).toHaveLength(state.history.length);
  });

  it('refuses to record the same round twice', () => {
    // The UI can re-render, and a resumed round is not a new decision. A double
    // entry would shift every later round by one and silently corrupt the tape.
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    let m = startMatch(battle, 55, ARENA, { a: pool.slice(0, 4), b: pool.slice(0, 4) });
    m = choose(m, 'a', m.offers.a[0].id);
    m = choose(m, 'b', m.offers.b[0].id);
    let rec = beginRecording(m, 'a');
    rec = recordRound(rec, m);
    rec = recordRound(rec, m);
    expect(rec.rounds).toHaveLength(1);
  });

  it('records nothing from a round where a side has not chosen', () => {
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    let m = startMatch(battle, 56, ARENA, { a: pool.slice(0, 4), b: pool.slice(0, 4) });
    m = choose(m, 'a', m.offers.a[0].id);
    const rec = recordRound(beginRecording(m, 'a'), m);
    expect(rec.rounds).toEqual([]);
  });
});

describe('a recording is small enough to keep', () => {
  it('stays under 1 kB for a full-length match', () => {
    // The whole design rests on storing decisions rather than events. If this
    // ever fails, something that is not a decision has been added to the tape.
    let worst = 0;
    for (const seed of SEEDS) {
      const { rec } = playAndRecord(seed, { a: 'massing', b: 'planning' });
      worst = Math.max(worst, recordingBytes(rec));
    }
    console.log(`largest recording over ${SEEDS.length} matches: ${worst} bytes`);
    expect(worst).toBeLessThan(1024);
  });
});

describe('a replay refuses rather than improvises', () => {
  it('throws when a recorded card is not on the offer it faces', () => {
    const { rec } = playAndRecord(777, { a: 'massing', b: 'massing' });
    const tampered: MatchRecording = {
      ...rec,
      rounds: rec.rounds.map((r, i) =>
        i === 0 ? { ...r, picks: { ...r.picks, a: 'war-elephant' } } : r,
      ),
    };
    // A quiet substitution would produce a plausible match that is not the one
    // recorded, which is worse than a crash — the point of a recording is that
    // it IS the match.
    expect(() => replay(tampered)).toThrow(/not on offer/);
  });

  it('throws on a recording from a different version', () => {
    const { rec } = playAndRecord(778, { a: 'massing', b: 'massing' });
    expect(() => replay({ ...rec, v: RECORDING_VERSION + 1 })).toThrow(/version/);
  });
});

describe('a recorded rival is honest about what it is', () => {
  it('plays the recorded card when that card is on offer', () => {
    const { rec } = playAndRecord(31337, { a: 'massing', b: 'planning' });
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    const m = startMatch(battle, rec.seed, rec.arena, rec.decks, rec.commanders);
    void pool;
    const d = recordedRivalPick(rec, 'a', m, () => m.offers.a[0].id);
    expect(d.recorded).toBe(true);
    expect(d.cardId).toBe(rec.rounds[0].picks.a);
  });

  it('reports recorded:false when it had to fall back', () => {
    const { rec } = playAndRecord(31338, { a: 'massing', b: 'planning' });
    // A different seed derives a different offer, so the recorded card is
    // usually absent — this is the normal case, not the exceptional one.
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    const other = startMatch(battle, 999_331, ARENA, {
      a: improviseDeck(pool, 4, 4),
      b: improviseDeck(pool, 5, 4),
    });
    const empty: MatchRecording = { ...rec, rounds: [] };
    const d = recordedRivalPick(empty, 'a', other, () => other.offers.a[0].id);
    expect(d.recorded).toBe(false);
    expect(other.offers.a.some((c) => c.id === d.cardId)).toBe(true);
  });

  it('never returns a card that is not on the offer', () => {
    // Whichever branch it takes, the pick must be legal — otherwise `choose`
    // silently no-ops and the round deadlocks.
    const { rec } = playAndRecord(31339, { a: 'drilling', b: 'massing' });
    const pool = draftPool(battle, ARENA).map((u) => u.id);
    for (const seed of [rec.seed, 12345, 67890]) {
      const m = startMatch(battle, seed, ARENA, {
        a: improviseDeck(pool, seed, 4),
        b: improviseDeck(pool, seed ^ 0x51ed, 4),
      });
      const d = recordedRivalPick(rec, 'a', m, () => m.offers.a[0].id);
      expect(m.offers.a.some((c) => c.id === d.cardId)).toBe(true);
    }
  });
});

describe('the round seed has one definition', () => {
  it('matches the expression the tests and the store used to inline', () => {
    for (const [seed, round] of [
      [90210, 1],
      [3571, 7],
      [0, 3],
    ] as const) {
      expect(roundSeedFor(seed, round)).toBe((seed ^ ((round * 0x5bf03635) >>> 0)) >>> 0);
    }
  });
});
