import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import type { Arena } from '../content/types';
import { arenaVideo, hasVideo } from './arenaMedia';

/**
 * The establishing shot before a battle session.
 *
 * Plays `public/art/arenas/<slug>.mp4` if it exists, over a title card naming
 * the ground and its date. If there is no video for that arena yet, the card
 * still plays on its own for a beat — so the twelve grounds without footage feel
 * deliberate rather than broken.
 */
const CARD_ONLY_MS = 1900;
/** Nobody should sit through the same ten seconds every match. */
const MAX_MS = 10_500;

export function ArenaIntro({ arena, onDone }: { arena: Arena; onDone: () => void }) {
  const [mode, setMode] = useState<'probing' | 'video' | 'card'>('probing');
  const videoRef = useRef<HTMLVideoElement>(null);
  const doneRef = useRef(false);

  const finish = (): void => {
    if (doneRef.current) return;
    doneRef.current = true;
    onDone();
  };

  useEffect(() => {
    let cancelled = false;
    void hasVideo(arena.slug).then((ok) => {
      if (!cancelled) setMode(ok ? 'video' : 'card');
    });
    return () => {
      cancelled = true;
    };
  }, [arena.slug]);

  useEffect(() => {
    if (mode === 'probing') return;
    // A hard ceiling regardless of the clip's own length, and the only timer
    // when there is no clip at all.
    const limit = mode === 'video' ? MAX_MS : CARD_ONLY_MS;
    const id = setTimeout(finish, limit);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  return (
    <motion.div
      className="arena-intro"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.45 } }}
    >
      {mode === 'video' && (
        <video
          ref={videoRef}
          className="arena-intro__video"
          src={arenaVideo(arena.slug)}
          autoPlay
          muted
          playsInline
          preload="auto"
          onEnded={finish}
          // A missing or unplayable file must not strand the player mid-match.
          onError={() => setMode('card')}
        />
      )}

      <div className="arena-intro__scrim" />

      <motion.div
        className="arena-intro__card"
        initial={{ opacity: 0, y: 22 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25, duration: 0.6, ease: [0.2, 1.1, 0.4, 1] }}
      >
        <span className="arena-intro__rank">Arena {arena.id}</span>
        <h2>{arena.name}</h2>
        <p className="arena-intro__sub">{arena.subtitle}</p>
        <p className="arena-intro__meta">
          {arena.year} · {arena.where}
        </p>
      </motion.div>

      <button className="arena-intro__skip" type="button" onClick={finish}>
        Skip
      </button>
    </motion.div>
  );
}
