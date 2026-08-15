/**
 * Content schema for Persia at War.
 *
 * Everything the game teaches lives in JSON so writers and historians can extend
 * it without touching code. Shapes follow RESEARCH-BRIEF.md §5, extended with the
 * fields the references passes turned out to need.
 *
 * English only. The bilingual EN/FA model was dropped on request; re-adding it
 * means turning these `string` fields back into `{ en, fa }` pairs.
 */

export type UnitClass =
  | 'heavy-infantry'
  | 'infantry'
  | 'archer'
  | 'cavalry'
  | 'horse-archer'
  | 'chariot'
  | 'elephant'
  // Reserved for the later launch eras (Safavid onward). Not yet in the data.
  | 'musketeer'
  | 'artillery';

/** Placeholder art keys. Replaced when commissioned art lands. */
export type Silhouette =
  | 'shield'
  | 'spear'
  | 'bow'
  | 'horse'
  | 'horse-bow'
  | 'chariot'
  | 'elephant'
  | 'club'
  | 'lasso'
  | 'camel';

/**
 * How far a record can be trusted. Concept v0.1 §3.4, replacing the old
 * `verified: boolean` — a yes/no flag could not tell a contemporary inscription
 * apart from a Greek story written five centuries later, and the game's whole
 * premise is that the difference matters.
 *
 *  - `attested`                   contemporary evidence: inscription, chronicle, archaeology
 *  - `probable`                   modern scholarship agrees, but the evidence is indirect
 *  - `traditional-account`        a later narrative or a legend — real as a story, not as an event
 *  - `reconstructed-for-gameplay` we invented it to make the game work, and we say so
 *  - `fictional`                  alternate history. Never enters play.
 *
 * The player-facing codex shows this without interrupting play, and the
 * source hierarchy in the brief maps onto it directly: the game may use all
 * five levels but must never present a lower one as a higher one.
 */
export type Confidence =
  | 'attested'
  | 'probable'
  | 'traditional-account'
  | 'reconstructed-for-gameplay'
  | 'fictional';

export interface Sourced {
  confidence: Confidence;
  disputed: string[];
  sourceRefs: string[];
}

export interface Era {
  id: string;
  name: string;
  span: string;
  /** Negative = BCE. Used by the era gate and by scenario filtering. */
  startYear: number;
  endYear: number;
  capital: string;
  color: string;
  accent: string;
  unlockAfter: string | null;
  signatureUnits: string[];
  blurb: string;
  sourceRefs: string[];
}

/**
 * A rung on the trophy ladder. Unlocking one opens the cards gated behind it.
 *
 * The ladder is ordered chronologically by `yearNumeric` — the date each place
 * entered the empire's story — and a test enforces that it never goes backwards.
 * These are places rather than events, so most of them existed at the same time;
 * the anchor date is the moment each one becomes Persian.
 */
export interface Arena extends Sourced {
  id: number;
  name: string;
  /**
   * Media key. The arena looks for `public/art/arenas/<slug>.mp4` for its intro
   * motion and `<slug>.png` for a still, and falls back cleanly when neither is
   * there — so the other twelve drop in without a code change.
   */
  slug: string;
  /** Modern location, so the map is findable. */
  where: string;
  subtitle: string;
  /** Human-readable anchor date, e.g. "550 BCE". */
  year: string;
  /** Negative = BCE. Drives the chronological-order test. */
  yearNumeric: number;
  /** Trophies required to reach this arena. */
  trophies: number;
  blurb: string;
  /** Direction for the commissioned battleground panel. */
  artNote: string;
  /**
   * The two figures flanking the lobby, if this ground has attested ones.
   * Omitted rather than invented — an arena without figures simply renders
   * without medallions.
   */
  figures?: {
    left: { name: string; title: string };
    right: { name: string; title: string };
  };
}

export interface Unit extends Sourced {
  id: string;
  era: string;
  class: UnitClass;
  name: string;
  /** Arena that unlocks this card for collection and play. */
  arena: number;

  // Combat profile. Tuned in src/sim/battle.ts — see BALANCE notes there.
  atk: number;
  def: number;
  hp: number;
  /** Field units, where the battlefield is 100 wide. 1.5 ≈ melee reach. */
  range: number;
  /** Field units per tick. */
  speed: number;
  /** Ticks between attacks. */
  attackInterval: number;
  /** Horse-archers back away rather than let melee close — the kiting behaviour. */
  kite: boolean;

  counters: UnitClass[];
  counteredBy: UnitClass[];

