import { describe, expect, it } from 'vitest';
import { draftPool, getBattle, getCommander, getUnit } from '../content';
import { aiRoundPick, makeOpponent, STYLE_LABEL, type AiOpponent, type RivalStyle } from './ai';
import { counterMultiplier, simulate, type Squad } from './battle';
import { choose, commitPicks, improviseDeck, nextRound, scoreRound, startMatch } from './match';
import type { Side } from './roundCore.ts';

/**
 * Rival styles.
 *
 * The offline opponent used to differ only by a `skill` scalar, which is a hit
 * rate rather than a habit: twenty-four differently-named rivals all drafted the
 * same army. These tests exist to prove the three styles are actually distinct
 * IN THE ARMIES THEY BUILD, not merely in the weights table — a bias that never
 * reaches the ledger is decoration.
 *
 * They also check no style dominates the other two, because three personalities
 * where one is simply correct is one personality and two handicaps.
 */

const battle = getBattle('pasargadae-550');
const ARENA = 13;
const SEEDS = Array.from({ length: 90 }, (_, i) => (i + 1) * 6367);

const rival = (style: RivalStyle, skill = 0.95): AiOpponent => ({
  name: style,
  avatar: 0,
  skill,
  style,
});

/** A whole match with a styled rival on each side. Returns both final ledgers. */
function playMatch(seed: number, styles: Record<Side, RivalStyle>) {
  const pool = draftPool(battle, ARENA).map((u) => u.id);
  const opponents: Record<Side, AiOpponent> = { a: rival(styles.a), b: rival(styles.b) };
  let m = startMatch(battle, seed, ARENA, {
    a: improviseDeck(pool, seed, 4),
    b: improviseDeck(pool, seed ^ 0x51ed, 4),
  });
  let guard = 0;
  while (m.phase !== 'over' && guard++ < 20) {
    m = choose(m, 'a', aiRoundPick(m, 'a', opponents.a));
    m = choose(m, 'b', aiRoundPick(m, 'b', opponents.b));
    m = commitPicks(m);
    const rs = (m.seed ^ ((m.round * 0x5bf03635) >>> 0)) >>> 0;
    const toSquad = (side: Side): Squad => {
      const c = getCommander(m.commanders[side]);
      return {
        side,
        units: m.ledgers[side].squads,
        doctrines: m.ledgers[side].doctrines,
        passive: c.passive.id,
        order: c.order.id,
      };
    };
    const log = simulate(battle, toSquad('a'), toSquad('b'), rs, m.round);
    m = scoreRound(m, log.winner, log.remaining);
    if (m.phase !== 'over') m = nextRound(m);
  }
  return m;
}

/** Averages of the shape of the army a style ends up with. */
function shapeOf(style: RivalStyle) {
  let classes = 0;
  let tier = 0;
  let doctrines = 0;
  let answers = 0;
  let squads = 0;
  let traits = 0;
  let n = 0;

  for (const seed of SEEDS) {
    // Always against the same opponent style, so the only variable is the
    // style under test. 'massing' is the flattest of the three, which makes it
    // the fairest yardstick.
    const m = playMatch(seed, { a: style, b: 'massing' });
    const mine = m.ledgers.a;
    const theirs = m.ledgers.b.squads.map((e) => getUnit(e.unitId));
    if (mine.squads.length === 0) continue;

    classes += new Set(mine.squads.map((e) => getUnit(e.unitId).class)).size;
    tier += mine.squads.reduce((t, e) => t + e.tier, 0) / mine.squads.length;
    doctrines += mine.doctrines.length;
    squads += mine.squads.length;
    traits += mine.squads.reduce((t, e) => t + e.traits.length, 0);
    // How much of the army actually counters what the other side fielded.
    answers +=
      mine.squads.reduce(
        (a, e) =>
          a + theirs.reduce((b, t) => b + (counterMultiplier(getUnit(e.unitId), t.class) - 1), 0),
        0,
      ) / mine.squads.length;
    n += 1;
  }
  return {
    squads: squads / n,
    traits: traits / n,
    classes: classes / n,
    tier: tier / n,
    doctrines: doctrines / n,
    answers: answers / n,
    matches: n,
  };
}

