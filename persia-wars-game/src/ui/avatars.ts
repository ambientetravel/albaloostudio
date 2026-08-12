import type { Silhouette } from '../content/types';

/**
 * PLACEHOLDER AVATARS — built from the same silhouettes as the units, recoloured.
 * Cheap, on-theme, and replaced by commissioned character art later.
 */
export interface Avatar {
  silhouette: Silhouette;
  body: string;
  ring: string;
}

export const AVATARS: Avatar[] = [
  { silhouette: 'spear', body: '#ff5a4d', ring: '#ffd45e' },
  { silhouette: 'bow', body: '#3fa9f5', ring: '#9fe8ff' },
  { silhouette: 'horse', body: '#6bd44a', ring: '#e6ff9c' },
  { silhouette: 'shield', body: '#ff5ca8', ring: '#ffd0e8' },
  { silhouette: 'horse-bow', body: '#ffa63d', ring: '#fff0b8' },
  { silhouette: 'chariot', body: '#45d9e8', ring: '#d6fbff' },
  { silhouette: 'elephant', body: '#b07bff', ring: '#ecd9ff' },
  { silhouette: 'spear', body: '#f5f0ff', ring: '#8a5fd8' },
];

export function avatarAt(index: number): Avatar {
  return AVATARS[((index % AVATARS.length) + AVATARS.length) % AVATARS.length];
}
