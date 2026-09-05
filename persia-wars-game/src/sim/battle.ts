import type { Battle, Unit, UnitClass } from '../content/types';
import { getUnit } from '../content';
import { makeRng } from './rng';
import {
  ROUNDS_MAX,
  TIER_MULT,
  WILDCARD_MULT,
  exhaustionMultiplier,
  roundTickLimit,
  type LedgerEntry,
  type Tier,
} from './roundCore.ts';
import {
  FIELD_MAX,
  FIELD_MIN,
  MAX_TICKS,
  TICK_RATE,
  type BattleEvent,
  type BattleLog,
  type Frame,
  type Side,
  type SimUnit,
} from './types';

/*
 * BALANCE
 *
 * Damage is atk × counter-multiplier × a little noise, minus a share of the
 * target's def, floored at 1 so nothing is ever perfectly immune. The counter
 * multiplier is the teachable part: it comes straight from each unit's
 * `counters` / `counteredBy` lists in the content JSON, so a writer can retune
 * the triangle without opening this file.
 */
/*
 * Exported so the Scrolls' rules pages can quote the real numbers rather than
 * restate them in prose. A balance change then updates what the game tells the
 * player, instead of quietly making the rules page a lie.
 */
export const COUNTER_BONUS = 1.5;
export const COUNTERED_PENALTY = 0.7;
export const DEF_SCALE = 0.3;
export const DAMAGE_NOISE = 0.15;
/** Horse-archers back off when melee gets within this distance. */
export const KITE_DISTANCE = 7;
/** A gorge is too tight for horses and wheels to be worth much. */
export const GORGE_MOBILITY_PENALTY: Partial<Record<UnitClass, number>> = {
  cavalry: 0.7,
  'horse-archer': 0.75,
  chariot: 0.55,
};

export interface Squad {
  side: Side;
  /**
   * The side's squads, in the order they were drafted. A duplicate pick raises
   * a unit's tier rather than adding a second squad — Concept v0.2 §2.4 — so
   * this list is at most `MAX_SQUADS` long however many rounds have been played.
   */
  units: LedgerEntry[];
  /** Army-wide doctrine ids in force for this side. */
  doctrines: string[];
  /** The commander's passive and order, if one is chosen. */
  passive?: string;
  order?: string;
}

/*
 * COMMANDERS
 *
 * v0.1 §7 asks for "one visible tactical order charged during the match", which
 * means the player pressing a button mid-combat. That contradicts the game's own
 * stated rule — "once the squads are set, the battle plays itself; the draft was
 * the game" — and it would need a mid-combat message on the wire that both
 * clients agreed the exact tick of, or online play desyncs.
 *
 * So an order fires AUTOMATICALLY, at a trigger printed on the commander's card.
 * It keeps the auto-battler premise, it keeps determinism, and it still gives
 * each commander one dramatic moment. Recorded as a deviation in DECISIONS.md.
 */

/** Cyrus: each distinct class after the first blunts the exhaustion ramp. */
const COHESION_PER_CLASS = 0.14;
const COHESION_CAP = 0.5;
/** Cyrus' order: the first squad to fall gets up once, at half strength. */
const REFORM_HP = 0.5;
/** Astyages' order: reinforce a squad on the spot when two down. */
const MUSTER_HP = 0.45;
const MUSTER_ATK = 1.3;

/*
 * TRAITS AND DOCTRINES
 *
 * Concept v0.2 finding 1.3: a rank and a trait must not be able to do each
 * other's job. A rank is numbers — more men, better kit, the same tactics. A
 * trait changes *how the squad fights*, and never touches its rank.
 *
 * Every effect below is behavioural for that reason, and every one of them has
 * a cost, so no trait is simply "better".
 */

