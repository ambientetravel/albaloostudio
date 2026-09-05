import { describe, expect, it } from 'vitest';
import { HORSE_RIG, MOUNTED_PARTS, FOOT_PARTS, gallop, idle, march, partsOf } from './rig';

/**
 * The gallop.
 *
 * Motion is the one thing a screenshot cannot check, so the claims the clip
 * makes about itself are checked here instead. The important one is not
 * "it moves" — it is Muybridge's: a galloping horse is airborne when its legs
 * are GATHERED UNDER it, not when they are stretched out. Every painting before
 * 1878 had that backwards and so does every animation that throws the legs wide
 * at the top of the bounce, so it is worth a test that fails if someone
 * "improves" the timing back to the pretty, wrong version.
 */

const SAMPLES = 200;
const at = (i: number) => gallop(i / SAMPLES);
/** Rotation of a part the clip is known to drive. */
const r = (p: { rot: Partial<Record<string, number>> }, part: string): number => p.rot[part] ?? 0;

describe('the gallop is a cycle', () => {
  it('closes — the end of a stride is the start of the next', () => {
    const a = gallop(0);
    const b = gallop(0.9999);
    for (const part of MOUNTED_PARTS) {
      expect(Math.abs(r(a, part) - r(b, part))).toBeLessThan(0.02);
    }
    expect(Math.abs(a.lift - b.lift)).toBeLessThan(0.2);
  });

  it('never jumps between adjacent frames', () => {
    // A discontinuity reads as a limb teleporting, which is worse than no
    // animation at all.
    for (let i = 1; i < SAMPLES; i += 1) {
      for (const part of MOUNTED_PARTS) {
        expect(Math.abs(r(at(i), part) - r(at(i - 1), part))).toBeLessThan(0.05);
      }
    }
  });

  it('keeps every joint inside a plausible range', () => {
    for (let i = 0; i < SAMPLES; i += 1) {
      const p = at(i);
      // A leg that swings past 45 degrees is a cartwheel, not a stride.
      expect(Math.abs(r(p, 'legs-front'))).toBeLessThan(0.8);
      expect(Math.abs(r(p, 'legs-hind'))).toBeLessThan(0.8);
      // The barrel pitches; it does not rear.
      expect(Math.abs(r(p, 'body'))).toBeLessThan(0.2);
      expect(p.lift).toBeLessThanOrEqual(0);
    }
  });
});

describe('Muybridge, 1878', () => {
  it('is airborne when the legs are gathered, not when they are extended', () => {
    // Fore and hind cross twice a stride — folded under in suspension, planted
    // under in stance — so "smallest spread" alone picks the wrong one half the
    // time. The claim that matters is about the moment of maximum lift: the
    // legs must be closer together then than they are on average.
    const spread = (i: number) => Math.abs(r(at(i), 'legs-front') - r(at(i), 'legs-hind'));
    let peak = 0;
    for (let i = 1; i < SAMPLES; i += 1) if (at(i).lift < at(peak).lift) peak = i;

    let total = 0;
    for (let i = 0; i < SAMPLES; i += 1) total += spread(i);
    const mean = total / SAMPLES;

    expect(at(peak).lift).toBeLessThan(0);
    expect(spread(peak)).toBeLessThan(mean * 0.5);
  });

  it('works the fore and hind legs out of phase', () => {
    // In step, the horse hops. Out of step, it runs.
    let sameSign = 0;
    for (let i = 0; i < SAMPLES; i += 1) {
      const p = at(i);
      if (Math.sign(r(p, 'legs-front')) === Math.sign(r(p, 'legs-hind'))) sameSign += 1;
    }
    expect(sameSign / SAMPLES).toBeLessThan(0.62);
  });

  it('leaves the ground exactly once a stride', () => {
    let liftoffs = 0;
    for (let i = 1; i < SAMPLES; i += 1) {
      if (at(i - 1).lift === 0 && at(i).lift < 0) liftoffs += 1;
    }
    expect(liftoffs).toBe(1);
  });
});

describe('standing still', () => {
  it('breathes rather than freezing', () => {
    const moved = [0, 0.3, 0.6, 0.9].map((t) => idle(t).rot.body ?? 0);
    expect(new Set(moved).size).toBeGreaterThan(1);
  });

  it('keeps the legs planted', () => {
    for (let i = 0; i < 20; i += 1) {
      const p = idle(i / 20);
      expect(r(p, 'legs-front')).toBe(0);
      expect(r(p, 'legs-hind')).toBe(0);
      expect(r(p, 'leg-lead')).toBe(0);
      expect(r(p, 'leg-rear')).toBe(0);
      expect(p.lift).toBe(0);
    }
  });
});

describe('the rig definition', () => {
  it('has a joint for every part, inside the texture', () => {
    const [w, h] = HORSE_RIG.size;
    expect(partsOf(HORSE_RIG)).toEqual(MOUNTED_PARTS);
    for (const part of MOUNTED_PARTS) {
      const j = HORSE_RIG.joints[part]!;
      expect(j).toBeDefined();
      expect(j.pivot[0]).toBeGreaterThanOrEqual(0);
      expect(j.pivot[0]).toBeLessThanOrEqual(w);
      expect(j.pivot[1]).toBeGreaterThanOrEqual(0);
      expect(j.pivot[1]).toBeLessThanOrEqual(h);
    }
  });

  it('draws the forelegs in front of the body and the tail behind it', () => {
    // Get this wrong and the horse wears its own legs.
    expect(HORSE_RIG.joints['legs-front']!.z).toBeGreaterThan(HORSE_RIG.joints.body!.z);
    expect(HORSE_RIG.joints.tail!.z).toBeLessThan(HORSE_RIG.joints.body!.z);
  });
});

describe('the march', () => {
  const m = (i: number) => march(i / SAMPLES);

  it('alternates the legs — that is the whole of a walk', () => {
    // Same sign on both legs is a hop, not a step.
    for (let i = 0; i < SAMPLES; i += 1) {
      const lead = r(m(i), 'leg-lead');
      const rear = r(m(i), 'leg-rear');
      if (Math.abs(lead) > 0.05) expect(Math.sign(lead)).toBe(-Math.sign(rear));
    }
  });

  it('rises when the legs pass and sinks when they are spread', () => {
    // Twice a stride, which is why a walking figure bobs at double the leg rate.
    let liftAtPass = 0;
    let liftAtSpread = 0;
    let smallest = Infinity;
    let widest = 0;
    for (let i = 0; i < SAMPLES; i += 1) {
      const gap = Math.abs(r(m(i), 'leg-lead') - r(m(i), 'leg-rear'));
      if (gap < smallest) [smallest, liftAtPass] = [gap, m(i).lift];
      if (gap > widest) [widest, liftAtSpread] = [gap, m(i).lift];
    }
    expect(liftAtPass).toBeLessThan(liftAtSpread);
  });

  it('marches rather than parades', () => {
    // Soldiers under shields advance; they do not bound. A leg past 25 degrees
    // is a drill display.
    for (let i = 0; i < SAMPLES; i += 1) {
      expect(Math.abs(r(m(i), 'leg-lead'))).toBeLessThan(0.45);
      expect(Math.abs(m(i).lift)).toBeLessThan(4);
    }
  });

  it('closes as a cycle', () => {
    for (const part of FOOT_PARTS) {
      expect(Math.abs(r(march(0), part) - r(march(0.9999), part))).toBeLessThan(0.02);
    }
  });
});
