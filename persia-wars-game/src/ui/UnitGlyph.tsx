import type { ReactElement } from 'react';
import type { Silhouette } from '../content/types';
import { cardArtUrl, unitArtUrl } from '../render/unitArt';

/**
 * A unit's picture, wherever the interface needs one.
 *
 * Commissioned art if there is any; otherwise the placeholder shape from
 * render/silhouettes.ts. Pass `unitId` for a unit or `cardId` for an Upgrade or
 * Doctrine emblem — callers that only know the silhouette keep working
 * unchanged, which is what lets art land a few pieces at a time.
 */
export function UnitGlyph({
  kind,
  size = 56,
  unitId,
  cardId,
}: {
  kind: Silhouette;
  size?: number;
  unitId?: string;
  cardId?: string;
}) {
  const art = unitId ? unitArtUrl(unitId) : cardId ? cardArtUrl(cardId) : null;
  if (art) {
    return (
      <img
        className="glyph glyph--art"
        src={art}
        width={size}
        height={size}
        alt=""
        aria-hidden="true"
        loading="lazy"
      />
    );
  }
  return (
    <svg
      className="glyph"
      width={size}
      height={size}
      viewBox="-16 -20 32 40"
      role="img"
      aria-hidden="true"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {shapes[kind]}
    </svg>
  );
}

const body = 'var(--glyph-body)';
const trim = 'var(--glyph-trim)';

const shapes: Record<Silhouette, ReactElement> = {
  shield: (
    <g>
      <path d="M0 -16 V14" stroke={trim} strokeWidth={2} />
      <rect x={-9} y={-13} width={18} height={26} rx={3} fill={body} stroke={trim} strokeWidth={2} />
      <path d="M-9 -4 H9 M-9 4 H9" stroke={trim} strokeWidth={1.4} />
    </g>
  ),
  spear: (
    <g>
      <path d="M7 -18 V15" stroke={trim} strokeWidth={2.4} />
      <path d="M7 -18 L4 -13 H10 Z" fill={trim} />
      <rect x={-8} y={-10} width={13} height={22} rx={4} fill={body} />
      <circle cx={-2} cy={-14} r={5} fill={body} />
      <rect x={-5} y={-19} width={6} height={4} fill={trim} />
    </g>
  ),
  bow: (
    <g>
      <rect x={-4} y={-10} width={12} height={22} rx={4} fill={body} />
      <circle cx={2} cy={-14} r={5} fill={body} />
      <path d="M0.9 -12 A12 12 0 0 0 0.9 10" stroke={trim} strokeWidth={2.4} />
      <path d="M-13 -12 V10" stroke={trim} strokeWidth={1.2} />
      <path d="M-13 -1 H4" stroke={trim} strokeWidth={2} />
    </g>
  ),
  horse: (
    <g>
      <ellipse cx={0} cy={4} rx={13} ry={6} fill={body} />
      <path d="M11 2 L15 -6 L12 -7 L8 -1 Z" fill={body} />
      <path d="M-9 9 L-10 15 M-3 9 L-4 15 M5 9 L6 15 M10 8 L11 15" stroke={body} strokeWidth={2} />
      <rect x={-4} y={-10} width={8} height={12} rx={3} fill={trim} />
      <circle cx={0} cy={-13} r={4} fill={trim} />
      <path d="M6 -18 L-2 0" stroke={trim} strokeWidth={2} />
    </g>
  ),
  'horse-bow': (
    <g>
      <ellipse cx={0} cy={4} rx={13} ry={6} fill={body} />
      <path d="M11 2 L15 -6 L12 -7 L8 -1 Z" fill={body} />
      <path d="M-9 9 L-10 15 M-3 9 L-4 15 M5 9 L6 15 M10 8 L11 15" stroke={body} strokeWidth={2} />
      <rect x={-4} y={-10} width={8} height={12} rx={3} fill={trim} />
      <circle cx={-1} cy={-13} r={4} fill={trim} />
      <path d="M-5.6 -16.7 A9 9 0 0 0 -5.6 0.7" stroke={trim} strokeWidth={2.2} />
    </g>
  ),
  chariot: (
    <g>
      <rect x={-6} y={-10} width={15} height={13} rx={2} fill={body} />
      <circle cx={-3} cy={7} r={8} stroke={trim} strokeWidth={2.4} />
      <path d="M-11 7 H5 M-3 -1 V15" stroke={trim} strokeWidth={1.2} />
      <path d="M5 7 L17 3 L16 8 Z" fill="var(--glyph-blade)" />
      <circle cx={2} cy={-14} r={4} fill={trim} />
    </g>
  ),
  elephant: (
    <g>
      <ellipse cx={-1} cy={2} rx={15} ry={10} fill={body} />
      <circle cx={11} cy={-1} r={7} fill={body} />
      <path d="M15 3 C20 8 18 14 14 15" stroke={body} strokeWidth={3.5} />
      <path d="M14 1 L21 4" stroke="var(--glyph-blade)" strokeWidth={2} />
      <path d="M-11 11 V16 M-3 12 V16 M5 12 V16" stroke={body} strokeWidth={4} />
      <rect x={-9} y={-14} width={14} height={9} rx={2} fill={trim} />
    </g>
  ),
  club: (
    <g>
      <rect x={-7} y={-9} width={13} height={21} rx={4} fill={body} />
      <circle cx={-1} cy={-14} r={5} fill={body} />
      <path d="M4 -2 L11 -14" stroke={trim} strokeWidth={2.5} />
      <rect x={8} y={-21} width={8} height={9} rx={3} fill={trim} />
      <circle cx={10} cy={-18} r={1.4} fill="var(--glyph-blade)" />
      <circle cx={14} cy={-16} r={1.4} fill="var(--glyph-blade)" />
    </g>
  ),
  lasso: (
    <g>
      <ellipse cx={-1} cy={5} rx={12} ry={5} fill={body} />
      <path d="M10 3 L14 -4 L11 -5 L7 0 Z" fill={body} />
      <path d="M-8 9 L-9 15 M4 9 L5 15" stroke={body} strokeWidth={2} />
      <rect x={-4} y={-9} width={8} height={11} rx={3} fill={trim} />
      <circle cx={0} cy={-12} r={4} fill={trim} />
      <ellipse cx={9} cy={-15} rx={7} ry={4} stroke={trim} strokeWidth={2} />
      <path d="M3 -11 L6 -13" stroke={trim} strokeWidth={1.6} />
    </g>
  ),
  camel: (
    <g>
      <ellipse cx={-2} cy={3} rx={13} ry={6} fill={body} />
      <ellipse cx={-6} cy={-3} rx={5} ry={4} fill={body} />
      <ellipse cx={2} cy={-3} rx={5} ry={4} fill={body} />
      <path d="M10 2 L13 -10" stroke={body} strokeWidth={3.5} />
      <circle cx={14} cy={-12} r={3.5} fill={body} />
      <path d="M-9 8 L-10 16 M-3 8 V16 M4 8 L5 16" stroke={body} strokeWidth={2} />
      <rect x={-4} y={-12} width={8} height={9} rx={3} fill={trim} />
      <path d="M0.9 -21.4 A8 8 0 0 0 0.9 -6.6" stroke={trim} strokeWidth={2} />
    </g>
  ),
};
