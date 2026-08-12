import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { getArena } from '../content';
import { arenaForTrophies } from '../game/progression';
import { useGame } from '../state/store';
import { arenaStill, hasStill } from './arenaMedia';

/**
 * The arena, enlarged behind the whole interface.
 *
 * The panel in the lobby stays a sharp window onto the ground; this is the same
 * scene blown up and pushed back, so the glass panels above have something to
 * refract. Blurred and scrimmed hard on purpose — the job is depth behind the
 * UI, not a second thing to look at, and every panel above it has to keep
 * carrying stone-white text at the same contrast it had over a flat gradient.
 *
 * Only on the meta screens. A match needs the battlefield legible, so draft,
 * battle and result keep the plain themed gradient.
 */
export function ArenaBackdrop() {
  const { trophies, matchState, screen } = useGame();
  const arena = getArena(screen === 'battle' && matchState ? matchState.arena : arenaForTrophies(trophies));
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setReady(false);
    void hasStill(arena.slug).then((ok) => {
      if (!cancelled) setReady(ok);
    });
    return () => {
      cancelled = true;
    };
  }, [arena.slug]);

  if (!ready) return null;

  return (
    <div className="backdrop" aria-hidden="true">
      <motion.img
        key={arena.slug}
        src={arenaStill(arena.slug)}
        alt=""
        initial={{ opacity: 0, scale: 1.14 }}
        animate={{ opacity: 1, scale: 1.08 }}
        transition={{ opacity: { duration: 1.1 }, scale: { duration: 18, ease: 'easeOut' } }}
      />
      <span className="backdrop__scrim" />
    </div>
  );
}
