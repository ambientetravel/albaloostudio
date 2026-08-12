import type { Silhouette } from '../content/types';

/**
 * How each kind of unit moves.
 *
 * A rider gallops, a spearman marches, an archer draws and looses. The
 * simulation does not know or care about any of this — it emits positions and
 * attack events, and everything here is presentation layered on top. That
 * separation is what keeps online play in lockstep: two clients can animate
 * differently and still agree on the result.
 *
 * These profiles are tuned to the placeholder silhouettes. When the commissioned
 * character art lands, the art changes and the profiles stay — a horse still
 * gallops whoever drew it.
 */

export type AttackStyle = 'thrust' | 'swing' | 'shoot' | 'charge' | 'stomp' | 'lash';

export interface MotionProfile {
  /** Bounce along the direction of travel. Gait, essentially. */
  bobAmp: number;
  bobHz: number;
  /** Side-to-side roll. */
  swayAmp: number;
  swayHz: number;
  /** Body lean, in radians. */
  tiltAmp: number;
  tiltHz: number;
  /** Feet leave the ground — a gallop, not a march. */
  airborne: boolean;
  attack: AttackStyle;
  /** Ranged units throw something visible. */
  projectile?: { kind: 'arrow' | 'stone'; speed: number };
}

const MARCH: MotionProfile = {
  bobAmp: 1.6, bobHz: 3.4, swayAmp: 0.5, swayHz: 1.7, tiltAmp: 0.03, tiltHz: 3.4,
  airborne: false, attack: 'thrust',
};

const PROFILES: Record<Silhouette, MotionProfile> = {
  // Foot. A steady tramp, and a straight thrust of the spear.
  spear: MARCH,

  // The shield wall moves slower and heavier, and shoves rather than stabs.
  shield: {
    bobAmp: 1.1, bobHz: 2.4, swayAmp: 0.9, swayHz: 1.2, tiltAmp: 0.02, tiltHz: 2.4,
    airborne: false, attack: 'thrust',
  },

  // Archers barely move: they are here to stand still and shoot.
  bow: {
    bobAmp: 0.7, bobHz: 2.2, swayAmp: 0.3, swayHz: 1.1, tiltAmp: 0.015, tiltHz: 2.2,
    airborne: false, attack: 'shoot',
    projectile: { kind: 'arrow', speed: 210 },
  },

  // A gallop: big vertical throw, real airtime, body leaning into the run.
  horse: {
    bobAmp: 4.2, bobHz: 5.2, swayAmp: 1.1, swayHz: 2.6, tiltAmp: 0.12, tiltHz: 5.2,
    airborne: true, attack: 'charge',
  },

  // Same gait, but the rider is turned in the saddle shooting.
  'horse-bow': {
    bobAmp: 3.8, bobHz: 5.0, swayAmp: 1.3, swayHz: 2.5, tiltAmp: 0.1, tiltHz: 5.0,
    airborne: true, attack: 'shoot',
    projectile: { kind: 'arrow', speed: 200 },
  },

  // Camels lope — slower cadence, much more roll than a horse.
  camel: {
    bobAmp: 3.0, bobHz: 3.0, swayAmp: 2.6, swayHz: 1.5, tiltAmp: 0.09, tiltHz: 3.0,
    airborne: false, attack: 'shoot',
    projectile: { kind: 'arrow', speed: 185 },
  },

  // Wheels do not bounce. It rolls flat and fast, and hits by running through.
  chariot: {
    bobAmp: 0.9, bobHz: 7.5, swayAmp: 0.6, swayHz: 3.4, tiltAmp: 0.05, tiltHz: 7.5,
    airborne: false, attack: 'charge',
  },

  // Enormous and slow: a long sway and a stamp.
  elephant: {
    bobAmp: 2.0, bobHz: 1.5, swayAmp: 3.0, swayHz: 0.75, tiltAmp: 0.05, tiltHz: 1.5,
    airborne: false, attack: 'stomp',
  },

  // Club-armed foot: marches, then swings overhead.
  club: { ...MARCH, attack: 'swing' },

  // Rides like cavalry, but the kill is a thrown noose.
  lasso: {
    bobAmp: 3.6, bobHz: 4.8, swayAmp: 1.4, swayHz: 2.4, tiltAmp: 0.11, tiltHz: 4.8,
    airborne: true, attack: 'lash',
  },
};

export function motionFor(s: Silhouette): MotionProfile {
  return PROFILES[s] ?? MARCH;
}

/**
 * Gait offsets for a unit at time `t`, phase-shifted per unit so a rank does not
 * move as one body.
 */
export function gait(
  p: MotionProfile,
  t: number,
  phase: number,
  moving: boolean,
): { bob: number; sway: number; tilt: number } {
  // Standing units keep a small idle breath so the field never looks frozen.
  const scale = moving ? 1 : 0.25;
  const w = (hz: number) => (t * hz + phase) * Math.PI * 2;
  // An airborne gait spends longer off the ground than on it, so the bounce is
  // rectified rather than a plain sine.
  const bobWave = p.airborne ? Math.abs(Math.sin(w(p.bobHz) / 2)) - 0.4 : Math.sin(w(p.bobHz));
  return {
    bob: bobWave * p.bobAmp * scale,
    sway: Math.sin(w(p.swayHz)) * p.swayAmp * scale,
    tilt: Math.sin(w(p.tiltHz)) * p.tiltAmp * scale,
  };
}

/**
 * Attack pose at `k` (0 → 1 through the swing). Returns a lunge along the facing
 * axis and a rotation, both of which peak early and recover — a strike is fast
 * out and slow back.
 */
export function attackPose(style: AttackStyle, k: number): { lunge: number; spin: number } {
  const snap = k < 0.3 ? k / 0.3 : 1 - (k - 0.3) / 0.7;
  switch (style) {
    case 'thrust':
      return { lunge: snap * 7, spin: 0 };
    case 'swing':
      return { lunge: snap * 3, spin: -snap * 0.9 };
    case 'charge':
      return { lunge: snap * 12, spin: snap * 0.16 };
    case 'stomp':
      return { lunge: snap * 4, spin: 0 };
    case 'lash':
      return { lunge: snap * 5, spin: snap * 0.5 };
    case 'shoot':
      // Recoil backwards rather than lunging forward.
      return { lunge: -snap * 3.5, spin: 0 };
  }
}
