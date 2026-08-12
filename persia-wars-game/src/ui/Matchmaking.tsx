import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { getArena } from '../content';
import { arenaForTrophies } from '../game/progression';
import { useGame } from '../state/store';
import { arenaVideo, hasVideo } from './arenaMedia';
import { Avatar } from './Avatar';

/**
 * Loading the battlefield and finding an opponent, over the arena's own footage.
 *
 * The clip runs to its natural end and then fades — it is the loading screen for
 * the ground you are about to fight on. Matchmaking happens underneath it, so
 * the wait is the establishing shot rather than a spinner.
 *
 * If no human turns up by the time the clip ends, the computer is offered. Until
 * there is a real player base that is the normal path, not an error state.
 */
const NO_VIDEO_MS = 8000;

export function Matchmaking() {
  const { profile, onlineCount, queuedCount, conn, trophies, cancelSearch, startAiMatch } = useGame();
  const arena = getArena(arenaForTrophies(trophies));
  const [media, setMedia] = useState<'probing' | 'video' | 'none'>('probing');
  const [elapsed, setElapsed] = useState(0);
  const [clipDone, setClipDone] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const offline = conn !== 'online';

  useEffect(() => {
    let cancelled = false;
    void hasVideo(arena.slug).then((ok) => {
      if (!cancelled) setMedia(ok ? 'video' : 'none');
    });
    return () => {
      cancelled = true;
    };
  }, [arena.slug]);

  // With no clip there is nothing to time against, so fall back to a plain wait.
  useEffect(() => {
    if (media !== 'none') return;
    const started = Date.now();
    const id = setInterval(() => {
      const ms = Date.now() - started;
      setElapsed(ms);
      if (ms >= NO_VIDEO_MS) setClipDone(true);
    }, 120);
    return () => clearInterval(id);
  }, [media]);

  const gaveUp = offline || clipDone;
  const frac = media === 'video' ? 0 : Math.min(1, elapsed / NO_VIDEO_MS);

  return (
    <div className="screen matchmaking">
      {media === 'video' && (
        <motion.div
          className="matchmaking__film"
          // The clip holds the screen, then hands it over.
          animate={{ opacity: clipDone ? 0 : 1 }}
          transition={{ duration: 0.9, ease: 'easeInOut' }}
        >
          <video
            ref={videoRef}
            src={arenaVideo(arena.slug)}
            autoPlay
            muted
            playsInline
            preload="auto"
            onEnded={() => setClipDone(true)}
            onError={() => setMedia('none')}
          />
          <span className="matchmaking__scrim" />
        </motion.div>
      )}

      <div className="matchmaking__body">
        <motion.div
          className="matchmaking__title"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.6 }}
        >
          <span className="arena-intro__rank">Arena {arena.id}</span>
          <h2>{gaveUp ? 'No one else is searching' : arena.name}</h2>
          <p className="muted">
            {offline
              ? 'The server is unreachable right now.'
              : gaveUp
                ? 'Take on the computer, or keep waiting.'
                : `Loading the battlefield · ${arena.year}`}
          </p>
        </motion.div>

        <div className="lobby__vs">
          <div className="lobby__slot">
            <Avatar index={profile?.avatar ?? 0} size={70} />
            <span>{profile?.name ?? 'Player'}</span>
          </div>
          <span className="lobby__x">VS</span>
          <div className="lobby__slot is-waiting">
            <motion.span
              className="lobby__spinner"
              aria-hidden="true"
              animate={{ rotate: 360 }}
              transition={{ duration: 3.2, repeat: Infinity, ease: 'linear' }}
            />
            <span>{gaveUp ? 'Nobody yet' : 'Finding an opponent…'}</span>
          </div>
        </div>

        {media === 'none' && !offline && (
          <div className="hunt-bar" aria-hidden="true">
            <span className="hunt-bar__fill" style={{ width: `${Math.round(frac * 100)}%` }} />
          </div>
        )}

        <p className="lobby__counts">
          {offline ? 'Offline' : `${onlineCount} online · ${queuedCount} searching`}
        </p>

        <div className="matchmaking__actions">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={gaveUp ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
            transition={{ duration: 0.4 }}
            style={{ pointerEvents: gaveUp ? 'auto' : 'none' }}
          >
            <button className="btn btn--gold" type="button" onClick={() => startAiMatch()}>
              <span className="btn__label">PLAY THE COMPUTER</span>
              <span className="btn__hint">A match starts right now</span>
            </button>
          </motion.div>

          <button className="btn btn--ghost" type="button" onClick={cancelSearch}>
            {gaveUp ? 'Back to lobby' : 'Cancel'}
          </button>
        </div>
      </div>
    </div>
  );
}
