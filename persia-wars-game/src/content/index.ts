import type {
  Arena,
  Battle,
  CapitalPiece,
  Commander,
  Confidence,
  ContentDb,
  BookDossier,
  Doctrine,
  DossierDb,
  Era,
  MissionDossier,
  King,
  Mission,
  MissionReward,
  Spell,
  Unit,
  Upgrade,
} from './types';
import erasRaw from './data/eras.json';
import arenasRaw from './data/arenas.json';
import unitsRaw from './data/units.json';
import upgradesRaw from './data/upgrades.json';
import doctrinesRaw from './data/doctrines.json';
import commandersRaw from './data/commanders.json';
import missionsRaw from './data/missions.json';
import capitalRaw from './data/capital.json';
import dossiersRaw from './data/dossiers.json';
import spellsRaw from './data/spells.json';
import kingsRaw from './data/kings.json';
import battlesRaw from './data/battles.json';

export const content: ContentDb = {
  eras: erasRaw as Era[],
  arenas: arenasRaw as Arena[],
  units: unitsRaw as Unit[],
  upgrades: upgradesRaw as Upgrade[],
  doctrines: doctrinesRaw as Doctrine[],
  commanders: commandersRaw as Commander[],
  missions: missionsRaw as Mission[],
  capital: capitalRaw as CapitalPiece[],
  spells: spellsRaw as Spell[],
  kings: kingsRaw as King[],
  battles: battlesRaw as Battle[],
};

export const upgradesById = new Map(content.upgrades.map((u) => [u.id, u]));
export const doctrinesById = new Map(content.doctrines.map((d) => [d.id, d]));
export const commandersById = new Map(content.commanders.map((c) => [c.id, c]));
export const missionsById = new Map(content.missions.map((m) => [m.id, m]));

/** The Historical Battle Dossiers, v0.1 §14. Keyed by mission id. */
export const dossiers = dossiersRaw as unknown as DossierDb;

export function dossierFor(missionId: string): MissionDossier | null {
  return dossiers.missions[missionId] ?? null;
}
export const capitalById = new Map(content.capital.map((c) => [c.id, c]));

export function getUpgrade(id: string): Upgrade {
  const u = upgradesById.get(id);
  if (!u) throw new Error(`Unknown upgrade: ${id}`);
  return u;
}
export function getDoctrine(id: string): Doctrine {
  const d = doctrinesById.get(id);
  if (!d) throw new Error(`Unknown doctrine: ${id}`);
  return d;
}
export function getCommander(id: string): Commander {
  const c = commandersById.get(id);
  if (!c) throw new Error(`Unknown commander: ${id}`);
  return c;
}
export function getMission(id: string): Mission {
  const m = missionsById.get(id);
  if (!m) throw new Error(`Unknown mission: ${id}`);
  return m;
}

/** Book One in order. The map draws straight from this. */
export const bookOne = [...content.missions].sort((a, b) => a.number - b.number);

/** Capital pieces in build order — camp first, tomb last. */
export const capitalOrder = [...content.capital].sort((a, b) => a.order - b.order);

export function commandersUnlockedAt(arena: number): Commander[] {
  return content.commanders.filter((c) => isPlayable(c.confidence) && c.arena <= arena);
}

/**
 * Whether a record may enter play.
 *
 * Everything except outright fiction can: a card openly labelled "reconstructed
 * for gameplay" is honest, and the codex says so. What the game must never do is
 * present a lower level of evidence as a higher one — which is a labelling rule,
 * not a playability one.
 */
export function isPlayable(c: Confidence): boolean {
  return c !== 'fictional';
}

/** Human-readable, for the codex and the offer screen. */
export const CONFIDENCE_LABEL: Record<Confidence, string> = {
  attested: 'Attested',
  probable: 'Probable',
  'traditional-account': 'Traditional account',
  'reconstructed-for-gameplay': 'Reconstructed for play',
  fictional: 'Fiction',
};

export const erasById = new Map(content.eras.map((e) => [e.id, e]));
export const unitsById = new Map(content.units.map((u) => [u.id, u]));
export const spellsById = new Map(content.spells.map((s) => [s.id, s]));
export const kingsById = new Map(content.kings.map((k) => [k.id, k]));
export const battlesById = new Map(content.battles.map((b) => [b.id, b]));
export const arenasById = new Map(content.arenas.map((a) => [a.id, a]));

