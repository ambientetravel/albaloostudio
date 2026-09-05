import type { Silhouette, UnitClass } from '../content/types';
import type { Tier } from './roundCore.ts';

export type Side = 'a' | 'b';

/** The battlefield is 100 units wide; both ends are off-limits so nobody walks off it. */
export const FIELD_WIDTH = 100;
export const FIELD_MIN = 2;
export const FIELD_MAX = 98;
/** Sim ticks per second. Playback runs at the same rate at 1× speed. */
export const TICK_RATE = 20;
/** Safety valve: a stalemate is called rather than looping forever. */
export const MAX_TICKS = 2400;

export interface SimUnit {
  uid: number;
  defId: string;
  side: Side;
  /** Levy → Trained → Veteran → Royal. Scales atk, def and hp together. */
  tier: Tier;
  /** Taken on a Wildcard round: this squad counts double. */
  doubled?: boolean;
  /** Trait ids from Upgrade cards. Behaviour only — never a rank. */
  traits: string[];
  cls: UnitClass;
  silhouette: Silhouette;
  x: number;
  /** Visual row only — combat distance is measured along x. */
  lane: number;
  hp: number;
  maxHp: number;
  atk: number;
  def: number;
  range: number;
  speed: number;
  interval: number;
  cd: number;
  /** Tick this unit joins the fight. Non-zero only for Wheeling Line. */
  enterAt: number;
  /** Locked Shields: takes the middle of the field and does not step past it. */
  holdLine: boolean;
  counters: UnitClass[];
  counteredBy: UnitClass[];
  kite: boolean;
  alive: boolean;
}

export type BattleEvent =
  | { t: 'attack'; uid: number; target: number; dmg: number; mult: number }
  | { t: 'death'; uid: number }
  /** A commander's order fired. One a match, at the trigger on the card. */
  | { t: 'order'; uid: number; order: string };

/** One tick of playback. Positions are absolute so the renderer can lerp freely. */
export interface Frame {
  tick: number;
  pos: { uid: number; x: number; hp: number }[];
  events: BattleEvent[];
}

export interface BattleLog {
  seed: number;
  /** Static per-unit facts the renderer needs once. */
  roster: {
    uid: number;
    defId: string;
    side: Side;
    cls: UnitClass;
    silhouette: Silhouette;
    lane: number;
    maxHp: number;
    tier: Tier;
    /** Taken on a Wildcard round — the renderer draws twice the men. */
    doubled?: boolean;
    /** Men to draw at Levy rank; the renderer scales it by tier. */
    count: number;
    traits: string[];
  }[];
  frames: Frame[];
  winner: Side | 'draw';
  /** Fraction of starting HP each side finished with — drives the result screen. */
  remaining: Record<Side, number>;
  ticks: number;
}
