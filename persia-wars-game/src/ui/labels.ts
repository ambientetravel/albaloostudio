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

/**
 * One word for a unit, for places too small to hold its name.
 *
 * The Army Ledger draws squads at 26px, and at 26px six of the plain infantry
 * are the same picture — a brown standing figure ten pixels wide. No amount of
 * redrawing fixes that: the box is smaller than the difference. So identity
 * comes from a word instead, and the art goes back to being flavour.
 *
 * The word chosen is the DISTINGUISHING one, which is usually the people rather
 * than the weapon — 'Bactrian' and 'Colchian' separate where 'Archer' and
 * 'Shieldman' would not. Written out rather than sliced off the name so that
 * 'Shield-bearer' does not become 'Shield' next to 'Shieldman'.
 */
const SHORT_NAME: Record<string, string> = {
  'persian-archer': 'Persian',
  'spara-bearer': 'Spara',
  'median-spearman': 'Median',
  'persian-cavalry': 'Noble',
  'kissian-levy': 'Kissian',
  immortal: 'Immortal',
  'bactrian-archer': 'Bactrian',
  'saka-horse-archer': 'Saka',
  'caspian-skirmisher': 'Caspian',
  'assyrian-clubman': 'Assyrian',
  'paphlagonian-javelineer': 'Paphlag.',
  'sagartian-lassoer': 'Sagartian',
  'indian-cane-archer': 'Indian',
  'arabian-camel-rider': 'Camel',
  'thracian-peltast': 'Thracian',
  'lydian-hoplite': 'Lydian',
  'colchian-shieldman': 'Colchian',
  'armenian-lancer': 'Armenian',
  'egyptian-marine': 'Egyptian',
  'ethiopian-bowman': 'Ethiopian',
  'greek-mercenary-hoplite': 'Greek',
  'scythed-chariot': 'Chariot',
  'chorasmian-rider': 'Chorasm.',
  'war-elephant': 'Elephant',
  melophoros: 'Apple',
};

/**
 * Falls back to the first word of the name, so a unit added without an entry
 * here gets something readable rather than nothing. The test pins the table
 * against the roster, so the fallback should never actually be reached.
 */
export function shortName(unitId: string, fullName: string): string {
  return SHORT_NAME[unitId] ?? fullName.split(/[\s-]/)[0];
}

export const SHORT_NAMES = SHORT_NAME;