describe('rival styles build different armies', () => {
  const massing = shapeOf('massing');
  const drilling = shapeOf('drilling');
  const planning = shapeOf('planning');

  it('reports the measured shape of each army', () => {
    for (const [name, s] of [['massing', massing], ['drilling', drilling], ['planning', planning]] as const) {
      console.log(
        `${name.padEnd(10)} squads=${s.squads.toFixed(2)} classes=${s.classes.toFixed(2)} ` +
        `tier=${s.tier.toFixed(2)} doctrines=${s.doctrines.toFixed(2)} traits=${s.traits.toFixed(2)} ` +
        `answers=${s.answers.toFixed(2)}`,
      );
    }
  });

  it('every style produced a full sample', () => {
    expect(massing.matches).toBe(SEEDS.length);
    expect(drilling.matches).toBe(SEEDS.length);
    expect(planning.matches).toBe(SEEDS.length);
  });

  it('massing carries the deepest squads', () => {
    // Measured at an average rank of 1.36 against planning's 1.16. It spends
    // its picks going up rather than sideways.
    expect(massing.tier).toBeGreaterThan(planning.tier + 0.1);
  });

  it('massing buys almost nothing that is not a unit', () => {
    // 0.17 doctrines and 0.61 traits, against 1.43 and 1.39 of combined
    // non-unit cards for the other two.
    const nonUnit = (s: { doctrines: number; traits: number }) => s.doctrines + s.traits;
    expect(nonUnit(massing)).toBeLessThan(nonUnit(drilling));
    expect(nonUnit(massing)).toBeLessThan(nonUnit(planning));
  });

  it('drilling ends up with roughly twice the traits of anyone else', () => {
    // Measured at 1.09 traits against 0.61 and 0.44. Not a nudge —
    // if this ever falls below 1.5x the Upgrade weight has stopped reaching the
    // ledger and the style is decoration.
    expect(drilling.traits).toBeGreaterThan(massing.traits * 1.5);
    expect(drilling.traits).toBeGreaterThan(planning.traits * 1.5);
  });

  it('planning ends up with several times the doctrines of anyone else', () => {
    // Measured at 0.99 doctrines against 0.17 and 0.30.
    expect(planning.doctrines).toBeGreaterThan(massing.doctrines * 2);
    expect(planning.doctrines).toBeGreaterThan(drilling.doctrines * 2);
  });

  it('planning spreads across more classes than massing', () => {
    expect(planning.classes).toBeGreaterThan(massing.classes);
  });

  it('no two styles produce the same army', () => {
    const shapes = [massing, drilling, planning].map(
      (s) => `${s.squads.toFixed(2)}/${s.traits.toFixed(2)}/${s.doctrines.toFixed(2)}`,
    );
    expect(new Set(shapes).size).toBe(3);
  });
});

describe('no rival style is simply the right answer', () => {
  const STYLES: RivalStyle[] = ['massing', 'drilling', 'planning'];

  /**
   * Each pairing is played BOTH ways round and the results summed.
   *
   * Side a and side b are not interchangeable — they get different improvised
   * decks and the simulation itself is not mirror-symmetric — so measuring a
   * pairing from one side alone measures the style advantage and the side
   * advantage added together. The first version of this test did exactly that
   * and reported the same matchup as 34% and as 66% depending on which name
   * sorted first.
   */
  function headToHead(x: RivalStyle, y: RivalStyle): { rate: number; played: number } {
    let wins = 0;
    let played = 0;
    for (const seed of SEEDS) {
      for (const [a, b] of [
        [x, y],
        [y, x],
      ] as const) {
        const m = playMatch(seed, { a, b });
        if (m.score.a === m.score.b) continue;
        const winner = m.score.a > m.score.b ? a : b;
        if (winner === x) wins += 1;
        played += 1;
      }
    }
    return { rate: wins / played, played };
  }

  it('every pairing stays inside 35-65% once the side advantage is cancelled', () => {
    const report: string[] = [];
    const bad: string[] = [];
    for (const a of STYLES) {
      for (const b of STYLES) {
        if (a >= b) continue;
        const { rate, played } = headToHead(a, b);
        report.push(`${a} vs ${b}: ${(rate * 100).toFixed(1)}% over ${played}`);
        if (rate < 0.35 || rate > 0.65) bad.push(report[report.length - 1]);
      }
    }
    for (const line of report) console.log(line);
    expect(bad).toEqual([]);
  });
});

describe('a rival is never mistaken for a person', () => {
  it('gives every generated opponent one of the three styles', () => {
    const seen = new Set<RivalStyle>();
    for (let seed = 1; seed <= 400; seed += 1) {
      const o = makeOpponent(seed * 7919, 6);
      expect(STYLES_SET.has(o.style)).toBe(true);
      seen.add(o.style);
    }
    // All three must actually be reachable, or a style ships that nobody meets.
    expect(seen.size).toBe(3);
  });

  it('has a readable label for each style, so the habit is learnable', () => {
    for (const style of STYLES_SET) {
      expect(STYLE_LABEL[style].length).toBeGreaterThan(0);
    }
  });

  it('keeps the opponent stable for a seed, so a rematch shows the same rival', () => {
    const a = makeOpponent(12345, 6);
    const b = makeOpponent(12345, 6);
    expect(a).toEqual(b);
  });
});

const STYLES_SET = new Set<RivalStyle>(['massing', 'drilling', 'planning']);
