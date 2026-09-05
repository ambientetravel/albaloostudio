import type { Unit, UnitClass } from '../content/types';

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

/**
 * The line under a unit's name.
 *
 * Since the name became a person ('Zarina'), the contingent is where the
 * history attaches — dropping it for the bare class loses 'Saka Horse-archer'
 * entirely, which is the fact, and keeps only the individual, which is the
 * invention. Four screens did exactly that before this was pulled into one
 * place, so it lives here and nowhere else.
 *
 * The class is appended only when the contingent does not already say it. The
 * counter system runs on class, so it cannot simply be dropped: 'Immortal'
 * gives no hint that it is heavy infantry.
 */
export function unitSubtitle(unit: Unit): string {
  const cls = CLASS_LABEL[unit.class];
  return unit.contingent.toLowerCase().includes(cls.toLowerCase())
    ? unit.contingent
    : `${unit.contingent} \u00b7 ${cls}`;
}
