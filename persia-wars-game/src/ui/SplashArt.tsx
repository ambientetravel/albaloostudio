import { motion } from 'framer-motion';

/**
 * PLACEHOLDER SPLASH — a layered Anshan in the Achaemenid palette.
 *
 * Built as separate SVG layers on purpose: each one drifts at its own speed so
 * the scene has parallax depth. When the commissioned key art is dropped in at
 * `public/art/anshan-splash.png` the LoadingScreen uses that instead, with a
 * slow push-in — a single flat image cannot parallax.
 *
 * The viewBox is deliberately taller than the art needs (1400 × 1000). The
 * splash is cropped with `slice` to fill any viewport, and the extra sky and
 * foreground are the crop margin — without them a portrait phone zooms straight
 * into the city walls.
 */
export function SplashArt() {
  return (
    <div className="splash-art" aria-hidden="true">
      <svg viewBox="0 0 1400 1000" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#0d1a33" />
            <stop offset="0.42" stopColor="#1f3b6e" />
            <stop offset="0.72" stopColor="#35609f" />
            <stop offset="1" stopColor="#a58063" />
          </linearGradient>
          <radialGradient id="sun" cx="0.5" cy="1" r="0.8">
            <stop offset="0" stopColor="#eec95f" stopOpacity="0.6" />
            <stop offset="1" stopColor="#eec95f" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="far" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#4a77b8" />
            <stop offset="1" stopColor="#2a4d8c" />
          </linearGradient>
          <linearGradient id="mid" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#a58063" />
            <stop offset="1" stopColor="#7a5b45" />
          </linearGradient>
          <linearGradient id="near" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#8c6a50" />
            <stop offset="1" stopColor="#543d2e" />
          </linearGradient>
        </defs>

        <rect width="1400" height="1000" fill="url(#sky)" />
        <ellipse cx="700" cy="620" rx="640" ry="300" fill="url(#sun)" />

        {/* Far ridges — barely move */}
        <motion.g
          initial={{ x: -14 }}
          animate={{ x: 14 }}
          transition={{ duration: 26, repeat: Infinity, repeatType: 'reverse', ease: 'easeInOut' }}
        >
          <path
            d="M-40 560 L150 452 L280 522 L420 418 L560 508 L700 442 L860 522 L1000 438 L1160 518 L1300 458 L1440 548 L1440 620 L-40 620 Z"
            fill="url(#far)"
            opacity="0.9"
          />
        </motion.g>

        {/* Mid ridges */}
        <motion.g
          initial={{ x: 18 }}
          animate={{ x: -18 }}
          transition={{ duration: 20, repeat: Infinity, repeatType: 'reverse', ease: 'easeInOut' }}
        >
          <path
            d="M-40 622 L180 536 L340 604 L520 524 L700 598 L900 530 L1080 604 L1260 540 L1440 618 L1440 672 L-40 672 Z"
            fill="url(#mid)"
          />
        </motion.g>

        {/* The plain the city stands on */}
        <rect x="-40" y="660" width="1480" height="400" fill="url(#near)" />
        <rect x="-40" y="660" width="1480" height="6" fill="#eec95f" opacity="0.55" />

        {/* River */}
        <path
          d="M180 1000 C 330 900, 430 840, 520 760 C 570 716, 600 690, 630 668 L700 668 C 650 700, 604 748, 566 806 C 508 894, 430 950, 360 1000 Z"
          fill="#2e9c9a"
          opacity="0.5"
        />

        {/* The city */}
        <motion.g
          initial={{ y: 5 }}
          animate={{ y: -5 }}
          transition={{ duration: 14, repeat: Infinity, repeatType: 'reverse', ease: 'easeInOut' }}
        >
          <rect x="470" y="672" width="480" height="118" fill="#a58063" />
          <rect x="470" y="672" width="480" height="8" fill="#eec95f" opacity="0.5" />
          {[...Array(21)].map((_, i) => (
            <rect key={i} x={474 + i * 23} y="664" width="12" height="10" fill="#a58063" />
          ))}

          {/* stepped temple platform */}
          <polygon points="676,672 744,672 754,698 666,698" fill="#c2a184" />
          <polygon points="666,698 754,698 764,724 656,724" fill="#b3906f" />
          <polygon points="656,724 764,724 774,752 646,752" fill="#a58063" />
          <rect x="702" y="636" width="16" height="38" fill="#c2a184" />
          <rect x="697" y="629" width="26" height="10" fill="#eec95f" opacity="0.85" />

          {/* low blocks */}
          {[
            [488, 730, 52, 40],
            [548, 740, 40, 30],
            [598, 726, 44, 44],
            [800, 732, 50, 38],
            [858, 740, 38, 30],
            [900, 728, 40, 42],
          ].map(([x, y, w, h], i) => (
            <rect key={i} x={x} y={y} width={w} height={h} fill={i % 2 ? '#b3906f' : '#a58063'} />
          ))}

          {/* gate */}
          <rect x="694" y="756" width="34" height="34" fill="#543d2e" />
          <rect x="690" y="749" width="42" height="9" fill="#eec95f" opacity="0.7" />
        </motion.g>

        {/* Foreground dunes — move most */}
        <motion.g
          initial={{ x: -26 }}
          animate={{ x: 26 }}
          transition={{ duration: 16, repeat: Infinity, repeatType: 'reverse', ease: 'easeInOut' }}
        >
          <path
            d="M-60 880 C 220 826, 440 880, 700 850 C 960 820, 1200 878, 1460 840 L1460 1040 L-60 1040 Z"
            fill="#543d2e"
          />
        </motion.g>
      </svg>
    </div>
  );
}
