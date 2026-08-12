import type { UnitClass } from '../content/types';

export const CLASS_LABEL: Record<UnitClass, string> = {
  'heavy-infantry': 'Heavy infantry',
  infantry: 'Infantry',
  archer: 'Archer',
  cavalry: 'Cavalry',
  'horse-archer': 'Horse-archer',
  chariot: 'Chariot',
  elephant: 'Elephant',
  musketeer: 'Musketeer',
  artillery: 'Artillery',
};

export function listClasses(classes: UnitClass[]): string {
  return classes.map((c) => CLASS_LABEL[c]).join(', ') || '—';
}
