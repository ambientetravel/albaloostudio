import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import type { Arena } from '../content/types';
import { arenaStill, hasStill } from './arenaMedia';
import { themeFor } from './arenaTheme';

/**
 * The lobby's window onto the arena you are ranked in.
 *
 * A still, not the intro clip — the clip is the battlefield's loading screen and
 * belongs on the matchmaking screen, where it plays to the end. Here we want a
 * panel that sits calmly behind the BATTLE button, painted in the arena's own
 * colours so the lobby looks like Anshan when you are in Anshan.
 *
 * Uses `public/art/arenas/<slug>.png` if it is there; otherwise draws a themed
 * skyline so every arena resolves to something deliberate.
 */
export function ArenaStage({ arena }: { arena: Arena }) {
  const [still, setStill] = useState<'probing' | 'yes' | 'no'>('probing');
  const theme = themeFor(arena.slug);

  useEffect(() => {
    let cancelled = false;
    setStill('probing');
    void hasStill(arena.slug).then((ok) => {
      if (!cancelled) setStill(ok ? 'yes' : 'no');
    });
    return () => {
      cancelled = true;
    };
  }, [arena.slug]);

  return (
    <div className={`arena-stage${still === 'yes' ? ' has-media' : ''}`}>
      <div className="arena-stage__art" aria-hidden="true">
        {still === 'yes' ? (
          <motion.img
            key={arena.slug}
            className="arena-stage__media"
            src={arenaStill(arena.slug)}
            alt=""
            initial={{ opacity: 0, scale: 1.05 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1 }}
          />
        ) : (
          <ThemedSkyline slug={arena.slug} accent={theme.accent} />
        )}
        {still === 'yes' && <span className="arena-stage__scrim" />}
      </div>

      {/* The lore lives on the scroll below; repeating it here just doubled it. */}
      <span className="arena-stage__year">{arena.year}</span>
    </div>
  );
}

/**
 * A placeholder skyline in the arena's palette. Deliberately simple — its job
 * is to carry the arena's colour, not to compete with the commissioned art that
 * will replace it.
 */
function ThemedSkyline({ slug, accent }: { slug: string; accent: string }) {
  const theme = themeFor(slug);
  return (
    <svg className="arena-stage__skyline" viewBox="0 0 600 200" preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id={`sky-${slug}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={theme.bgTop} />
          <stop offset="1" stopColor={theme.bgMid} />
        </linearGradient>
      </defs>
      <rect width="600" height="200" fill={`url(#sky-${slug})`} />
      <ellipse cx="300" cy="150" rx="230" ry="80" fill={accent} opacity="0.16" />
      <path
        d="M-20 128 L70 92 L130 118 L210 80 L280 112 L360 84 L440 116 L520 88 L620 124 L620 210 L-20 210 Z"
        fill={theme.surface2}
      />
      <path
        d="M-20 150 L90 122 L170 146 L260 118 L360 148 L470 120 L620 150 L620 210 L-20 210 Z"
        fill={theme.surface3}
      />
      <rect x="-20" y="168" width="640" height="44" fill={theme.rim} opacity="0.55" />
      <rect x="-20" y="166" width="640" height="3" fill={accent} opacity="0.7" />
      <g opacity="0.9">
        <rect x="252" y="132" width="96" height="36" fill={theme.surface} />
        <polygon points="276,132 324,132 330,116 270,116" fill={theme.surface} />
        <rect x="294" y="100" width="12" height="18" fill={accent} />
      </g>
    </svg>
  );
}
