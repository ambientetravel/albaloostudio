import { Container, Sprite, Texture } from 'pixi.js';

/**
 * Skeletal rigs for unit sprites.
 *
 * A still image pushed around by a sine wave is not a gallop — the horse has no
 * legs that move. This cuts the painted sprite into parts, hangs them on
 * pivots, and animates the pivots, which is what a 2D skeletal tool like Rive
 * or Spine does. Done natively because Pixi's `Container` IS a transform
 * hierarchy: a bone is a container with a pivot, and that is the whole idea.
 *
 * The trade against a real tool, stated plainly: in Rive you would tune these
 * curves in an editor and see them immediately, and you would get MESH
 * deformation, so a leg bends rather than swinging rigid. This is rigid-part
 * animation, which is the cheaper half of what Rive does. It is worth doing
 * first because it proves the cut and the timing before anyone buys a licence —
 * and if the gallop reads at 40px, the bending probably is not needed at all.
 *
 * Parts come from `tools/rig/cut_horse.py`, which keeps every part on the full
 * canvas so all four share one origin and a pivot is just a coordinate.
 */

export type RigPart = 'body' | 'legs-front' | 'legs-hind' | 'tail';
export const RIG_PARTS: RigPart[] = ['tail', 'legs-hind', 'body', 'legs-front'];

export interface Joint {
  /** Where this part turns, in texture pixels. */
  pivot: [number, number];
  /** Draw order, back to front. */
  z: number;
}

export interface RigDef {
  /** Texture dimensions the pivots are measured in. */
  size: [number, number];
  joints: Record<RigPart, Joint>;
}

/**
 * The mounted rig. Pivots measured off `persian-cavalry.png` (168x256): the
 * hind legs meet the barrel at the stifle, the forelegs at the shoulder, the
 * tail at the dock, and the whole animal turns about the hip.
 */
export const HORSE_RIG: RigDef = {
  size: [168, 256],
  joints: {
    tail: { pivot: [37, 132], z: 0 },
    'legs-hind': { pivot: [72, 200], z: 1 },
    body: { pivot: [85, 195], z: 2 },
    'legs-front': { pivot: [122, 200], z: 3 },
  },
};

export interface RigPose {
  /** Rotation per part, radians. */
  rot: Record<RigPart, number>;
  /** Whole-body rise, in texture pixels. Negative is up. */
  lift: number;
}

/**
 * A gallop, from Muybridge.
 *
 * *The Horse in Motion*, 1878, settled what a gallop actually is, and the fact
 * everyone remembers is exactly the one that matters here: **all four feet
 * leave the ground when the legs are GATHERED UNDER the body, not when they are
 * stretched out.** Every painting before 1878 had it backwards, and so does any
 * animation that throws the legs wide at the top of the bounce.
 *
 * So the lift peaks when fore and hind are closest together, and the horse is
 * at its lowest as the forelegs reach out to take the landing.
 *
 * `t` is the stride phase in [0, 1).
 */
export function gallop(t: number): RigPose {
  const tau = Math.PI * 2;
  // Hind legs drive back then gather forward. Forelegs run counter-phase —
  // reaching as the hind gather, folding as the hind drive.
  const hind = Math.sin(tau * t);
  const fore = Math.sin(tau * (t + 0.45));
  /*
   * Fore and hind cross TWICE a stride — once folded under in suspension, once
   * planted under in stance — and only one of those is airborne. The offset of
   * 0.45 rather than a clean 0.5 is what separates them: the crossings land at
   * t = 0.025 and t = 0.525, and the lift is centred on the first.
   *
   * Getting this wrong is not subtle and not visible in a screenshot: the horse
   * rises while its legs are stretched out, which is the pose every painter
   * used before 1878 and the exact thing Muybridge disproved. A test pins it.
   */
  const SUSPENSION = 0.025;
  const gathered = Math.max(0, Math.cos(tau * (t - SUSPENSION)));
  return {
    rot: {
      'legs-hind': hind * 0.5,
      'legs-front': fore * 0.55,
      // Pitches nose-down as the forehand takes the landing.
      body: Math.sin(tau * (t + 0.3)) * 0.075,
      // The tail streams, lagging the body it hangs off.
      tail: Math.sin(tau * (t - 0.15)) * 0.3,
    },
    lift: -gathered * 7,
  };
}

/** Standing: a breath, not a freeze. */
export function idle(t: number): RigPose {
  const s = Math.sin(Math.PI * 2 * t * 0.25);
  return {
    rot: { 'legs-hind': 0, 'legs-front': 0, body: s * 0.012, tail: s * 0.14 },
    lift: 0,
  };
}

export interface RiggedFigure {
  root: Container;
  parts: Record<RigPart, Sprite>;
}

/** Builds the display objects. Parts share one origin by construction. */
export function buildRig(def: RigDef, textures: Record<RigPart, Texture>): RiggedFigure {
  const root = new Container();
  const parts = {} as Record<RigPart, Sprite>;
  for (const name of [...RIG_PARTS].sort((a, b) => def.joints[a].z - def.joints[b].z)) {
    const joint = def.joints[name];
    const sp = new Sprite(textures[name]);
    // Pivot and position at the same point: the part turns about its joint and
    // still lands exactly where it was painted.
    sp.pivot.set(joint.pivot[0], joint.pivot[1]);
    sp.position.set(joint.pivot[0], joint.pivot[1]);
    root.addChild(sp);
    parts[name] = sp;
  }
  return { root, parts };
}

/** Applies a pose. Once a frame, per figure. */
export function applyPose(fig: RiggedFigure, pose: RigPose): void {
  for (const name of RIG_PARTS) {
    const sp = fig.parts[name];
    if (sp) sp.rotation = pose.rot[name] ?? 0;
  }
  fig.root.y = pose.lift;
}
