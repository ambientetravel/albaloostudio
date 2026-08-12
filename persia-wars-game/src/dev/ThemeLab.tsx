import { useState } from 'react';
import { content } from '../content';
import { ACHAEMENID_PALETTE } from '../ui/palette';
import { arenaVideo, arenaStill } from '../ui/arenaMedia';
import { applyArenaTheme, themeFor, type ArenaTheme } from '../ui/arenaTheme';

/**
 * DEV TOOL — reachable at `?themelab`, never linked from the game.
 *
 * Derives an arena theme from that arena's own footage instead of guessing it.
 * Samples frames across the clip, pulls out a sky / mid / ground band and the
 * most saturated colour, then snaps everything toward the six Achaemenid hues so
 * a derived theme cannot drift off-palette. Prints a block ready to paste into
 * `src/ui/arenaTheme.ts`.
 *
 * The snapping is the important part: sampled colour alone would give thirteen
 * unrelated schemes. Pulling each sample toward its nearest palette hue keeps
 * the whole ladder recognisably the same game.
 */

const SAMPLES = 7;
/** How far a sampled colour is dragged toward its nearest palette hue. */
const SNAP = 0.45;

type RGB = [number, number, number];

const hex = ([r, g, b]: RGB): string =>
  '#' + [r, g, b].map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0')).join('');

function parseHex(h: string): RGB {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

const mix = (a: RGB, b: RGB, t: number): RGB => [
  a[0] + (b[0] - a[0]) * t,
  a[1] + (b[1] - a[1]) * t,
  a[2] + (b[2] - a[2]) * t,
];

const scale = (c: RGB, k: number): RGB => [c[0] * k, c[1] * k, c[2] * k];
const lum = ([r, g, b]: RGB): number => 0.2126 * r + 0.7152 * g + 0.0722 * b;
const sat = ([r, g, b]: RGB): number => {
  const mx = Math.max(r, g, b);
  const mn = Math.min(r, g, b);
  return mx === 0 ? 0 : (mx - mn) / mx;
};

/** Distance in hue-ish space, ignoring brightness so a dark sand still matches sand. */
function hueDistance(a: RGB, b: RGB): number {
  const na = lum(a) || 1;
  const nb = lum(b) || 1;
  const x = scale(a, 1 / na);
  const y = scale(b, 1 / nb);
  return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]);
}

const PALETTE_RGB = ACHAEMENID_PALETTE.map((p) => ({ name: p.name, rgb: parseHex(p.hex) }));

function snapToPalette(c: RGB): RGB {
  let best = PALETTE_RGB[0];
  let bestD = Infinity;
  for (const p of PALETTE_RGB) {
    const d = hueDistance(c, p.rgb);
    if (d < bestD) {
      bestD = d;
      best = p;
    }
  }
  // Keep the sample's own brightness, borrow the palette's hue.
  const target = scale(best.rgb, (lum(c) || 1) / (lum(best.rgb) || 1));
  return mix(c, target, SNAP);
}

interface Sampled {
  sky: RGB;
  mid: RGB;
  ground: RGB;
  accent: RGB;
}

async function sampleVideo(src: string): Promise<Sampled> {
  const video = document.createElement('video');
  video.src = src;
  video.muted = true;
  video.crossOrigin = 'anonymous';
  await new Promise<void>((res, rej) => {
    video.onloadedmetadata = () => res();
    video.onerror = () => rej(new Error(`cannot load ${src}`));
  });

  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!;

  const bands: { top: RGB[]; mid: RGB[]; low: RGB[] } = { top: [], mid: [], low: [] };
  let accent: RGB = [0, 0, 0];
  let accentScore = -1;

  for (let i = 0; i < SAMPLES; i++) {
    const t = ((i + 0.5) / SAMPLES) * video.duration;
    await new Promise<void>((res) => {
      video.onseeked = () => res();
      video.currentTime = t;
    });
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);

    for (let y = 0; y < canvas.height; y++) {
      for (let x = 0; x < canvas.width; x++) {
        const o = (y * canvas.width + x) * 4;
        const c: RGB = [data[o], data[o + 1], data[o + 2]];
        // The sky band is deliberately narrow. A full top third of a city shot
        // is mostly rooftops, which drags the sky colour down into the walls.
        const band =
          y < canvas.height * 0.16 ? 'top' : y < canvas.height * 0.68 ? 'mid' : 'low';
        bands[band].push(c);
        // The accent is the most vivid pixel that is not nearly black or white.
        const s = sat(c) * Math.min(1, lum(c) / 90);
        if (s > accentScore && lum(c) > 40 && lum(c) < 225) {
          accentScore = s;
          accent = c;
        }
      }
    }
  }

  const mean = (list: RGB[]): RGB =>
    list.length === 0
      ? [0, 0, 0]
      : (list.reduce<RGB>((acc, c) => [acc[0] + c[0], acc[1] + c[1], acc[2] + c[2]], [0, 0, 0]).map((v) =>
          Math.round(v / list.length),
        ) as RGB);

  return { sky: mean(bands.top), mid: mean(bands.mid), ground: mean(bands.low), accent };
}

