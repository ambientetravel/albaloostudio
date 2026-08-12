import { useEffect, useState } from 'react';

/**
 * A framed character medallion with a title banner, as in the lobby mockup.
 *
 * Looks for `public/art/portraits/<id>.png` and falls back to a procedural
 * silhouette so an arena without commissioned portraits still reads as
 * deliberate. Placeholder art, like everything else visual.
 */
export function Portrait({
  id,
  name,
  title,
  side,
}: {
  id: string;
  name: string;
  title: string;
  side: 'left' | 'right';
}) {
  const [art, setArt] = useState<'probing' | 'yes' | 'no'>('probing');
  const src = `./art/portraits/${id}.png`;

  useEffect(() => {
    let cancelled = false;
    const img = new Image();
    img.onload = () => !cancelled && setArt('yes');
    img.onerror = () => !cancelled && setArt('no');
    img.src = src;
    return () => {
      cancelled = true;
    };
  }, [src]);

  return (
    <div className={`portrait portrait--${side}`}>
      <span className="portrait__ring">
        {art === 'yes' ? (
          <img src={src} alt="" />
        ) : (
          <svg viewBox="0 0 48 48" aria-hidden="true" className="portrait__ph">
            {/* Bearded profile in the Persepolis relief manner — a stand-in. */}
            <circle cx="24" cy="24" r="24" className="portrait__ph-bg" />
            <path
              d="M16 40 C16 30 18 24 24 22 C30 20 34 24 34 30 L34 40 Z"
              className="portrait__ph-body"
            />
            <circle cx="26" cy="17" r="7" className="portrait__ph-head" />
            <path d="M19 14 C19 9 33 9 33 14 L33 11 C33 7 19 7 19 11 Z" className="portrait__ph-crown" />
            <path d="M20 20 C20 27 26 29 30 27 L30 21 Z" className="portrait__ph-beard" />
          </svg>
        )}
      </span>
      <span className="portrait__banner">
        <strong>{name}</strong>
        <em>{title}</em>
      </span>
    </div>
  );
}