/** Ready Volley: shoot sooner, and be less ready when something arrives. */
const READY_VOLLEY_RANGE = 1.35;
const READY_VOLLEY_EXPOSED_DEF = 0.7;
/** Within this distance a Ready Volley archer counts as caught. */
const CAUGHT_DISTANCE = 4;
/** Long Reach: a longer spear touches first. Melee only. */
const LONG_REACH_BONUS = 0.9;
/** Wheeling Line: ticks held back before the riders commit. */
const WHEELING_DELAY = 170;
/** Loosed Rein: faster away, slower in. */
const LOOSED_REIN_KITE = 1.5;
const LOOSED_REIN_ADVANCE = 0.7;
/** The Centre Holds: the middle firms up, the wings pay for it. */
const CENTRE_DEF = 1.3;
const WING_DEF = 0.78;
/** Broken Ground: trained for a pass, wasted on a plain. */
const BROKEN_GROUND_GORGE = 1.18;
const BROKEN_GROUND_PLAIN = 0.9;
/** Shoot the Horses: what counts as a horse. */
const MOUNTED: UnitClass[] = ['cavalry', 'horse-archer', 'chariot'];

/**
 * Locked Shields, against something mounted.
 *
 * The counter triangle already has every infantry card countering cavalry, so
 * "gains cavalry as a counter" would have been a promise the unit already kept —
 * a card that reads as an effect and is not one. The wall's real benefit is that
 * a horse will not press home against a planted shield, so this is armour
 * against mounted attackers specifically, on top of the triangle.
 */
const LOCKED_SHIELDS_VS_MOUNTED = 2.3;

/** Locked Shields holds the middle of the field and does not step past it. */
const FIELD_MID = (FIELD_MIN + FIELD_MAX) / 2;

function terrainMultiplier(battle: Battle, cls: UnitClass): number {
  if (battle.field.terrain !== 'gorge') return 1;
  return GORGE_MOBILITY_PENALTY[cls] ?? 1;
}

/**
 * Men this squad puts on the field.
 *
 * `count` is the unit's own head count — a Kissian levy is eight, an Immortal
 * three, a war elephant one — and rank multiplies it, so ranking a levy up
 * gives you more levy rather than turning it into something else.
 *
 * Every man carries the squad's stat line DIVIDED by the head count, so a
 * squad is worth exactly what it was worth before it became a crowd. Head count
 * changes how a squad LOOKS and how it comes apart, never how strong it is.
 *
 * Giving each man the full stat line was tried first and was badly wrong: army
 * strength then scaled with head count, so a Kissian levy (8) was eight times
 * an elephant (1) at the same rank, and a tier-3 archer beat the cavalry that
 * counters it every time out of forty. The counter triangle is supposed to
 * outrank the ladder; head count had quietly outranked both.
 *
 * Dividing needs one care: armour is a FLAT subtraction, so def must be divided
 * with atk or a man with atk/8 against full armour does nothing at all. The
 * damage floor divides too — a squad's minimum volley is still 1, spread over
 * however many men are throwing it.
 *
 * What DOES change, deliberately, is granularity: a squad now loses power
 * smoothly as men fall instead of fighting at full strength until it pops.
 */
export const MEN_TIER_MULT = [1, 1.2, 1.45, 1.7] as const;
/** Hard ceiling per squad. Targeting is O(n^2) per tick and this bounds it. */
export const MAX_MEN = 10;

export function menInSquad(count: number, tier: Tier, doubled: boolean): number {
  const mult = MEN_TIER_MULT[Math.max(0, Math.min(3, tier - 1))] ?? 1;
  return Math.max(1, Math.min(MAX_MEN, Math.round(count * mult) * (doubled ? 2 : 1)));
}