function themeFromSample(s: Sampled): ArenaTheme {
  const sky = snapToPalette(s.sky);
  const mid = snapToPalette(s.mid);
  const ground = snapToPalette(s.ground);
  const accent = snapToPalette(s.accent);

  // Panels have to carry stone-white text at every arena, so they are pinned to
  // a brightness band rather than taken straight from the frame.
  const base = mid;
  const toward = (k: number): RGB => scale(base, (k * 255) / Math.max(1, lum(base)));

  return {
    bgTop: hex(scale(sky, Math.min(1.15, 150 / Math.max(1, lum(sky))))),
    bgMid: hex(scale(mid, Math.min(1.1, 110 / Math.max(1, lum(mid))))),
    bgDeep: hex(scale(ground, Math.min(1, 58 / Math.max(1, lum(ground))))),
    surface: hex(toward(0.28)),
    surface2: hex(toward(0.2)),
    surface3: hex(toward(0.14)),
    rim: hex(toward(0.06)),
    rimLight: hex(toward(0.7)),
    accent: hex(scale(accent, Math.min(1.4, 175 / Math.max(1, lum(accent))))),
  };
}

export default function ThemeLab() {
  const [busy, setBusy] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, ArenaTheme>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  const run = async (slug: string): Promise<void> => {
    setBusy(slug);
    try {
      const s = await sampleVideo(arenaVideo(slug));
      const theme = themeFromSample(s);
      setResults((r) => ({ ...r, [slug]: theme }));
      setErrors((e) => {
        const next = { ...e };
        delete next[slug];
        return next;
      });
      applyArenaTheme(slug);
    } catch (err) {
      setErrors((e) => ({ ...e, [slug]: err instanceof Error ? err.message : String(err) }));
    } finally {
      setBusy(null);
    }
  };

  const runAll = async (): Promise<void> => {
    for (const a of content.arenas) await run(a.slug);
  };

  const block = (slug: string, t: ArenaTheme): string =>
    `  '${slug}': {\n` +
    `    bgTop: '${t.bgTop}', bgMid: '${t.bgMid}', bgDeep: '${t.bgDeep}',\n` +
    `    surface: '${t.surface}', surface2: '${t.surface2}', surface3: '${t.surface3}',\n` +
    `    rim: '${t.rim}', rimLight: '${t.rimLight}', accent: '${t.accent}',\n` +
    `  },`;

  const all = content.arenas
    .filter((a) => results[a.slug])
    .map((a) => block(a.slug, results[a.slug]))
    .join('\n');

  return (
    <div className="screen themelab">
      <h2>Theme lab</h2>
      <p className="muted">
        Dev tool. Samples each arena&apos;s clip and derives a theme snapped to the Achaemenid palette. Paste the
        output into <code>src/ui/arenaTheme.ts</code>. Not linked from the game.
      </p>

      <div className="row">
        <button className="btn btn--gold" type="button" onClick={runAll} disabled={busy !== null}>
          {busy ? `Sampling ${busy}…` : 'Sample every arena with a clip'}
        </button>
      </div>

      <div className="themelab__grid">
        {content.arenas.map((a) => {
          const t = results[a.slug] ?? themeFor(a.slug);
          const derived = Boolean(results[a.slug]);
          return (
            <div key={a.slug} className="themelab__row">
              <button
                className="btn btn--teal btn--price"
                type="button"
                onClick={() => run(a.slug)}
                disabled={busy !== null}
              >
                {a.id}. {a.name}
              </button>
              <span className="themelab__swatches">
                {[t.bgTop, t.bgMid, t.bgDeep, t.surface, t.rim, t.accent].map((c, i) => (
                  <i key={i} style={{ background: c }} title={c} />
                ))}
              </span>
              <span className="themelab__state">
                {errors[a.slug] ? 'no clip' : derived ? 'derived' : 'current'}
              </span>
              <img className="themelab__still" src={arenaStill(a.slug)} alt="" onError={(e) => e.currentTarget.remove()} />
            </div>
          );
        })}
      </div>

      {all && (
        <>
          <h3>Paste into arenaTheme.ts</h3>
          <textarea className="themelab__out" readOnly value={all} rows={Math.min(30, all.split('\n').length + 1)} />
        </>
      )}
    </div>
  );
}
