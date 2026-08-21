import { useEffect, useRef } from 'react';
import { Application, Assets, Container, Graphics, Sprite, Texture } from 'pixi.js';
import type { Battle, Silhouette } from '../content/types';
import { getArena } from '../content';
import type { BattleLog } from '../sim/types';
import { FIELD_MAX, FIELD_MIN, TICK_RATE } from '../sim/types';
import { themeFor } from '../ui/arenaTheme';
import { attackPose, gait, motionFor } from './motion';
import { PALETTE, drawSilhouette } from './silhouettes';
import { unitArtUrl } from './unitArt';

const SIDE_COLOR = { a: PALETTE.red, b: PALETTE.blue } as const;
const SIDE_TRIM = { a: PALETTE.gold, b: PALETTE.white } as const;
const LANE_COUNT = 4;
/** Seconds an attack streak or a strike flare stays on screen. */
const FLASH_LIFE = 0.2;
/** Seconds a unit spends in its attack pose. */
const SWING_LIFE = 0.34;
/**
 * How long a struck unit reacts for.
 *
 * The attacker had a swing and the hit had a flare, but the VICTIM did nothing —
 * so a blow landed on a figure that went on breathing as though nothing had
 * touched it, and the whole exchange read as decoration rather than damage.
 * Short on purpose: long enough to see, too short to fight the gait.
 */
const HURT_LIFE = 0.22;

const hex = (s: string): number => Number.parseInt(s.replace('#', ''), 16);
/**
 * Local height of a commissioned sprite, matched to the placeholder shapes so a
 * half-finished roster does not look like two different scales on one field.
 */
const SPRITE_HEIGHT = 38;

interface Props {
  log: BattleLog;
  battle: Battle;
  /** The ladder rung being fought on — decides the floor. */
  arenaId: number;
  speed: number;
  /** Fires once, when playback reaches the end of the log. */
  onFinished: () => void;
}

interface Flash {
  from: number;
  to: number;
  mult: number;
  life: number;
}

/** A commander's order firing. One a match, so it gets a ring of its own. */
interface OrderBurst {
  uid: number;
  life: number;
}
const ORDER_LIFE = 1.1;

interface Shot {
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  kind: 'arrow' | 'stone';
  life: number;
  total: number;
}

/**
 * The battlefield.
 *
 * **Portrait, and the player is at the bottom.** The simulation is
 * one-dimensional — every unit has a single "advance" coordinate — so rotating
 * the field is purely a rendering decision: the same deterministic log is mapped
 * down the screen instead of across it. Nothing in `sim/` changed, which is what
 * keeps two online clients agreeing on the result while drawing it differently.
 *
 * The view is the arena floor seen from above, not a landscape with a horizon.
 * Two ranks face each other along the length of the phone and close on the
 * middle, each unit moving the way its own kind moves — see `motion.ts`.
 */
