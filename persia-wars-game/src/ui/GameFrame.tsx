/**
 * The ornate border that wraps the whole game.
 *
 * Drawn procedurally rather than as a bitmap so it scales to any viewport
 * without a nine-slice, and so it recolours with the arena theme — the frame at
 * Babylon is the same carving in Babylon's metal.
 *
 * The motifs are read off the Anshan key art: a cuneiform tick strip along the
 * top and bottom, plain vertical rules down the sides, and a lion at each
 * corner. Placeholder work, like everything else visual — but the geometry is
 * what the commissioned frame should replace, not the idea.
 */

/** A single cuneiform-ish wedge cluster. Varied by index so the strip is not a stamp. */
function Wedges({ x, seed }: { x: number; seed: number }) {
  const kind = seed % 4;
  return (
    <g transform={`translate(${x} 0)`}>
      {kind === 0 && (
        <>
          <path d="M0 4 L5 0 L5 8 Z" />
          <path d="M7 0 L7 8 L9 8 L9 0 Z" />
        </>
      )}
      {kind === 1 && (
        <>
          <path d="M0 0 L0 8 L2 8 L2 0 Z" />
          <path d="M4 4 L9 1 L9 7 Z" />
        </>
      )}
      {kind === 2 && (
        <>
          <path d="M0 1 L6 4 L0 7 Z" />
          <path d="M8 0 L8 8 L10 8 L10 0 Z" />
        </>
      )}
      {kind === 3 && (
        <>
          <path d="M0 0 L0 8 L2 8 L2 0 Z" />
          <path d="M4 0 L4 8 L6 8 L6 0 Z" />
          <path d="M8 3 L12 5 L8 7 Z" />
        </>
      )}
    </g>
  );
}

function CuneiformStrip({ width, count = 34 }: { width: number; count?: number }) {
  const step = width / count;
  return (
    <g fill="currentColor" opacity="0.85">
      {Array.from({ length: count }, (_, i) => (
        <Wedges key={i} x={i * step + step * 0.2} seed={i * 7 + 3} />
      ))}
    </g>
  );
}

/** Corner lion, in profile — the Achaemenid guardian motif, heavily simplified. */
function Lion({ flip = false }: { flip?: boolean }) {
  return (
    <g
      fill="currentColor"
      transform={flip ? 'translate(34 0) scale(-1 1)' : undefined}
      opacity="0.95"
    >
      <path d="M4 18 L6 12 L11 10 L14 12 L20 12 L24 14 L28 13 L30 16 L27 18 L28 22 L25 22 L24 19 L14 19 L13 22 L10 22 L10 19 Z" />
      <circle cx="27" cy="12" r="3.4" />
      <path d="M30 10 L33 8 L32 12 Z" />
      <path d="M4 18 L1 21 L5 21 Z" />
    </g>
  );
}

export function GameFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="gameframe">
      <div className="gameframe__edge" aria-hidden="true">
        {/* Top strip */}
        <svg className="gameframe__strip gameframe__strip--top" viewBox="0 0 400 22" preserveAspectRatio="none">
          <rect width="400" height="22" className="gf-band" />
          <rect y="20" width="400" height="2" className="gf-rule" />
        </svg>
        <svg className="gameframe__glyphs gameframe__glyphs--top" viewBox="0 0 400 10" preserveAspectRatio="none">
          <CuneiformStrip width={400} />
        </svg>

        {/* Bottom strip */}
        <svg className="gameframe__strip gameframe__strip--bottom" viewBox="0 0 400 22" preserveAspectRatio="none">
          <rect width="400" height="22" className="gf-band" />
          <rect width="400" height="2" className="gf-rule" />
        </svg>
        <svg className="gameframe__glyphs gameframe__glyphs--bottom" viewBox="0 0 400 10" preserveAspectRatio="none">
          <CuneiformStrip width={400} />
        </svg>

        {/* Side rules */}
        <span className="gameframe__side gameframe__side--left" />
        <span className="gameframe__side gameframe__side--right" />

        {/* Corner lions — top only; the navigation sits in the bottom corners. */}
        <svg className="gameframe__lion gameframe__lion--tl" viewBox="0 0 34 24">
          <Lion />
        </svg>
        <svg className="gameframe__lion gameframe__lion--tr" viewBox="0 0 34 24">
          <Lion flip />
        </svg>
      </div>

      <div className="gameframe__inner">{children}</div>
    </div>
  );
}
