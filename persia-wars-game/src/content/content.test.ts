import { describe, expect, it } from 'vitest';
import { allStrings, content, draftPool, getBattle, isPlayable, lockedUnits, unitsUnlockedAt } from './index';
import type { Confidence } from './types';

describe('content guard-rails', () => {
  // The hard rule from the parent project, made unbreakable rather than remembered.
  it('never says "Arabian Gulf"', () => {
    expect(allStrings().filter((s) => /arabian\s+gulf/i.test(s))).toEqual([]);
  });

  it('gives every card and codex entry at least one source', () => {
    const unsourced = [
      ...content.battles.map((b) => ({ kind: 'battle', id: b.id, refs: b.sourceRefs })),
      ...content.kings.map((k) => ({ kind: 'king', id: k.id, refs: k.sourceRefs })),
      ...content.units.map((u) => ({ kind: 'unit', id: u.id, refs: u.sourceRefs })),
      ...content.spells.map((s) => ({ kind: 'spell', id: s.id, refs: s.sourceRefs })),
      ...content.arenas.map((a) => ({ kind: 'arena', id: String(a.id), refs: a.sourceRefs })),
    ].filter((x) => x.refs.length === 0);
    expect(unsourced).toEqual([]);
  });

  it('has no blank player-visible strings', () => {
    expect(allStrings().filter((s) => s.trim() === '')).toEqual([]);
  });

  it("keeps modern wars out of the children's core", () => {
    // §9: the Iran–Iraq war is excluded from this dataset entirely.
    expect(content.battles.filter((b) => b.yearNumeric > 1925)).toEqual([]);
  });

  it('points every unit, king and battle at an era that exists', () => {
    const eraIds = new Set(content.eras.map((e) => e.id));
    const orphans = [...content.units, ...content.kings, ...content.battles]
      .filter((x) => !eraIds.has(x.era))
      .map((x) => x.id);
    expect(orphans).toEqual([]);
  });

  it('points every battle at kings that exist', () => {
    const kingIds = new Set(content.kings.map((k) => k.id));
    expect(content.battles.flatMap((b) => b.kings.filter((k) => !kingIds.has(k)))).toEqual([]);
  });

  it('points every card at an arena that exists', () => {
    const arenaIds = new Set(content.arenas.map((a) => a.id));
    const bad = [...content.units, ...content.spells].filter((c) => !arenaIds.has(c.arena)).map((c) => c.id);
    expect(bad).toEqual([]);
  });

  it('has unique ids across every collection', () => {
    for (const [name, rows] of Object.entries({
      units: content.units,
      spells: content.spells,
      kings: content.kings,
      battles: content.battles,
    })) {
      const ids = rows.map((r) => r.id);
      expect(new Set(ids).size, `duplicate id in ${name}`).toBe(ids.length);
    }
  });
});

const LEVELS: Confidence[] = [
  'attested',
  'probable',
  'traditional-account',
  'reconstructed-for-gameplay',
  'fictional',
];

describe('confidence labelling', () => {
  /** Every record that carries sources, across every file. */
  const sourced = [
    ...content.units.map((r) => ({ kind: 'unit', ...r })),
    ...content.upgrades.map((r) => ({ kind: 'upgrade', ...r })),
    ...content.doctrines.map((r) => ({ kind: 'doctrine', ...r })),
    ...content.arenas.map((r) => ({ kind: 'arena', ...r })),
    ...content.battles.map((r) => ({ kind: 'battle', ...r })),
    ...content.kings.map((r) => ({ kind: 'king', ...r })),
    ...content.spells.map((r) => ({ ...r, kind: 'spell' })),
  ];

  it('gives every record one of the five levels', () => {
    for (const r of sourced) {
      expect(LEVELS, `${r.kind} ${r.id}`).toContain(r.confidence);
    }
  });

  it('gives every record at least one source', () => {
    for (const r of sourced) {
      expect(r.sourceRefs.length, `${r.kind} ${r.id} has no source`).toBeGreaterThan(0);
    }
  });

  it('keeps fiction out of every draft pool and every arena unlock', () => {
    for (const battle of content.battles) {
      expect(draftPool(battle, 13).every((u) => isPlayable(u.confidence))).toBe(true);
    }
    for (const arena of content.arenas) {
      expect(unitsUnlockedAt(arena.id).every((u) => isPlayable(u.confidence))).toBe(true);
    }
  });

  it('calls a legend a legend rather than history', () => {
    for (const spell of content.spells) {
      expect(spell.kind).toBe('legend');
      // Real as a story, not as an event. That distinction is the whole point.
      expect(spell.confidence).toBe('traditional-account');
      expect(spell.source.trim().length).toBeGreaterThan(0);
    }
  });

  /*
   * The honesty rule. A card we invented to make the game work has to say so in
   * its own disputed list, not only in a machine-readable field — otherwise it
   * sits next to a researched unit looking exactly as well-evidenced.
   */
  it('makes every invented card admit it in words', () => {
    for (const r of sourced) {
      if (r.confidence !== 'reconstructed-for-gameplay') continue;
      expect(r.disputed.length, `${r.kind} ${r.id} is invented but disputes nothing`).toBeGreaterThan(0);
    }
  });

  it('does not label anything as fiction yet, and would refuse to play it if it did', () => {
    const fiction = sourced.filter((r) => r.confidence === 'fictional');
    expect(fiction).toEqual([]);
    expect(isPlayable('fictional')).toBe(false);
    for (const level of LEVELS.filter((l) => l !== 'fictional')) expect(isPlayable(level)).toBe(true);
  });
});