export function getEra(id: string): Era {
  const e = erasById.get(id);
  if (!e) throw new Error(`Unknown era: ${id}`);
  return e;
}
export function getUnit(id: string): Unit {
  const u = unitsById.get(id);
  if (!u) throw new Error(`Unknown unit: ${id}`);
  return u;
}
export function getBattle(id: string): Battle {
  const b = battlesById.get(id);
  if (!b) throw new Error(`Unknown battle: ${id}`);
  return b;
}
export function getArena(id: number): Arena {
  const a = arenasById.get(id);
  if (!a) throw new Error(`Unknown arena: ${id}`);
  return a;
}

/**
 * Cards a player at this arena is allowed to hold. Unverified content never
 * reaches play — a card the historian has not signed off cannot be drafted, no
 * matter how far the player has progressed.
 */
export function unitsUnlockedAt(arena: number): Unit[] {
  return content.units.filter((u) => isPlayable(u.confidence) && u.arena <= arena);
}

/**
 * Upgrades and doctrines the match's arena has opened. They carry no date gate:
 * a trait is a way of fighting rather than a piece of equipment, so nothing
 * about a scenario's year rules one out. Units are the only date-gated kind.
 */
export function upgradesUnlockedAt(arena: number): Upgrade[] {
  return content.upgrades.filter((u) => isPlayable(u.confidence) && u.arena <= arena);
}

export function doctrinesUnlockedAt(arena: number): Doctrine[] {
  return content.doctrines.filter((d) => isPlayable(d.confidence) && d.arena <= arena);
}

/** Arenas are 1..n; anything outside that is a bad or hostile input. */
export function clampArena(n: unknown): number {
  const v = Math.floor(Number(n));
  if (!Number.isFinite(v)) return 1;
  return Math.min(content.arenas.length, Math.max(1, v));
}

/**
 * The draft pool: verified units of the era, that the scenario's date allows,
 * that the match's arena has unlocked.
 *
 * Two gates, and they teach different things:
 *   - the **date** gate is history — no scythed chariot at Pasargadae in 550
 *     BCE, because the first firm evidence for one is 150 years later;
 *   - the **arena** gate is progression — the ladder widens the roster as the
 *     player climbs, so Anshan is four cards and the Persian Gates is all of them.
 *
 * `arena` is a property of the MATCH, never of a player's private collection.
 * That is what lets the server derive the identical pool and validate a pick it
 * never sent. Drafting from a personal deck would require trusting the client's
 * inventory over the wire, which would give the whole scheme away.
 */
export function draftPool(battle: Battle, arena: number): Unit[] {
  return content.units.filter((u) => {
    if (!isPlayable(u.confidence)) return false;
    if (u.era !== battle.era) return false;
    if (u.arena > arena) return false;
    if (u.earliestAttested !== null && u.earliestAttested > battle.yearNumeric) return false;
    return true;
  });
}

/** Unlocked at this arena, but ruled out by the scenario's date. */
export function lockedUnits(battle: Battle, arena: number): Unit[] {
  return content.units.filter((u) => {
    if (!isPlayable(u.confidence) || u.era !== battle.era) return false;
    if (u.arena > arena) return false;
    return u.earliestAttested !== null && u.earliestAttested > battle.yearNumeric;
  });
}

/** Still behind the ladder — shown so a thin pool reads as progress, not a bug. */
export function arenaLockedUnits(battle: Battle, arena: number): Unit[] {
  return content.units
    .filter((u) => isPlayable(u.confidence) && u.era === battle.era && u.arena > arena)
    .sort((a, b) => a.arena - b.arena);
}

/** Collects every string in the content tree, for the content guard-rail tests. */
export function allStrings(): string[] {
  const out: string[] = [];
  const walk = (v: unknown): void => {
    if (typeof v === 'string') out.push(v);
    else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') Object.values(v).forEach(walk);
  };
  walk(content);
  return out;
}

export type {
  Arena,
  Battle,
  CapitalPiece,
  Commander,
  Confidence,
  ContentDb,
  BookDossier,
  Doctrine,
  DossierDb,
  Era,
  MissionDossier,
  King,
  Mission,
  MissionReward,
  Spell,
  Unit,
  Upgrade,
};