  /**
   * The hook. Shown on the draft card, which is read in about two seconds while
   * choosing under a timer, so it has to be one idea and it has to fit.
   */
  blurb: string;
  /**
   * The same subject with its ATTRIBUTION. Herodotus, the Persepolis reliefs,
   * the gold daric — what we know this from, and how firmly.
   *
   * These were once `blurb` and `blurbOlder`, a kid/older reading toggle that
   * defaulted to kid. That was never a reading-age split: 24 of 25 units named
   * a source in the long text and 1 of 25 did in the short one, so the toggle
   * was the evidence layer and it was off. Both are now shown to everyone — the
   * hook on the card, this in the codex beneath it — and the field is named for
   * the job it does rather than for an audience that no longer exists.
   */
  evidence: string;

  /**
   * Year this unit is first firmly attested in an Iranian army (negative = BCE).
   * `null` means it is available for the whole era.
   */
  earliestAttested: number | null;
  /** Why the gate exists, shown to the player when a unit is locked out. */
  attestationNote: string | null;

  art: { silhouette: Silhouette };
}

/**
 * A Zauber card. These come from Iranian myth — the Shahnameh and the Avesta —
 * not from the historical record, and `kind: 'legend'` is what makes the codex
 * say so out loud. Teaching the difference between a story and an event is part
 * of the point, so legends are labelled, never quietly mixed in with history.
 */
export interface Spell extends Sourced {
  id: string;
  name: string;
  /** Where the story comes from, e.g. "Shahnameh" or "Avesta". */
  source: string;
  arena: number;
  kind: 'legend';
  blurb: string;
  evidence: string;
  art: { silhouette: Silhouette };
}

/**
 * A codex figure. Named `King` to match the brief's schema, but the collection
 * also holds commanders who were never kings (satraps, generals) — `title` says
 * which, so the game never promotes anyone it shouldn't.
 */
export interface King extends Sourced {
  id: string;
  era: string;
  name: string;
  title: string;
  reign: string;
  bio: string;
  achievement: string;
}

/** A battle is both a playable scenario and the codex card it unlocks. */
export interface Battle extends Sourced {
  id: string;
  era: string;
  year: string;
  /** Negative = BCE. Drives the draft-pool attestation gate. */
  yearNumeric: number;
  name: string;
  opponents: { a: string; b: string };
  /** What actually happened. The game result may diverge; this never changes. */
  victor: string;
  victorSide: 'a' | 'b';
  onIranianSoil: boolean;
  site: string;
  summary: string;
  evidence: string;
  teaches: string[];
  /** King ids unlocked in the codex by playing this scenario. */
  kings: string[];
  field: {
    terrain: 'plain' | 'gorge';
    note: string;
  };
}

/**
 * What a card does when it is taken. Three kinds, split so that no two of them
 * can do each other's job — Concept v0.2 finding 1.3:
 *
 *   unit     joins the field, or raises the rank of a squad already there
 *   upgrade  gives one squad a TRAIT. Never a rank. Sideways, not upward.
 *   doctrine changes how the whole army behaves
 */
export type CardKind = 'unit' | 'upgrade' | 'doctrine';

/** Traits an Upgrade can grant. Each is implemented in src/sim/battle.ts. */
export type TraitId =
  | 'ready-volley'
  | 'locked-shields'
  | 'long-reach'
  | 'wheeling-line'
  | 'loosed-rein';

/** Army-wide effects a Doctrine can apply. Also implemented in the sim. */
export type DoctrineId = 'centre-holds' | 'shoot-the-horses' | 'broken-ground';

/**
 * Shared by both new kinds. `consequence` is the line the offer screen shows —
 * v0.1 §6.4 requires a stated consequence and forbids a bare percentage, so
 * this field is what the player reads before choosing, and it is prose.
 */
interface Playable extends Sourced {
  id: string;
  name: string;
  /** Arena that unlocks this card. */
  arena: number;
  consequence: string;
  blurb: string;
  evidence: string;
  art: { silhouette: Silhouette };
}

export interface Upgrade extends Playable {
  trait: TraitId;
  /** Squad classes this can be applied to. Offered only when one is fielded. */
  appliesTo: UnitClass[];
}

export interface Doctrine extends Playable {
  effect: DoctrineId;
}

/** Commander passives, implemented in src/sim/battle.ts and roundCore.ts. */
export type PassiveId = 'many-peoples' | 'kings-levy';
/** Commander orders. One use a match, fired at a stated trigger. */
export type OrderId = 'the-line-reforms' | 'muster-again';