describe('the arena ladder is a timeline', () => {
  // Cross-checked against Encyclopædia Iranica — see docs/BATTLEGROUNDS.md.
  // An earlier version had Susa before Ecbatana, which is backwards.
  it('never goes backwards in time', () => {
    for (let i = 1; i < content.arenas.length; i++) {
      const prev = content.arenas[i - 1];
      const here = content.arenas[i];
      expect(here.yearNumeric, `${here.name} is earlier than ${prev.name}`).toBeGreaterThanOrEqual(
        prev.yearNumeric,
      );
    }
  });

  it('numbers its rungs 1..n in order', () => {
    expect(content.arenas.map((a) => a.id)).toEqual(content.arenas.map((_, i) => i + 1));
  });

  it('raises the trophy requirement at every rung', () => {
    for (let i = 1; i < content.arenas.length; i++) {
      expect(content.arenas[i].trophies).toBeGreaterThan(content.arenas[i - 1].trophies);
    }
    expect(content.arenas[0].trophies).toBe(0);
  });

  it('starts before Cyrus and ends with Alexander', () => {
    expect(content.arenas[0].name).toBe('Anshan');
    expect(content.arenas[content.arenas.length - 1].yearNumeric).toBe(-330);
  });

  it('gives every ground a date, a place, an art note and a source', () => {
    for (const a of content.arenas) {
      expect(a.year.trim().length, `${a.name} has no date`).toBeGreaterThan(0);
      expect(a.where.trim().length, `${a.name} has no modern location`).toBeGreaterThan(0);
      expect(a.artNote.trim().length, `${a.name} has no art direction`).toBeGreaterThan(0);
      expect(a.sourceRefs.length, `${a.name} is unsourced`).toBeGreaterThan(0);
    }
  });
});

describe('the collection', () => {
  it('has the 25 units and 16 spells the design calls for', () => {
    expect(content.units).toHaveLength(25);
    expect(content.spells).toHaveLength(16);
  });

  it('unlocks a full starting deck in arena 1', () => {
    // A new player is handed four cards. Every one of them has to be a card
    // arena 1 actually unlocks, or the collection shows them as locked.
    const arena1 = unitsUnlockedAt(1);
    expect(arena1.length).toBeGreaterThanOrEqual(4);
  });

  it('gives arena 1 enough variety to teach the counter triangle', () => {
    const classes = new Set(unitsUnlockedAt(1).map((u) => u.class));
    expect(classes.has('archer')).toBe(true);
    expect(classes.has('cavalry')).toBe(true);
    expect(classes.has('infantry') || classes.has('heavy-infantry')).toBe(true);
  });

  it('spreads units across the arena ladder rather than bunching them', () => {
    const byArena = new Map<number, number>();
    for (const u of content.units) byArena.set(u.arena, (byArena.get(u.arena) ?? 0) + 1);
    // Arena 1 must be playable on its own: a starting deck needs four cards.
    expect(unitsUnlockedAt(1).length).toBeGreaterThanOrEqual(3);
    for (const [arena, count] of byArena) {
      expect(count, `arena ${arena} has too many unlocks at once`).toBeLessThanOrEqual(4);
    }
  });

  it('keeps every unit class represented so the counter triangle stays whole', () => {
    const classes = new Set(content.units.map((u) => u.class));
    for (const required of ['heavy-infantry', 'infantry', 'archer', 'cavalry', 'horse-archer', 'chariot', 'elephant']) {
      expect(classes.has(required as never), `no unit of class ${required}`).toBe(true);
    }
  });
});

