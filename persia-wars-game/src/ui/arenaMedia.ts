/**
 * Arena media lookup.
 *
 * One convention for all thirteen grounds, so new art needs no code change:
 *
 *   public/art/arenas/<slug>.mp4   intro motion, played before a battle
 *   public/art/arenas/<slug>.png   still, used in the lobby when there is no video
 *
 * Everything that consumes these probes for the file first and falls back to the
 * procedural placeholder, so a half-filled folder never breaks a screen.
 */

export function arenaVideo(slug: string): string {
  return `./art/arenas/${slug}.mp4`;
}

export function arenaStill(slug: string): string {
  return `./art/arenas/${slug}.png`;
}

/** Cache of which arena assets actually exist, so we probe each one once. */
const probed = new Map<string, Promise<boolean>>();

export function hasVideo(slug: string): Promise<boolean> {
  const key = `v:${slug}`;
  let p = probed.get(key);
  if (!p) {
    p = fetch(arenaVideo(slug), { method: 'HEAD' })
      .then((r) => r.ok && (r.headers.get('content-type') ?? '').includes('video'))
      .catch(() => false);
    probed.set(key, p);
  }
  return p;
}

export function hasStill(slug: string): Promise<boolean> {
  const key = `i:${slug}`;
  let p = probed.get(key);
  if (!p) {
    p = new Promise<boolean>((resolve) => {
      const img = new Image();
      img.onload = () => resolve(true);
      img.onerror = () => resolve(false);
      img.src = arenaStill(slug);
    });
    probed.set(key, p);
  }
  return p;
}
