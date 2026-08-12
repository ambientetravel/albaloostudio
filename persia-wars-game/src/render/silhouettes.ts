import { Graphics } from 'pixi.js';
import type { Silhouette } from '../content/types';

/**
 * PLACEHOLDER ART.
 *
 * These are procedural shapes standing in for the commissioned character art.
 * They exist so the loop is playable and testable, and they are not the art
 * direction. When real assets land, this file is deleted and the renderer swaps
 * to sprite textures — nothing else needs to change.
 *
 * Everything is drawn inside a 26 × 30 box centred on (0, 0), y+ downward.
 */

/**
 * The Achaemenid palette in the form Pixi wants. Mirrors the custom properties
 * in styles.css — keep the two in step.
 */
export const PALETTE = {
  ink: 0x0d1a33, // rim
  white: 0xede8db, // MXR-ACH-03 Stone White
  gold: 0xeec95f,
  goldDeep: 0xd4a22b, // MXR-ACH-02 Achaemenid Gold
  red: 0xb8412a, // MXR-ACH-06 Ochre Red — side A
  blue: 0x2e9c9a, // MXR-ACH-04 Persian Turquoise — side B
  turquoise: 0x4fc4c1,
  ochreHi: 0xd96b52,

  // Terrain. The plain is stone brown because Fars is not a green meadow, and
  // the gorge floor is a lighter tint of the same brown so the darker walls in
  // front of it stay legible as walls.
  sky: 0x1f3b6e, // MXR-ACH-01 Imperial Lapis
  skyDeep: 0x142a4f,
  ground: 0x7a5b45, // MXR-ACH-05 Stone Brown
  groundDeep: 0x543d2e,
  sand: 0xa58063,
  sandDeep: 0x7a5b45,
  rock: 0x2a4d8c,
  rockDeep: 0x142a4f,

  // Arena 1 (Anshan): a built platform rather than open country.
  brick: 0x9c7a5c,
  brickHi: 0xb89170,
  lapisDeep: 0x1a3260,
  lapisLine: 0x4a77b8,
} as const;