describe('era gate', () => {
  it('keeps scythed chariots out of Pasargadae in 550 BCE', () => {
    const pool = draftPool(getBattle('pasargadae-550'), 13).map((u) => u.id);
    expect(pool).not.toContain('scythed-chariot');
    expect(pool).not.toContain('war-elephant');
    expect(pool).not.toContain('greek-mercenary-hoplite');
    expect(pool).toContain('immortal');
  });

  it('allows them at the Persian Gates in 330 BCE, after they are attested', () => {
    const pool = draftPool(getBattle('persian-gates-330'), 13).map((u) => u.id);
    expect(pool).toContain('scythed-chariot');
    expect(pool).toContain('war-elephant');
  });

  it('explains every unit it locks out', () => {
    for (const battle of content.battles) {
      for (const u of lockedUnits(battle, 13)) {
        expect(u.attestationNote, `${u.id} is locked with no explanation`).toBeTruthy();
      }
    }
  });

  it('leaves a playable pool in every scenario', () => {
    for (const battle of content.battles) {
      expect(draftPool(battle, 13).length).toBeGreaterThanOrEqual(3);
    }
  });
});

/*
 * Anachronism guard — Concept v0.2, finding 1.5.
 *
 * A battle used to be called "Pasargadae" and sited there, for a fight that
 * happened years before anything stood on that plain. The arena of the same
 * name shows the finished capital, and any scenario can be played at any arena,
 * so the built city was routinely standing behind a battle that preceded it.
 *
 * Generalised: a battle must not be sited at a place the ladder dates later
 * than the battle itself.
 */
describe('battles are not sited at places that did not exist yet', () => {
  it('no battle site names an arena dated after the battle', () => {
    for (const b of content.battles) {
      for (const a of content.arenas) {
        if (!b.site.toLowerCase().includes(a.name.toLowerCase())) continue;
        expect(
          a.yearNumeric,
          `${b.name} (${b.yearNumeric}) is sited at ${a.name}, which the ladder dates to ${a.yearNumeric}`,
        ).toBeLessThanOrEqual(b.yearNumeric);
      }
    }
  });

  it('the 550 BCE revolt records that its location rests on a late source', () => {
    const b = content.battles.find((x) => x.id === 'pasargadae-550')!;
    expect(b.disputed.join(' ')).toMatch(/Strabo/);
  });
});

/**
 * The evidence layer.
 *
 * This text used to sit behind a 'reading level' toggle that defaulted to off,
 * so almost nobody saw it. Measured at the time: 24 of 25 units named a source
 * in the long blurb and 1 of 25 did in the short one — which meant the half of
 * this game that teaches HOW WE KNOW was the half that was hidden.
 *
 * Both are now shown to everyone, the short line as the hook and the long one
 * beneath it. These tests exist because a merge like that can quietly become a
 * deletion: with no toggle left to reveal it, a missing `blurbOlder` would just
 * look like a shorter card.
 */
describe('the sourced text every card carries', () => {
  it('exists for every unit, and is not a copy of the short line', () => {
    const missing = content.units.filter((u) => !u.blurbOlder?.trim());
    expect(missing.map((u) => u.id)).toEqual([]);
    const duplicated = content.units.filter((u) => u.blurbOlder === u.blurb);
    expect(duplicated.map((u) => u.id)).toEqual([]);
  });

  it('actually says more than the hook', () => {
    // Not a style rule — the long text is where the attribution lives, and
    // attribution costs words.
    const tooShort = content.units
      .filter((u) => u.blurbOlder.length <= u.blurb.length)
      .map((u) => u.id);
    expect(tooShort).toEqual([]);
  });

  it('names a source for the overwhelming majority of units', () => {
    // 24 of 25 when this was written. Pinned a little below that so a genuinely
    // sourceless unit can be added, but a drift back toward unsourced flavour
    // fails.
    const cites = /Herodotus|Arrian|Strabo|Xenophon|Ctesias|Persepolis|relief|coin|daric|source|scholar|record/i;
    const sourced = content.units.filter((u) => cites.test(u.blurbOlder));
    expect(sourced.length).toBeGreaterThanOrEqual(content.units.length - 3);
  });

  it('carries the same for both battles and every upgrade and doctrine', () => {
    for (const b of content.battles) expect(b.summaryOlder?.trim()).toBeTruthy();
    for (const c of [...content.upgrades, ...content.doctrines]) {
      expect(c.blurbOlder?.trim()).toBeTruthy();
    }
  });
});
