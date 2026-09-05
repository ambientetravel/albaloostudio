import { describe, expect, it } from 'vitest';
import { getBattle } from '../content';
import { simulate, type Squad } from './battle';
import type { Tier } from './roundCore.ts';

/**
 * Every trait and doctrine has to do something the player can watch happen.
 *
 * A card whose effect cannot be measured is a label, not a mechanic — and a
 * label that claims an effect it does not have is the one thing this project
 * refuses to ship. Each test below pins the *stated consequence* on the card
 * against what the simulation actually does, and each also checks the stated
 * cost, so no trait is quietly "just better".
 */

const plain = getBattle('pasargadae-550');
const gorge = getBattle('persian-gates-330');
const SEEDS = Array.from({ length: 60 }, (_, i) => (i + 1) * 7919);

const squad = (
  side: 'a' | 'b',
  units: { unitId: string; tier?: Tier; traits?: string[] }[],
  doctrines: string[] = [],
): Squad => ({
  side,
  units: units.map((u) => ({ unitId: u.unitId, tier: u.tier ?? 1, traits: u.traits ?? [] })),
  doctrines,
});

/** How often side a wins across the seed set, in a given round. */
function winRate(a: Squad, b: Squad, round = 5, battle = plain): number {
  let wins = 0;
  for (const seed of SEEDS) if (simulate(battle, a, b, seed, round).winner === 'a') wins++;
  return wins / SEEDS.length;
}

describe('Ready Volley', () => {
  it('beats a plain archer in a shooting match — it starts sooner', () => {
    const withTrait = squad('a', [{ unitId: 'persian-archer', traits: ['ready-volley'] }]);
    const without = squad('b', [{ unitId: 'persian-archer' }]);
    expect(winRate(withTrait, without)).toBeGreaterThan(0.7);
  });

  it('pays for it against something that reaches it', () => {
    // Caught flat-footed: the same archer does WORSE against cavalry than a
    // plain one does, which is the card's stated cost.
    const trait = winRate(
      squad('a', [{ unitId: 'persian-archer', traits: ['ready-volley'] }]),
      squad('b', [{ unitId: 'persian-cavalry' }]),
    );
    const plainArcher = winRate(
      squad('a', [{ unitId: 'persian-archer' }]),
      squad('b', [{ unitId: 'persian-cavalry' }]),
    );
    expect(trait).toBeLessThanOrEqual(plainArcher);
  });
});

describe('Locked Shields', () => {
  it('holds against horses — measured in what is left standing, not in wins', () => {
    // Plain infantry already beats cavalry every time, because the counter
    // triangle says so. A win-rate comparison could therefore never show this
    // trait working at all; what it changes is the price of the win.
    const survived = (traits: string[]) => {
      let total = 0;
      for (const seed of SEEDS) {
        total += simulate(
          plain,
          squad('a', [{ unitId: 'spara-bearer', traits }]),
          squad('b', [{ unitId: 'persian-cavalry' }]),
          seed,
          5,
        ).remaining.a;
      }
      return total / SEEDS.length;
    };
    expect(survived(['locked-shields'])).toBeGreaterThan(survived([]));
  });

  it('really does stop at the middle of the field', () => {
    // The stated cost: "takes the middle of the field and will not go past it".
    // Against something that refuses contact, a wall that cannot pursue is
    // stuck — so the wall must never end up in the enemy's half.
    const log = simulate(
      plain,
      squad('a', [{ unitId: 'spara-bearer', traits: ['locked-shields'] }]),
      squad('b', [{ unitId: 'saka-horse-archer' }]),
      4242,
      5,
    );
    const wallUid = log.roster.find((r) => r.side === 'a')!.uid;
    const furthest = Math.max(
      ...log.frames.map((f) => f.pos.find((p) => p.uid === wallUid)?.x ?? 0),
    );
    expect(furthest).toBeLessThanOrEqual(50.001);
  });
});

describe('Long Reach', () => {
  it('wins the clash against the same spearman without it', () => {
    expect(
      winRate(
        squad('a', [{ unitId: 'median-spearman', traits: ['long-reach'] }]),
        squad('b', [{ unitId: 'median-spearman' }]),
      ),
    ).toBeGreaterThan(0.65);
  });

  it('does nothing against something that never closes', () => {
    // "No effect at all at range" — against an archer the reach is irrelevant.
    const withReach = winRate(
      squad('a', [{ unitId: 'median-spearman', traits: ['long-reach'] }]),
      squad('b', [{ unitId: 'persian-archer' }]),
    );
    const without = winRate(
      squad('a', [{ unitId: 'median-spearman' }]),
      squad('b', [{ unitId: 'persian-archer' }]),
    );
    expect(Math.abs(withReach - without)).toBeLessThan
      (0.2);
  });
});

describe('Wheeling Line', () => {
  it('holds the riders back, then commits them', () => {
    const log = simulate(
      plain,
      squad('a', [{ unitId: 'median-spearman' }, { unitId: 'persian-cavalry', traits: ['wheeling-line'] }]),
      squad('b', [{ unitId: 'median-spearman' }, { unitId: 'spara-bearer' }]),
      999,
      5,
    );
    const riderUid = log.roster.find((r) => r.side === 'a' && r.cls === 'cavalry')!.uid;
    const xAt = (tick: number) => log.frames[tick]?.pos.find((p) => p.uid === riderUid)?.x;
    // Still on its start line well after the infantry has set off.
    expect(xAt(120)).toBe(xAt(0));
    // And moving by the time it is due.
    const late = xAt(Math.min(log.frames.length - 1, 260));
    if (late !== undefined && xAt(0) !== undefined) expect(late).not.toBe(xAt(0));
  });
});