function spawn(
  def: Unit,
  uid: number,
  side: Side,
  index: number,
  battle: Battle,
  entry: LedgerEntry,
  doctrines: string[],
  laneCount: number,
  file = 0,
  men = 1,
  /**
   * The divisor for this man's share of the squad.
   *
   * Normally equal to `men`. A Wildcard squad spawns TWICE the men but still
   * divides by the undoubled count, so the doubling actually doubles the squad
   * — dividing by the doubled count made ×2 a no-op that only looked like
   * something, which is exactly the kind of bug a test earns its keep on.
   */
  share = men,
): SimUnit {
  const terrain = terrainMultiplier(battle, def.class);
  const traits = entry.traits;
  // A tier is "more of the same": more men, better kit, the same tactics. It
  // multiplies attack, armour and health alike so the card stays recognisable.
  //
  // A Wildcard squad rides the SAME multiplier rather than a separate rule, so
  // it stays "more of the same" too — twice the men, not a different unit with
  // special powers. That also means it needs no new balance surface: it moves
  // the one number rank already moves.
  const t = (TIER_MULT[entry.tier - 1] ?? 1) * (entry.doubled ? WILDCARD_MULT : 1);

  // Wheeling Line riders come in wide, so they take the outermost lane rather
  // than their draft position — that is what makes it read as a flank.
  const wheeling = traits.includes('wheeling-line');
  const lane = wheeling ? (side === 'a' ? 0 : Math.max(0, laneCount - 1)) : index;

  let atk = def.atk * t * terrain;
  let armour = def.def * t;
  let hp = def.hp * t;
  let range = def.range;
  let speed = def.speed * terrain;
  const counters = [...def.counters];

  // --- traits ---------------------------------------------------------------
  if (traits.includes('ready-volley')) range *= READY_VOLLEY_RANGE;
  if (traits.includes('long-reach') && def.range < 3) range += LONG_REACH_BONUS;
  // Kept for a future roster that includes infantry which does not already
  // counter cavalry; every card in the current set does, which is why the real
  // effect is the armour bonus in `strike` rather than this line.
  if (traits.includes('locked-shields') && !counters.includes('cavalry')) counters.push('cavalry');
  if (traits.includes('loosed-rein')) speed *= LOOSED_REIN_ADVANCE;

  // --- doctrines ------------------------------------------------------------
  if (doctrines.includes('centre-holds')) {
    // Middle lanes firm up; the wings are what pays for it.
    const middle = lane === 1 || lane === 2;
    armour *= middle ? CENTRE_DEF : WING_DEF;
    if (middle) hp *= CENTRE_DEF;
  }
  if (doctrines.includes('broken-ground')) {
    atk *= battle.field.terrain === 'gorge' ? BROKEN_GROUND_GORGE : BROKEN_GROUND_PLAIN;
  }

  // Divided among the men. Not rounded — a man may be worth 3.8 hp, and
  // rounding each of ten men would quietly change what the squad is worth.
  const rounded = hp / share;
  /*
   * Every man of a squad stands at the SAME x. Formation depth is the
   * renderer's business, exactly as `lane` already is.
   *
   * This was tried the other way first and it broke four tests. x is the combat
   * axis, so a rank stood 1.3 units back is 1.3 units out of the fight — and a
   * spear's reach is about 1.5, so Long Reach's whole +0.9 advantage was
   * swamped by the formation it was standing in. Depth that the simulation can
   * feel is not depth, it is a handicap.
   */
  const ABREAST = 4;
  const offset = index * 3;
  return {
    uid,
    defId: def.id,
    side,
    squad: `${side}:${index}`,
    file,
    // Spread across the lane, centred, so the squad reads as a body of men.
    slot: men <= 1 ? 0 : ((file % ABREAST) / (ABREAST - 1) - 0.5) * 2,
    men: share,
    tier: entry.tier,
    doubled: entry.doubled,
    traits,
    cls: def.class,
    silhouette: def.art.silhouette,
    x: side === 'a' ? 14 - offset : 86 + offset,
    lane,
    hp: rounded,
    maxHp: rounded,
    // Terrain hits a unit's fighting value, not just its speed — a chariot in a
    // defile is not a slow chariot, it is a useless one.
    /*
     * atk and def stay at SQUAD scale. Only hp is divided.
     *
     * Armour is a flat subtraction, so a divided atk against an undivided def
     * collapses: six spearmen each swinging for a sixth could not scratch a
     * chariot, and chariots went from losing a gorge to winning every seed of
     * it. `strike` therefore computes the whole squad's blow with the original
     * formula and divides the RESULT by the attacker's head count — identical
     * total damage, identical armour behaviour, just delivered in more pieces.
     */
    atk,
    def: armour,
    range,
    speed,
    interval: def.attackInterval,
    cd: 0,
    counters,
    counteredBy: def.counteredBy,
    kite: def.kite || traits.includes('loosed-rein'),
    // Riders that wheel sit out the first clash and arrive on a busy flank.
    enterAt: wheeling ? WHEELING_DELAY : 0,
    holdLine: traits.includes('locked-shields'),
    alive: true,
  };
}