export function BattleCanvas({ log, battle, arenaId, speed, onFinished }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  // Read through refs so changing speed doesn't tear down and rebuild the canvas.
  const speedRef = useRef(speed);
  const finishedRef = useRef(false);
  const onFinishedRef = useRef(onFinished);
  speedRef.current = speed;
  onFinishedRef.current = onFinished;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    let destroyed = false;
    let app: Application | null = null;
    let observer: ResizeObserver | null = null;
    finishedRef.current = false;

    const hostSize = (): { w: number; h: number } => {
      const r = host.getBoundingClientRect();
      // The host can measure 0 before first layout; never hand Pixi a zero size.
      return { w: Math.max(1, Math.round(r.width)), h: Math.max(1, Math.round(r.height)) };
    };

    void (async () => {
      const instance = new Application();
      const initial = hostSize();
      await instance.init({
        backgroundAlpha: 0,
        antialias: true,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
        autoDensity: true,
        width: initial.w,
        height: initial.h,
      });
      if (destroyed) {
        instance.destroy(true, { children: true });
        return;
      }
      app = instance;
      host.replaceChildren(instance.canvas);

      observer = new ResizeObserver(() => {
        const { w, h } = hostSize();
        if (w !== instance.screen.width || h !== instance.screen.height) instance.renderer.resize(w, h);
      });
      observer.observe(host);

      const ground = new Graphics();
      const shotLayer = new Graphics();
      const flashLayer = new Graphics();
      const unitLayer = new Container();
      instance.stage.addChild(ground, unitLayer, shotLayer, flashLayer);

      const theme = themeFor(getArena(arenaId).slug);
      const accent = hex(theme.accent);
      // The floor is the LIGHTER token and the surround the darkest, so the
      // fighting ground separates from what encloses it. The other way round
      // the two read as one flat slab.
      const floor = hex(theme.surface);
      const floorDeep = hex(theme.rim);
      const rim = hex(theme.rimLight);

      /**
       * Commissioned art is a texture; a unit still waiting for art is the old
       * vector shape. Both are Containers, so everything downstream — the gait,
       * the lunge, the death spin — is identical either way.
       */
      const artUrls = [...new Set(log.roster.map((u) => unitArtUrl(u.defId)))].filter(
        (u): u is string => u !== null,
      );
      const textures = new Map<string, Texture>();
      if (artUrls.length > 0) {
        const loaded = await Promise.all(artUrls.map((u) => Assets.load<Texture>(u)));
        artUrls.forEach((u, i) => textures.set(u, loaded[i]));
        if (destroyed) {
          instance.destroy(true, { children: true });
          return;
        }
      }

      interface Piece {
        root: Container;
        body: Container;
        bar: Graphics;
        silhouette: Silhouette;
        phase: number;
        /** Counts down while the unit is mid-swing. */
        swing: number;
        /** Counts down while the unit is recoiling from a hit. */
        hurt: number;
        /** True when this unit is commissioned art rather than a placeholder. */
        tall: boolean;
      }

      const sprites = new Map<number, Piece>();
      for (const u of log.roster) {
        const root = new Container();

        const url = unitArtUrl(u.defId);
        const texture = url ? textures.get(url) : undefined;
        let body: Container;
        // The ring has to match whatever it sits under: a horseman is half again
        // as wide as an archer, and one fixed ellipse looks wrong beneath both.
        let ringRx = 9;
        if (texture) {
          const art = new Sprite(texture);
          // Feet essentially on the origin, with a sliver below so the figure
          // meets the ground rather than hovering over it.
          art.anchor.set(0.5, 0.94);
          art.height = SPRITE_HEIGHT;
          art.width = (texture.width / texture.height) * SPRITE_HEIGHT;
          ringRx = Math.max(7, art.width * 0.42);
          body = art;
        } else {
          const shape = new Graphics();
          drawSilhouette(shape, u.silhouette, SIDE_COLOR[u.side], SIDE_TRIM[u.side]);
          body = shape;
        }

        // The team is read off a coloured ring on the ground, not off the unit.
        // Tinting full-colour art muddies it, and two armies of muddy figures is
        // worse than no team colour at all.
        const ringY = texture ? 1 : 13;
        const ring = new Graphics();
        ring.ellipse(0, ringY, ringRx, ringRx * 0.34).fill({ color: SIDE_COLOR[u.side], alpha: 0.5 });
        ring
          .ellipse(0, ringY, ringRx, ringRx * 0.34)
          .stroke({ width: 1.2, color: SIDE_TRIM[u.side], alpha: 0.75 });

        const bar = new Graphics();
        root.addChild(ring, body, bar);
        unitLayer.addChild(root);
        sprites.set(u.uid, {
          root,
          body,
          bar,
          silhouette: u.silhouette,
          // Phase-shift per unit so a rank does not move as one body.
          phase: (u.uid * 0.37) % 1,
          swing: 0,
          hurt: 0,
          tall: Boolean(texture),
        });
      }

      const flashes: Flash[] = [];
      const shots: Shot[] = [];
      const bursts: OrderBurst[] = [];
      let elapsedTicks = 0;
      let lastAppliedFrame = -1;
      let clock = 0;

      /**
       * Field position → screen Y. Low field values sit at the BOTTOM, which is
       * where side A spawns, so the player's own army is nearest to them.
       */
      const toScreenY = (pos: number, h: number): number => {
        const pad = h * 0.07;
        const usable = h - pad * 2;
        return h - pad - ((pos - FIELD_MIN) / (FIELD_MAX - FIELD_MIN)) * usable;
      };
      /**
       * Lane → screen X. The two sides share a lane, so each is nudged off its
       * centreline: head-on they used to stack exactly on top of each other and
       * the rear one vanished.
       */
      const laneX = (lane: number, side: 'a' | 'b', w: number): number => {
        // Commissioned sprites are wider than the placeholder shapes were, so
        // the lanes have to spread further or neighbours overlap.
        const pad = w * 0.08;
        const step = (w - pad * 2) / LANE_COUNT;
        return pad + step * (lane + 0.5) + (side === 'a' ? -1 : 1) * step * 0.16;
      };
      /**
       * The silhouettes are drawn at a size that suited a wide field seen from
       * the side. On a phone-width portrait floor they came out about 20px tall
       * and read as specks, so they are scaled to the width they have to share.
       */
      const unitScale = (w: number): number => Math.max(1.2, Math.min(2.4, w / 172));

      const paintFloor = (w: number, h: number): void => {
        ground.clear();

        // Surround: the city or crowd the arena sits in.
        ground.rect(0, 0, w, h).fill(floorDeep);

        const inset = Math.min(w * 0.06, 22);
        const fx = inset;
        const fy = h * 0.045;
        const fw = w - inset * 2;
        const fh = h - fy * 2;
        const r = Math.min(28, fw * 0.09);

        // The fighting floor.
        ground.roundRect(fx - 5, fy - 5, fw + 10, fh + 10, r + 4).fill(accent);
        ground.roundRect(fx, fy, fw, fh, r).fill(floor);

        // Territory. Each half carries a wash of its own side's colour, so
        // "my end" and "their end" read instantly instead of having to be
        // worked out from where the sprites happen to be standing. Kept very
        // low so it tints the ground rather than repainting it — the arena's
        // own floor colour still has to come through.
        //
        // Side A holds the BOTTOM of the screen and B the top, which is the
        // same convention `toScreenY` and `facing` use.
        const halfAlpha = 0.11;
        ground
          .roundRect(fx, fy, fw, fh / 2, r)
          .fill({ color: SIDE_COLOR.b, alpha: halfAlpha });
        ground
          .roundRect(fx, fy + fh / 2, fw, fh / 2, r)
          .fill({ color: SIDE_COLOR.a, alpha: halfAlpha });

        // Tile grid, denser along the axis of advance so distance reads.
        const cols = 6;
        const rows = 14;
        for (let c = 1; c < cols; c++) {
          const x = fx + (fw / cols) * c;
          ground.moveTo(x, fy).lineTo(x, fy + fh);
        }
        for (let rIdx = 1; rIdx < rows; rIdx++) {
          const y = fy + (fh / rows) * rIdx;
          ground.moveTo(fx, y).lineTo(fx + fw, y);
        }
        ground.stroke({ width: 1, color: rim, alpha: 0.35 });

        // Halfway line — where the two ranks meet.
        ground
          .moveTo(fx, fy + fh / 2)
          .lineTo(fx + fw, fy + fh / 2)
          .stroke({ width: 2, color: accent, alpha: 0.55 });

        // Centre medallion.
        const cx = fx + fw / 2;
        const cy = fy + fh / 2;
        const rad = Math.min(fw, fh) * 0.17;
        ground.circle(cx, cy, rad).stroke({ width: 3, color: accent, alpha: 0.45 });
        ground.circle(cx, cy, rad * 0.55).stroke({ width: 2, color: accent, alpha: 0.3 });
        for (let i = 0; i < 8; i++) {
          const a = (i / 8) * Math.PI * 2;
          ground
            .moveTo(cx + Math.cos(a) * rad * 0.55, cy + Math.sin(a) * rad * 0.55)
            .lineTo(cx + Math.cos(a) * rad, cy + Math.sin(a) * rad);
        }
        ground.stroke({ width: 1.5, color: accent, alpha: 0.3 });

        // The two baselines, so it is obvious which end is yours.
        ground.roundRect(fx + fw * 0.2, fy + fh - 8, fw * 0.6, 5, 3).fill(SIDE_COLOR.a);
        ground.roundRect(fx + fw * 0.2, fy + 3, fw * 0.6, 5, 3).fill(SIDE_COLOR.b);

        // Corner posts.
        for (const [px, py] of [
          [fx, fy],
          [fx + fw, fy],
          [fx, fy + fh],
          [fx + fw, fy + fh],
        ]) {
          ground.circle(px, py, 9).fill(accent);
          ground.circle(px, py, 9).stroke({ width: 2, color: rim });
        }
      };

      instance.ticker.add((ticker) => {
        const w = instance.screen.width;
        const h = instance.screen.height;
        paintFloor(w, h);

        const dt = ticker.deltaMS / 1000;
        clock += dt;
        elapsedTicks += dt * TICK_RATE * speedRef.current;

        const idx = Math.min(Math.floor(elapsedTicks), log.frames.length - 1);
        const frame = log.frames[idx];
        const nextFrame = log.frames[Math.min(idx + 1, log.frames.length - 1)];
        const alpha = Math.min(1, elapsedTicks - idx);

        // Apply every event we skipped past, so a 4x replay never drops a death.
        for (let f = lastAppliedFrame + 1; f <= idx; f++) {
          for (const ev of log.frames[f].events) {
            if (ev.t === 'order') {
              bursts.push({ uid: ev.uid, life: ORDER_LIFE });
              continue;
            }
            if (ev.t !== 'attack') continue;
            flashes.push({ from: ev.uid, to: ev.target, mult: ev.mult, life: FLASH_LIFE });
            const s = sprites.get(ev.uid);
            if (s) s.swing = SWING_LIFE;
            // The one being hit reacts too. Without this the blow lands on a
            // figure that carries on breathing as if nothing touched it.
            const victim = sprites.get(ev.target);
            if (victim) victim.hurt = HURT_LIFE;
          }
        }
        lastAppliedFrame = idx;

        const screen = new Map<number, { x: number; y: number }>();

        for (let i = 0; i < frame.pos.length; i++) {
          const p = frame.pos[i];
          const np = nextFrame.pos[i];
          const meta = log.roster[i];
          const sprite = sprites.get(p.uid);
          if (!sprite || !meta) continue;

          const pos = p.x + (np.x - p.x) * alpha;
          const baseY = toScreenY(pos, h);
          const baseX = laneX(meta.lane, meta.side, w);

          const profile = motionFor(sprite.silhouette);
          const moving = Math.abs(np.x - p.x) > 0.01;
          const g = gait(profile, clock, sprite.phase, moving);

          // Side A advances up the screen, side B down it.
          const facing = meta.side === 'a' ? -1 : 1;

          let lunge = 0;
          let spin = 0;
          if (sprite.swing > 0) {
            sprite.swing = Math.max(0, sprite.swing - dt);
            const k = 1 - sprite.swing / SWING_LIFE;
            const pose = attackPose(profile.attack, k);
            lunge = pose.lunge * facing;
            spin = pose.spin * facing;
          }

          // Recoil: a short jolt away from whoever hit them, and a squash, so a
          // landed blow is visible on the body and not only in the flare.
          let recoil = 0;
          let squash = 1;
          if (sprite.hurt > 0) {
            sprite.hurt = Math.max(0, sprite.hurt - dt);
            const h = sprite.hurt / HURT_LIFE;
            recoil = h * 3.4 * -facing;
            squash = 1 + h * 0.14;
          }

          const x = baseX + g.sway;
          const y = baseY - Math.abs(g.bob) + lunge + recoil;
          screen.set(p.uid, { x, y });
          const k = unitScale(w);
          sprite.root.position.set(x, y);
          sprite.root.scale.set(k * squash, k / squash);
          // The health bar is chrome, not anatomy: counter-scale it so it stays
          // the same size on an elephant and on an archer. The recoil squash is
          // non-uniform, so this has to undo BOTH axes — a plain 1/k would leave
          // the bar squashing along with the body every time the unit was hit.
          sprite.bar.scale.set(1 / (k * squash), squash / k);
          sprite.body.rotation = g.tilt + spin;

          const hpFrac = meta.maxHp > 0 ? p.hp / meta.maxHp : 0;
          if (p.hp <= 0) {
            sprite.root.alpha = Math.max(0, sprite.root.alpha - dt * 2.5);
            sprite.body.rotation += dt * 3 * facing;
            sprite.bar.clear();
          } else {
            sprite.root.alpha = 1;
            sprite.bar.clear();
            // The bar is counter-scaled, so this offset is in WORLD pixels — it
            // has to include the unit's scale or it lands on the chest instead
            // of above the head, which is exactly what it did first time.
            const barY = sprite.tall ? -SPRITE_HEIGHT * 0.94 * k - 8 : -22 * k - 10;
            sprite.bar.roundRect(-15, barY, 30, 7, 3).fill(PALETTE.ink);
            sprite.bar
              .roundRect(-13, barY + 2, 26 * hpFrac, 3, 2)
              .fill(hpFrac > 0.5 ? PALETTE.turquoise : hpFrac > 0.25 ? PALETTE.gold : PALETTE.ochreHi);
          }
        }

        // --- projectiles ------------------------------------------------------
        for (let i = flashes.length - 1; i >= 0; i--) {
          const fl = flashes[i];
          if (fl.life !== FLASH_LIFE) continue; // only spawn on the first frame
          const from = screen.get(fl.from);
          const to = screen.get(fl.to);
          const shooter = sprites.get(fl.from);
          const proj = shooter && motionFor(shooter.silhouette).projectile;
          if (from && to && proj) {
            const dist = Math.hypot(to.x - from.x, to.y - from.y);
            const total = Math.max(0.08, dist / proj.speed);
            shots.push({ fromX: from.x, fromY: from.y, toX: to.x, toY: to.y, kind: proj.kind, life: total, total });
          }
        }

        shotLayer.clear();
        for (let i = shots.length - 1; i >= 0; i--) {
          const s = shots[i];
          s.life -= dt;
          if (s.life <= 0) {
            shots.splice(i, 1);
            continue;
          }
          const k = 1 - s.life / s.total;
          const x = s.fromX + (s.toX - s.fromX) * k;
          const y = s.fromY + (s.toY - s.fromY) * k;
          const ang = Math.atan2(s.toY - s.fromY, s.toX - s.fromX);
          if (s.kind === 'arrow') {
            const len = 9;
            shotLayer
              .moveTo(x - Math.cos(ang) * len, y - Math.sin(ang) * len)
              .lineTo(x, y)
              .stroke({ width: 2, color: PALETTE.gold });
            shotLayer.circle(x, y, 1.6).fill(PALETTE.white);
          } else {
            shotLayer.circle(x, y, 2.6).fill(PALETTE.white);
          }
        }

        // --- strike flares ----------------------------------------------------
        flashLayer.clear();
        for (let i = flashes.length - 1; i >= 0; i--) {
          const fl = flashes[i];
          fl.life -= dt;
          if (fl.life <= 0) {
            flashes.splice(i, 1);
            continue;
          }
          const to = screen.get(fl.to);
          if (!to) continue;
          const fade = fl.life / FLASH_LIFE;
          // Gold for a favourable matchup, white for neutral, red when countered.
          const color = fl.mult > 1 ? PALETTE.gold : fl.mult < 1 ? PALETTE.red : PALETTE.white;
          flashLayer.circle(to.x, to.y - 4, 4 + 10 * (1 - fade)).stroke({ width: 2.5, color, alpha: fade });
        }

        // --- commander orders ------------------------------------------------
        for (let i = bursts.length - 1; i >= 0; i--) {
          const b = bursts[i];
          b.life -= dt;
          if (b.life <= 0) {
            bursts.splice(i, 1);
            continue;
          }
          const at = screen.get(b.uid);
          if (!at) continue;
          const k = 1 - b.life / ORDER_LIFE;
          // An expanding gold ring: one a match, so it should be unmistakable.
          flashLayer
            .circle(at.x, at.y - 6, 8 + 46 * k)
            .stroke({ width: 3.5 * (1 - k), color: PALETTE.gold, alpha: 1 - k });
          flashLayer
            .circle(at.x, at.y - 6, 4 + 26 * k)
            .stroke({ width: 2.5 * (1 - k), color: PALETTE.white, alpha: (1 - k) * 0.8 });
        }

        if (idx >= log.frames.length - 1 && !finishedRef.current) {
          finishedRef.current = true;
          onFinishedRef.current();
        }
      });
    })();

    return () => {
      destroyed = true;
      observer?.disconnect();
      observer = null;
      if (app) {
        app.destroy(true, { children: true });
        app = null;
      }
      host.replaceChildren();
    };
  }, [log, battle, arenaId]);

  return <div className="battle-canvas" ref={hostRef} aria-hidden="true" />;
}