export function drawSilhouette(g: Graphics, kind: Silhouette, body: number, trim: number): void {
  g.clear();
  switch (kind) {
    case 'shield':
      // Tall standing wicker shield with a woven cross-hatch and a spear behind.
      g.moveTo(0, -16).lineTo(0, 14).stroke({ width: 2, color: trim });
      g.roundRect(-9, -13, 18, 26, 3).fill(body);
      g.roundRect(-9, -13, 18, 26, 3).stroke({ width: 2, color: trim });
      g.moveTo(-9, -4).lineTo(9, -4).moveTo(-9, 4).lineTo(9, 4).stroke({ width: 1.5, color: trim });
      break;

    case 'spear':
      // Guardsman: long spear, small round shield, tall headdress.
      g.moveTo(7, -18).lineTo(7, 15).stroke({ width: 2.5, color: trim });
      g.poly([7, -18, 4, -13, 10, -13]).fill(trim);
      g.roundRect(-8, -10, 13, 22, 4).fill(body);
      g.circle(-2, -14, 5).fill(body);
      g.rect(-5, -19, 6, 4).fill(trim);
      break;

    case 'bow':
      // Archer: drawn bow arc in front of the body.
      g.roundRect(-4, -10, 12, 22, 4).fill(body);
      g.circle(2, -14, 5).fill(body);
      g.arc(-4, -1, 12, -1.15, 1.15).stroke({ width: 2.5, color: trim });
      g.moveTo(-13, -12).lineTo(-13, 10).stroke({ width: 1.2, color: trim });
      g.moveTo(-13, -1).lineTo(4, -1).stroke({ width: 2, color: trim });
      break;

    case 'horse':
      // Rider: horse body with legs, rider torso and a raised javelin.
      g.ellipse(0, 4, 13, 6).fill(body);
      g.poly([11, 2, 15, -6, 12, -7, 8, -1]).fill(body);
      g.moveTo(-9, 9).lineTo(-10, 15).moveTo(-3, 9).lineTo(-4, 15).stroke({ width: 2, color: body });
      g.moveTo(5, 9).lineTo(6, 15).moveTo(10, 8).lineTo(11, 15).stroke({ width: 2, color: body });
      g.roundRect(-4, -10, 8, 12, 3).fill(trim);
      g.circle(0, -13, 4).fill(trim);
      g.moveTo(6, -18).lineTo(-2, 0).stroke({ width: 2, color: trim });
      break;

    case 'horse-bow':
      // Same horse, but the rider is turned in the saddle shooting backwards.
      g.ellipse(0, 4, 13, 6).fill(body);
      g.poly([11, 2, 15, -6, 12, -7, 8, -1]).fill(body);
      g.moveTo(-9, 9).lineTo(-10, 15).moveTo(-3, 9).lineTo(-4, 15).stroke({ width: 2, color: body });
      g.moveTo(5, 9).lineTo(6, 15).moveTo(10, 8).lineTo(11, 15).stroke({ width: 2, color: body });
      g.roundRect(-4, -10, 8, 12, 3).fill(trim);
      g.circle(-1, -13, 4).fill(trim);
      g.arc(-8, -8, 9, -1.3, 1.3).stroke({ width: 2.2, color: trim });
      break;

    case 'chariot':
      // Cart box, spoked wheel, and the blade jutting from the axle.
      g.roundRect(-6, -10, 15, 13, 2).fill(body);
      g.circle(-3, 7, 8).stroke({ width: 2.5, color: trim });
      g.moveTo(-11, 7).lineTo(5, 7).moveTo(-3, -1).lineTo(-3, 15).stroke({ width: 1.2, color: trim });
      g.poly([5, 7, 17, 3, 16, 8]).fill(PALETTE.white);
      g.circle(2, -14, 4).fill(trim);
      break;

    case 'elephant':
      // Bulk, trunk, tusk and a small tower on the back.
      g.ellipse(-1, 2, 15, 10).fill(body);
      g.circle(11, -1, 7).fill(body);
      g.moveTo(15, 3).bezierCurveTo(20, 8, 18, 14, 14, 15).stroke({ width: 3.5, color: body });
      g.moveTo(14, 1).lineTo(21, 4).stroke({ width: 2, color: PALETTE.white });
      g.moveTo(-11, 11).lineTo(-11, 16).moveTo(-3, 12).lineTo(-3, 16).stroke({ width: 4, color: body });
      g.moveTo(5, 12).lineTo(5, 16).stroke({ width: 4, color: body });
      g.roundRect(-9, -14, 14, 9, 2).fill(trim);
      break;

    case 'club':
      // Studded club raised over the shoulder, linen corselet beneath.
      g.roundRect(-7, -9, 13, 21, 4).fill(body);
      g.circle(-1, -14, 5).fill(body);
      g.moveTo(4, -2).lineTo(11, -14).stroke({ width: 2.5, color: trim });
      g.roundRect(8, -21, 8, 9, 3).fill(trim);
      g.circle(10, -18, 1.4).circle(14, -16, 1.4).fill(PALETTE.white);
      break;

    case 'lasso':
      // Rider swinging a noose — no armour, which is the point of the unit.
      g.ellipse(-1, 5, 12, 5).fill(body);
      g.poly([10, 3, 14, -4, 11, -5, 7, 0]).fill(body);
      g.moveTo(-8, 9).lineTo(-9, 15).moveTo(4, 9).lineTo(5, 15).stroke({ width: 2, color: body });
      g.roundRect(-4, -9, 8, 11, 3).fill(trim);
      g.circle(0, -12, 4).fill(trim);
      g.ellipse(9, -15, 7, 4).stroke({ width: 2, color: trim });
      g.moveTo(3, -11).lineTo(6, -13).stroke({ width: 1.6, color: trim });
      break;

    case 'camel':
      // Two humps and a long neck, with a bow-armed rider between them.
      g.ellipse(-2, 3, 13, 6).fill(body);
      g.ellipse(-6, -3, 5, 4).ellipse(2, -3, 5, 4).fill(body);
      g.moveTo(10, 2).lineTo(13, -10).stroke({ width: 3.5, color: body });
      g.circle(14, -12, 3.5).fill(body);
      g.moveTo(-9, 8).lineTo(-10, 16).moveTo(-3, 8).lineTo(-3, 16).stroke({ width: 2, color: body });
      g.moveTo(4, 8).lineTo(5, 16).stroke({ width: 2, color: body });
      g.roundRect(-4, -12, 8, 9, 3).fill(trim);
      g.arc(-2, -14, 8, -1.2, 1.2).stroke({ width: 2, color: trim });
      break;
  }
}