export function counterMultiplier(attacker: Pick<SimUnit, 'counters' | 'counteredBy'>, targetClass: UnitClass): number {
  if (attacker.counters.includes(targetClass)) return COUNTER_BONUS;
  if (attacker.counteredBy.includes(targetClass)) return COUNTERED_PENALTY;
  return 1;
}

/**
 * Who a unit goes for.
 *
 * Normally the nearest living enemy. Under Shoot the Horses, an archer ignores
 * whatever is closest and looks for something mounted first — which is the
 * doctrine's whole cost as well as its benefit: while the archers are answering
 * the wings, nothing is answering the centre.
 */
function nearestEnemy(u: SimUnit, enemies: SimUnit[], shootHorses: boolean): SimUnit | null {
  // `enemies` is this side's living opponents, rebuilt once a tick. Scanning
  // the whole roster per unit was O(n^2) over EVERY unit including the dead and
  // one's own side, which was survivable at twelve units and is not at ninety.
  const hunting =
    shootHorses && (u.cls === 'archer' || u.cls === 'horse-archer') && enemies.some(
      (o) => MOUNTED.includes(o.cls),
    );

  let best: SimUnit | null = null;
  let bestD = Infinity;
  for (const other of enemies) {
    if (hunting && !MOUNTED.includes(other.cls)) continue;
    const d = Math.abs(other.x - u.x);
    // Ties broken by uid so the result never depends on array iteration luck.
    if (d < bestD || (d === bestD && best !== null && other.uid < best.uid)) {
      bestD = d;
      best = other;
    }
  }
  return best;
}

/**
 * Runs one round.
 *
 * `round` sets how long the round may last and when lines begin to break —
 * see `roundCore.roundTickLimit` and `exhaustionMultiplier`. It defaults to the
 * last round, which is the most generous budget, so a caller that does not care
 * about rounds gets the old behaviour of "run until it resolves".
 */