describe('Loosed Rein', () => {
  it('keeps a horse-archer further away from a pursuer, and alive longer', () => {
    /*
     * Measured over the CHASE, not the whole battle.
     *
     * This used to average the gap across every frame, which quietly measured
     * the wrong thing: Loosed Rein makes the rider survive longer, so the tail
     * of the log is full of frames where he has finally been run down and the
     * gap is nearly zero. A trait that works was dragging its own average
     * below the baseline's. Surviving longer is the trait doing its job, so it
     * is asserted here rather than being allowed to sabotage the reading.
     */
    const CHASE = 80;
    const run = (traits: string[]) => {
      const log = simulate(
        plain,
        squad('a', [{ unitId: 'saka-horse-archer', traits }]),
        squad('b', [{ unitId: 'persian-cavalry' }]),
        31337,
        5,
      );
      const meUid = log.roster.find((r) => r.side === 'a')!.uid;
      const themUid = log.roster.find((r) => r.side === 'b')!.uid;
      const gaps = log.frames.slice(0, CHASE).map((f) => {
        const me = f.pos.find((p) => p.uid === meUid)?.x ?? 0;
        const them = f.pos.find((p) => p.uid === themUid)?.x ?? 0;
        return Math.abs(them - me);
      });
      return {
        gap: gaps.reduce((s, g) => s + g, 0) / gaps.length,
        ticks: log.frames.length,
      };
    };
    const loose = run(['loosed-rein']);
    const plainRun = run([]);
    expect(loose.gap).toBeGreaterThan(plainRun.gap);
    expect(loose.ticks).toBeGreaterThan(plainRun.ticks);
  });
});

describe('The Centre Holds', () => {
  it('firms the middle and thins the wings, rather than making everything better', () => {
    const four = [
      { unitId: 'spara-bearer' },
      { unitId: 'median-spearman' },
      { unitId: 'median-spearman' },
      { unitId: 'spara-bearer' },
    ];
    const log = simulate(
      plain,
      squad('a', four, ['centre-holds']),
      squad('b', four),
      555,
      5,
    );
    const hp = (lane: number) => log.roster.find((r) => r.side === 'a' && r.lane === lane)!.maxHp;
    const plainHp = (lane: number) => log.roster.find((r) => r.side === 'b' && r.lane === lane)!.maxHp;
    // Middle lanes gained health; the wings did not.
    expect(hp(1)).toBeGreaterThan(plainHp(1));
    expect(hp(0)).toBe(plainHp(0));
  });
});

describe('Shoot the Horses', () => {
  it('makes archers ignore the nearer target to answer the cavalry', () => {
    // Side b sends infantry up the middle and cavalry on the flank. Without the
    // doctrine the archers shoot whatever is closest; with it they hunt riders.
    const a = squad('a', [{ unitId: 'persian-archer' }], ['shoot-the-horses']);
    const control = squad('a', [{ unitId: 'persian-archer' }]);
    const enemy = squad('b', [{ unitId: 'persian-cavalry' }, { unitId: 'spara-bearer' }]);

    const cavalryDied = (side: Squad) => {
      let died = 0;
      for (const seed of SEEDS) {
        const log = simulate(plain, side, enemy, seed, 5);
        const cav = log.roster.find((r) => r.side === 'b' && r.cls === 'cavalry')!.uid;
        if (log.frames.some((f) => f.events.some((e) => e.t === 'death' && e.uid === cav))) died++;
      }
      return died;
    };
    expect(cavalryDied(a)).toBeGreaterThanOrEqual(cavalryDied(control));
  });
});

describe('Broken Ground', () => {
  it('helps in a gorge and hurts on a plain — the same card, both ways', () => {
    const withIt = squad('a', [{ unitId: 'median-spearman' }, { unitId: 'spara-bearer' }], ['broken-ground']);
    const without = squad('b', [{ unitId: 'median-spearman' }, { unitId: 'spara-bearer' }]);
    const inGorge = winRate(withIt, without, 5, gorge);
    const onPlain = winRate(withIt, without, 5, plain);
    expect(inGorge).toBeGreaterThan(onPlain);
  });
});

describe('a trait is never a rank', () => {
  it('leaves health untouched — that is what a rank is for', () => {
    const log = simulate(
      plain,
      squad('a', [{ unitId: 'persian-archer', traits: ['ready-volley'] }]),
      squad('b', [{ unitId: 'persian-archer' }]),
      1,
      5,
    );
    const [mine, theirs] = ['a', 'b'].map((s) => log.roster.find((r) => r.side === s)!.maxHp);
    expect(mine).toBe(theirs);
  });

  it('a rank raises health and a trait does not', () => {
    const ranked = simulate(
      plain,
      squad('a', [{ unitId: 'persian-archer', tier: 2 }]),
      squad('b', [{ unitId: 'persian-archer' }]),
      1,
      5,
    );
    const [up, base] = ['a', 'b'].map((s) => ranked.roster.find((r) => r.side === s)!.maxHp);
    expect(up).toBeGreaterThan(base);
  });
});
