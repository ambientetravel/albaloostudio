import { describe, expect, it } from 'vitest';
import { content, isPlayable } from '../content';
import {
  MAX_CARD_LEVEL,
  applyTrophyDelta,
  arenaForTrophies,
  arenaProgress,
  canUpgrade,
  cardsToUpgrade,
  coinsToUpgrade,
  nextArenaAt,
  rollCardReward,
} from './progression';

describe('the arena ladder', () => {
  it('starts everyone in arena 1', () => {
    expect(arenaForTrophies(0)).toBe(1);
  });

  it('never skips or reverses as trophies climb', () => {
    let last = 1;
    for (let t = 0; t <= 5000; t += 10) {
      const a = arenaForTrophies(t);
      expect(a).toBeGreaterThanOrEqual(last);
      expect(a - last).toBeLessThanOrEqual(1);
      last = a;
    }
  });

  it('matches each arena to its own threshold exactly', () => {
    for (const arena of content.arenas) {
      expect(arenaForTrophies(arena.trophies)).toBe(arena.id);
    }
  });

  it('reports no next arena at the top of the ladder', () => {
    const top = content.arenas[content.arenas.length - 1];
    expect(nextArenaAt(top.trophies)).toBeNull();
    expect(arenaProgress(top.trophies).frac).toBe(1);
  });

  it('keeps arena progress inside 0 and 1', () => {
    for (let t = 0; t <= 5000; t += 7) {
      const { frac } = arenaProgress(t);
      expect(frac).toBeGreaterThanOrEqual(0);
      expect(frac).toBeLessThanOrEqual(1);
    }
  });
});

describe('trophies', () => {
  it('never drops below zero, so a beginner cannot get stuck', () => {
    let t = 0;
    for (let i = 0; i < 20; i++) t = applyTrophyDelta(t, false);
    expect(t).toBe(0);
  });

  it('goes up on a win and down on a loss', () => {
    expect(applyTrophyDelta(500, true)).toBeGreaterThan(500);
    expect(applyTrophyDelta(500, false)).toBeLessThan(500);
  });
});

describe('card upgrades', () => {
  it('needs both duplicates and coins', () => {
    const level = 1;
    const need = cardsToUpgrade(level);
    const coins = coinsToUpgrade(level);
    expect(canUpgrade({ count: need, level }, coins)).toBe(true);
    expect(canUpgrade({ count: need - 1, level }, coins)).toBe(false);
    expect(canUpgrade({ count: need, level }, coins - 1)).toBe(false);
  });

  it('refuses to upgrade past the maximum level', () => {
    expect(canUpgrade({ count: 9999, level: MAX_CARD_LEVEL }, 9_999_999)).toBe(false);
  });

  it('gets more expensive every level', () => {
    for (let l = 1; l < MAX_CARD_LEVEL - 1; l++) {
      expect(cardsToUpgrade(l + 1)).toBeGreaterThan(cardsToUpgrade(l));
      expect(coinsToUpgrade(l + 1)).toBeGreaterThan(coinsToUpgrade(l));
    }
  });
});

describe('card rewards', () => {
  it('only ever awards cards the player has unlocked', () => {
    for (const arena of content.arenas) {
      const allowed = new Set(content.units.filter((u) => isPlayable(u.confidence) && u.arena <= arena.id).map((u) => u.id));
      const rolled = rollCardReward(arena.id, 12345, 40);
      for (const id of rolled) expect(allowed.has(id)).toBe(true);
    }
  });

  it('never awards a card that is not playable', () => {
    const unplayable = new Set(content.units.filter((u) => !isPlayable(u.confidence)).map((u) => u.id));
    const rolled = rollCardReward(13, 999, 200);
    for (const id of rolled) expect(unplayable.has(id)).toBe(false);
  });

  it('is deterministic for a given seed', () => {
    expect(rollCardReward(5, 4242, 10)).toEqual(rollCardReward(5, 4242, 10));
  });
});
