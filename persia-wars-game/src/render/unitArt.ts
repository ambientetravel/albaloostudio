import { content } from '../content';

/**
 * Commissioned unit art, with the placeholder silhouettes as the fallback.
 *
 * Art arrives a few units at a time. Rather than gate the whole game on all
 * twenty-five, every lookup answers "sprite or shape?" per unit, so a build with
 * four finished sprites and twenty-one placeholders renders correctly and the
 * two are visibly different — which is the point. Nobody has to remember which
 * units are done.
 *
 * A sprite is registered here only when the file actually exists in the build,
 * so a typo'd id falls back to the shape instead of drawing nothing.
 */

/**
 * Vite resolves this at build time — the set of files really shipped, with
 * hashed URLs. Deliberately NOT a glob over `public/`: that returns a path
 * which happens to work in the dev server and 404s in a production build, and
 * nothing in the dev loop would have caught it.
 */
const unitFiles = import.meta.glob('../assets/units/*.png', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>;

/**
 * Upgrade and Doctrine emblems. Kept in a separate folder from the units for a
 * reason that is design, not filing: a card emblem must never contain a figure.
 * A unit and a trait are different kinds of thing — that is the whole of M2 —
 * and art that shows a soldier for both undoes it.
 */
const cardFiles = import.meta.glob('../assets/cards/*.png', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>;

const index = (files: Record<string, string>): Map<string, string> => {
  const map = new Map<string, string>();
  for (const [path, url] of Object.entries(files)) {
    const id = path.split('/').pop()?.replace(/\.png$/, '');
    if (id) map.set(id, url);
  }
  return map;
};

const byId = index(unitFiles);
const cardById = index(cardFiles);

/** The sprite URL for a unit, or null if it is still a placeholder. */
export function unitArtUrl(unitId: string): string | null {
  return byId.get(unitId) ?? null;
}

export function hasUnitArt(unitId: string): boolean {
  return byId.has(unitId);
}

/** The emblem for an Upgrade or Doctrine, or null while it is a placeholder. */
export function cardArtUrl(cardId: string): string | null {
  return cardById.get(cardId) ?? null;
}

/**
 * How far through the roster the art actually is. Surfaced in the dev overlay
 * so "we have art now" never gets said when four of twenty-five are done.
 */
export function artProgress(): {
  units: { done: number; total: number; missing: string[] };
  cards: { done: number; total: number; missing: string[] };
} {
  const cardIds = [...content.upgrades, ...content.doctrines].map((c) => c.id);
  const missingUnits = content.units.filter((u) => !byId.has(u.id)).map((u) => u.id);
  const missingCards = cardIds.filter((id) => !cardById.has(id));
  return {
    units: { done: content.units.length - missingUnits.length, total: content.units.length, missing: missingUnits },
    cards: { done: cardIds.length - missingCards.length, total: cardIds.length, missing: missingCards },
  };
}
