import { useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { SplashArt } from './SplashArt';

/** Drop the commissioned key art here and the splash uses it automatically. */
const KEY_ART = './art/anshan-splash.png';

const TITLE = 'PERSIA AT WAR';

interface Props {
  onDone: () => void;
  /** Minimum time on screen, so it never flashes past on a fast load. */
  minMs?: number;
}

/** `?boot=12000` holds the splash open, for reviewing the animation. */
function bootOverride(): number | null {
  if (typeof location === 'undefined') return null;
  const raw = new URLSearchParams(location.search).get('boot');
  const n = raw ? Number(raw) : NaN;
  return Number.isFinite(n) && n > 0 ? n : null;
}

export function LoadingScreen({ onDone, minMs = 2600 }: Props) {
  const [art, setArt] = useState<'pending' | 'image' | 'fallback'>('pending');
  const [progress, setProgress] = useState(0);
  const reduce = useReducedMotion();
  const hold = bootOverride() ?? minMs;

  // Use the real key art if it is there, the layered placeholder if it is not.
  useEffect(() => {
    const img = new Image();
    img.onload = () => setArt('image');
    img.onerror = () => setArt('fallback');
    img.src = KEY_ART;
  }, []);

  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => {
      const frac = Math.min(1, (Date.now() - started) / hold);
      setProgress(frac);
      if (frac >= 1) {
        clearInterval(id);
        onDone();
      }
    }, 60);
    return () => clearInterval(id);
  }, [hold, onDone]);

  return (
    <motion.div
      className="loading"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.5 } }}
    >
      <div className="loading__art">
        {art === 'image' ? (
          // A single flat image cannot parallax, so it gets a slow push-in instead.
          <motion.img
            src={KEY_ART}
            alt=""
            initial={{ scale: reduce ? 1 : 1.12, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ scale: { duration: 14, ease: 'easeOut' }, opacity: { duration: 1.1 } }}
          />
        ) : art === 'fallback' ? (
          <SplashArt />
        ) : null}
        <div className="loading__vignette" />
      </div>

      <div className="loading__plate">
        {/*
          Words are kept whole. Letters animate individually, but a bare run of
          inline-blocks will happily break in the middle of "WAR".

          The gold sweep is a brightness flare travelling letter to letter rather
          than an overlay bar — an overlay has to re-derive the line wrapping to
          line up with the glyphs, and shows as a lit rectangle when it does not.
        */}
        <h1 className="loading__title" aria-label={TITLE}>
          {TITLE.split(' ').map((word, w, words) => {
            const before = words.slice(0, w).reduce((n, x) => n + x.length + 1, 0);
            return (
              <span className="loading__word" key={w} aria-hidden="true">
                {word.split('').map((ch, c) => {
                  const i = before + c;
                  const inAt = 0.25 + i * 0.045;
                  return (
                    <motion.span
                      key={c}
                      initial={{ opacity: 0, y: reduce ? 0 : 26, rotateX: reduce ? 0 : -70 }}
                      animate={{
                        opacity: 1,
                        y: 0,
                        rotateX: 0,
                        filter: reduce
                          ? 'brightness(1)'
                          : ['brightness(1)', 'brightness(1.85)', 'brightness(1)'],
                      }}
                      transition={{
                        opacity: { delay: inAt, duration: 0.45 },
                        y: { delay: inAt, duration: 0.5, ease: [0.2, 1.3, 0.5, 1] },
                        rotateX: { delay: inAt, duration: 0.5 },
                        filter: { delay: 1.15 + i * 0.04, duration: 0.8, times: [0, 0.35, 1] },
                      }}
                    >
                      {ch}
                    </motion.span>
                  );
                })}
              </span>
            );
          })}
        </h1>

        <motion.p
          className="loading__sub"
          initial={{ opacity: 0, y: reduce ? 0 : 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.0, duration: 0.6 }}
        >
          Heart of Elam, cradle of kings
        </motion.p>

        <motion.div
          className="loading__bar"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.3, duration: 0.4 }}
        >
          <span className="loading__fill" style={{ width: `${Math.round(progress * 100)}%` }} />
        </motion.div>

        <motion.p
          className="loading__note"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.6, duration: 0.5 }}
        >
          {art === 'image' ? 'Anshan · 559 BCE' : 'Anshan · 559 BCE · placeholder art'}
        </motion.p>
      </div>
    </motion.div>
  );
}