/**
 * A commander. v0.1 §7: one passive identity, one order, one drafting affinity.
 *
 * The `confidence` on this record is about the **person** — both of these are
 * attested rulers. The kit is not: no source describes either man using a
 * battlefield doctrine, and each record says so in its own `disputed` list,
 * enforced by test.
 */
export interface Commander extends Sourced {
  id: string;
  name: string;
  epithet: string;
  arena: number;
  /** Which way slot C of the offer leans: toward new classes, or toward yours. */
  affinity: 'wide' | 'deep';
  passive: { id: PassiveId; name: string; reads: string };
  order: { id: OrderId; name: string; reads: string; trigger: string };
  blurb: string;
  evidence: string;
  art: { silhouette: Silhouette };
}

/**
 * A Chronicle mission. Concept v0.2 §9 — Book One, Rise of Cyrus.
 *
 * The chapter is a **dramatic reconstruction** and the game says so on entry.
 * Most missions are `reconstructed-for-gameplay`: the framework of the revolt is
 * known, the scenes are not. Where a mission rests on a real record its
 * confidence says so, and where it rests on Herodotus it says that instead.
 */
export type MissionObjective =
  /** Win the match. */
  | 'defeat'
  /** Win by still having an army at the end — mission 10's whole point. */
  | 'survive'
  /** No battle at all: a decision that shapes what you carry forward. */
  | 'choice';

/**
 * What finishing a mission gives you. Breadth, never power — v0.1 §5.1: campaign
 * rewards unlock choice and must not create a statistical advantage in ranked.
 */
export interface MissionReward {
  kind: 'card' | 'upgrade' | 'doctrine' | 'commander' | 'capital';
  id: string;
}

export interface MissionChoice {
  id: string;
  label: string;
  reads: string;
  reward: MissionReward;
}

export interface Mission extends Sourced {
  id: string;
  chapter: 1 | 2;
  /** 1-based across the whole book, so the map can number them straight through. */
  number: number;
  name: string;
  /** The 15–30 second setup. v0.1 §5.1 step 2 — always skippable. */
  setup: string;
  objective: MissionObjective;
  /** Rounds to win. Ramps through the book; 0 for a `choice` mission. */
  winsNeeded: number;
  scenario: string;
  teaches: string[];
  reward: MissionReward | null;
  choices?: MissionChoice[];
  /**
   * Whether the full Historical Battle Dossier (v0.1 §14) exists for this
   * mission. The dossier itself lives in `dossiers.json`, keyed by mission id;
   * a test asserts this flag and that file agree, so the flag cannot be set
   * without the document.
   */
  dossier: boolean;
}

/**
 * The Historical Battle Dossier — v0.1 §14.
 *
 * A production document, not a marketing one. Its most important field is
 * `mustNotClaim`: the things that are widely believed, or dramatically
 * convenient, and are not supported. A dossier whose `whatWeKnow` reads "almost
 * nothing" is doing its job — most of Book One is scene-setting on a four-fact
 * frame, and saying so is the point.
 */
export interface MissionDossier {
  /** Plain-language, player-facing. The "what we know" card after a mission. */
  whatWeKnow: string;
  location: { text: string; confidence: Confidence };
  combatants: string;
  /** Contemporary or near-contemporary evidence specific to this mission. */
  specificEvidence: string[];
  /** Later narrative sources, always flagged as later. */
  laterSources?: string[];
  unitArchetypes: string[];
  /** Never present these as fact. The field that earns the document. */
  mustNotClaim: string[];
  abstractions: { what: string; why: string }[];
  reviewStatus: 'drafted' | 'specialist-reviewed';
}

/** The evidence base shared by every mission in a book, stated once. */
export interface BookDossier {
  id: string;
  title: string;
  framework: string;
  dateRange: { text: string; confidence: Confidence };
  contemporaryEvidence: string[];
  laterSources: string[];
  material: string[];
  mustNotClaim: string[];
  sensitivities: string[];
  reviewStatus: 'drafted' | 'specialist-reviewed';
}

export interface DossierDb {
  book: BookDossier;
  missions: Record<string, MissionDossier>;
}

/** A piece of Pasargadae. Cosmetic and narrative only — never a ranked stat. */
export interface CapitalPiece extends Sourced {
  id: string;
  name: string;
  order: number;
  reads: string;
}

export interface ContentDb {
  eras: Era[];
  arenas: Arena[];
  units: Unit[];
  upgrades: Upgrade[];
  doctrines: Doctrine[];
  commanders: Commander[];
  missions: Mission[];
  capital: CapitalPiece[];
  spells: Spell[];
  kings: King[];
  battles: Battle[];
}