export function simulate(
  battle: Battle,
  squadA: Squad,
  squadB: Squad,
  seed: number,
  round = ROUNDS_MAX,
): BattleLog {
  const rng = makeRng(seed);
  const units: SimUnit[] = [];
  let uid = 0;
  const tickLimit = Math.min(MAX_TICKS, roundTickLimit(round, TICK_RATE));

  const lanes = Math.max(squadA.units.length, squadB.units.length, 1);
  const doctrines: Record<Side, string[]> = { a: squadA.doctrines, b: squadB.doctrines };
  const passive: Record<Side, string | undefined> = { a: squadA.passive, b: squadB.passive };
  const order: Record<Side, string | undefined> = { a: squadA.order, b: squadB.order };
  const orderUsed: Record<Side, boolean> = { a: false, b: false };
  /*
   * Cyrus' Many Peoples. Counted once, from the squads as drafted: a wider army
   * holds together longer under pressure. Four of the same kind is worth nothing,
   * which is what makes it a reason to draft wide rather than a free bonus.
   */
  const cohesion: Record<Side, number> = { a: 0, b: 0 };
  for (const side of ['a', 'b'] as Side[]) {
    if (passive[side] !== 'many-peoples') continue;
    const squad = side === 'a' ? squadA : squadB;
    const classes = new Set(squad.units.map((e) => getUnit(e.unitId).class));
    cohesion[side] = Math.min(COHESION_CAP, Math.max(0, classes.size - 1) * COHESION_PER_CLASS);
  }
  // One ledger entry is now a body of men rather than one abstract block.
  for (const [side, squad] of [['a', squadA], ['b', squadB]] as const) {
    squad.units.forEach((e, i) => {
      const def = getUnit(e.unitId);
      const men = menInSquad(def.count, e.tier, Boolean(e.doubled));
      // Share is the UNDOUBLED count, so a Wildcard squad is twice the men AND
      // twice the squad rather than twice the men at half the value each.
      const share = menInSquad(def.count, e.tier, false);
      for (let f = 0; f < men; f++) {
        units.push(spawn(def, uid++, side, i, battle, e, doctrines[side], lanes, f, men, share));
      }
    });
  }

  const startHp: Record<Side, number> = {
    a: units.filter((u) => u.side === 'a').reduce((s, u) => s + u.maxHp, 0),
    b: units.filter((u) => u.side === 'b').reduce((s, u) => s + u.maxHp, 0),
  };

  const frames: Frame[] = [];
  let tick = 0;
  let winner: Side | 'draw' = 'draw';

  for (; tick < tickLimit; tick++) {
    const events: BattleEvent[] = [];
    // Living enemies per side, in roster order so tie-breaking is unchanged.
    const living: Record<Side, SimUnit[]> = { a: [], b: [] };
    for (const u of units) if (u.alive) living[u.side].push(u);

    for (const u of units) {
      if (!u.alive) continue;
      if (u.cd > 0) u.cd--;

      // Riders that wheel wide are not on the field yet.
      if (tick < u.enterAt) continue;

      const target = nearestEnemy(u, living[u.side === 'a' ? 'b' : 'a'], doctrines[u.side].includes('shoot-the-horses'));
      if (!target) continue;
      const dx = target.x - u.x;
      const dist = Math.abs(dx);
      const dir = dx === 0 ? (u.side === 'a' ? 1 : -1) : Math.sign(dx);

      // Horse-archers refuse to be caught: if something melee is closing and they
      // are not ready to shoot anyway, they give ground. This is the shape of the
      // "Parthian shot" the Saka used and the Parthians later made famous.
      if (u.kite && dist < KITE_DISTANCE && target.range < KITE_DISTANCE) {
        const away = u.traits.includes('loosed-rein') ? 0.8 * LOOSED_REIN_KITE : 0.8;
        u.x = Math.min(FIELD_MAX, Math.max(FIELD_MIN, u.x - dir * u.speed * away));
        if (u.cd === 0 && dist <= u.range) {
          events.push(strike(u, target, rng.range(1 - DAMAGE_NOISE, 1 + DAMAGE_NOISE), tick));
        }
        continue;
      }

      if (dist <= u.range) {
        if (u.cd === 0) events.push(strike(u, target, rng.range(1 - DAMAGE_NOISE, 1 + DAMAGE_NOISE), tick));
      } else {
        let next = u.x + dir * u.speed;
        // A shield wall takes the middle of the field and will not step past it.
        // "Will not pursue" has to mean something the player can watch happen.
        if (u.holdLine) {
          next = u.side === 'a' ? Math.min(next, FIELD_MID) : Math.max(next, FIELD_MID);
        }
        u.x = Math.min(FIELD_MAX, Math.max(FIELD_MIN, next));
      }
    }

    for (const u of units) {
      if (!u.alive || u.hp > 0) continue;

      /*
       * Cyrus — The Line Reforms. The first SQUAD you lose gets back up once.
       *
       * Squad, not man. With per-man entities the trigger has to wait until
       * every man of a squad is down, and then it stands the whole squad up
       * again — otherwise the order would fire on the first casualty of the
       * battle and revive one spearman, which is not what the card says.
       */
      if (order[u.side] === 'the-line-reforms' && !orderUsed[u.side]) {
        const squadmates = units.filter((x) => x.squad === u.squad);
        const lastStanding = squadmates.every((x) => x === u || !x.alive);
        if (lastStanding) {
          orderUsed[u.side] = true;
          for (const m of squadmates) {
            m.alive = true;
            m.hp = Math.max(1, Math.round(m.maxHp * REFORM_HP));
          }
          events.push({ t: 'order', uid: u.uid, order: 'the-line-reforms' });
          continue;
        }
      }

      u.alive = false;
      u.hp = 0;
      events.push({ t: 'death', uid: u.uid });

      // Astyages — Muster Again. Falling two squads behind reinforces one of
      // yours on the spot. It answers a collapse; it does not prevent one.
      for (const side of ['a', 'b'] as Side[]) {
        if (order[side] !== 'muster-again' || orderUsed[side]) continue;
        // Counted in SQUADS wiped out, not men killed. Two squads behind is a
        // collapse; two men behind is a skirmish, and the card means the first.
        const wiped = (s2: Side): number => {
          const keys = new Set(units.filter((x) => x.side === s2).map((x) => x.squad));
          let n = 0;
          for (const k of keys) if (units.every((x) => x.squad !== k || !x.alive)) n += 1;
          return n;
        };
        if (wiped(side) - wiped(side === 'a' ? 'b' : 'a') < 2) continue;
        // The healthiest surviving SQUAD: reinforcing one about to fall is a waste.
        const alive = units.filter((x) => x.side === side && x.alive);
        if (alive.length === 0) continue;
        const bySquad = new Map<string, SimUnit[]>();
        for (const m of alive) bySquad.set(m.squad, [...(bySquad.get(m.squad) ?? []), m]);
        const bestSquad = [...bySquad.entries()].sort(
          (p, q) =>
            q[1].reduce((n, x) => n + x.hp / x.maxHp, 0) / q[1].length -
              p[1].reduce((n, x) => n + x.hp / x.maxHp, 0) / p[1].length ||
            p[1][0].uid - q[1][0].uid,
        )[0];
        if (!bestSquad) continue;
        orderUsed[side] = true;
        for (const m of bestSquad[1]) {
          m.maxHp = Math.round(m.maxHp * (1 + MUSTER_HP));
          m.hp = Math.min(m.maxHp, Math.round(m.hp + m.maxHp * MUSTER_HP));
          m.atk *= MUSTER_ATK;
        }
        events.push({ t: 'order', uid: bestSquad[1][0].uid, order: 'muster-again' });
      }
    }

    frames.push({
      tick,
      pos: units.map((u) => ({ uid: u.uid, x: round2(u.x), hp: Math.max(0, Math.round(u.hp)) })),
      events,
    });

    const aliveA = units.some((u) => u.alive && u.side === 'a');
    const aliveB = units.some((u) => u.alive && u.side === 'b');
    if (!aliveA || !aliveB) {
      winner = aliveA ? 'a' : aliveB ? 'b' : 'draw';
      tick++;
      break;
    }
  }

  const remaining: Record<Side, number> = {
    a: sumHp(units, 'a') / startHp.a,
    b: sumHp(units, 'b') / startHp.b,
  };

  // Timed out with both sides standing: the side that took less punishment wins.
  // With the exhaustion ramp this is now rare rather than routine.
  if (winner === 'draw' && tick >= tickLimit) {
    if (remaining.a > remaining.b) winner = 'a';
    else if (remaining.b > remaining.a) winner = 'b';
  }

  return {
    seed,
    roster: units.map((u) => ({
      uid: u.uid,
      defId: u.defId,
      side: u.side,
      cls: u.cls,
      silhouette: u.silhouette,
      lane: u.lane,
      maxHp: u.maxHp,
      tier: u.tier,
      doubled: u.doubled,
      squad: u.squad,
      file: u.file,
      slot: u.slot,
      traits: u.traits,
    })),
    frames,
    winner,
    remaining,
    ticks: tick,
  };

  function strike(u: SimUnit, target: SimUnit, noise: number, tick: number): BattleEvent {
    const mult = counterMultiplier(u, target.cls);
    // Ready Volley bought its earlier shooting by being unready at contact.
    const caught =
      target.traits.includes('ready-volley') && Math.abs(target.x - u.x) <= CAUGHT_DISTANCE;
    let armour = caught ? target.def * READY_VOLLEY_EXPOSED_DEF : target.def;
    // A horse will not press home against a planted shield wall.
    if (target.holdLine && MOUNTED.includes(u.cls)) armour *= LOCKED_SHIELDS_VS_MOUNTED;
    // Lines break late in a round. Without this two armoured squads grind past
    // any sane round budget and the result falls to a health comparison, which
    // is a coin flip wearing a uniform.
    // Cohesion does not reduce damage — it delays the point at which a line
    // starts coming apart. A one-class army feels the full ramp.
    const weary = 1 + (exhaustionMultiplier(tick, tickLimit) - 1) * (1 - cohesion[target.side]);
    // The squad's blow, by the original formula, then split among the men
    // throwing it. Not rounded: at ten men a share can be worth less than a
    // point, and rounding it away would make big squads harmless.
    const dmg = Math.max(1, u.atk * mult * noise * weary - armour * DEF_SCALE) / u.men;
    target.hp -= dmg;
    u.cd = u.interval;
    return { t: 'attack', uid: u.uid, target: target.uid, dmg, mult };
  }
}

function sumHp(units: SimUnit[], side: Side): number {
  return units.filter((u) => u.side === side).reduce((s, u) => s + Math.max(0, u.hp), 0);
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
