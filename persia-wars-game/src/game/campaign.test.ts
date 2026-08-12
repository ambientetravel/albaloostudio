import { describe, expect, it } from 'vitest';
import { bookOne, capitalOrder, content, dossierFor, dossiers, getMission } from '../content';
import {
  bookFinished,
  bookProgress,
  capitalProgress,
  chapterOf,
  completeMission,
  freshCampaign,
  isComplete,
  isUnlocked,
  missionSucceeded,
  nextMission,
  rewardFor,
  setCounterHistory,
  type CampaignState,
} from './campaign';

/**
 * Book One — the Chronicle frame.
 *
 * The rule these tests exist to protect is v0.1 §5.1: **campaign rewards unlock
 * breadth of choice and must never create a statistical advantage in ranked**.
 * A campaign that hands out power is a campaign that has to be played before you
 * can compete, and that is the thing the concept is most explicit about not
 * wanting.
 */

describe('the shape of Book One', () => {
  it('is fourteen missions in two chapters of seven', () => {
    expect(bookOne).toHaveLength(14);
    expect(chapterOf(1)).toHaveLength(7);
    expect(chapterOf(2)).toHaveLength(7);
  });

  it('numbers them 1..14 with no gaps and no repeats', () => {
    expect(bookOne.map((m) => m.number)).toEqual(Array.from({ length: 14 }, (_, i) => i + 1));
  });

  it('keeps chapter one before chapter two', () => {
    for (const m of bookOne) expect(m.chapter).toBe(m.number <= 7 ? 1 : 2);
  });

  it('names every scenario a mission plays on', () => {
    for (const m of bookOne) {
      expect(content.battles.some((b) => b.id === m.scenario), `${m.id} → ${m.scenario}`).toBe(true);
    }
  });

  it('ramps the match length rather than making every mission a full match', () => {
    const first = bookOne[0];
    const last = bookOne[bookOne.length - 1];
    expect(first.winsNeeded).toBeLessThan(last.winsNeeded);
    expect(last.winsNeeded).toBe(4);
  });

  it('includes the survival mission, because losing well is the lesson', () => {
    const survive = bookOne.filter((m) => m.objective === 'survive');
    expect(survive.length).toBeGreaterThan(0);
    expect(survive.map((m) => m.id)).toContain('retreat-to-persis');
  });

  it('includes a mission that is a decision rather than a battle', () => {
    const choices = bookOne.filter((m) => m.objective === 'choice');
    expect(choices.length).toBeGreaterThan(0);
    for (const m of choices) {
      expect(m.choices?.length ?? 0).toBeGreaterThan(1);
      // A branch that gives nothing is not a choice.
      for (const c of m.choices ?? []) expect(c.reward).toBeTruthy();
    }
  });
});

describe('rewards are breadth, never power', () => {
  /** Every reward the book can hand out, including every branch of every choice. */
  const allRewards = bookOne.flatMap((m) => [
    ...(m.reward ? [m.reward] : []),
    ...(m.choices ?? []).map((c) => c.reward),
  ]);

  it('only ever grants a card, a trait, a doctrine, a commander or a building', () => {
    for (const r of allRewards) {
      expect(['card', 'upgrade', 'doctrine', 'commander', 'capital']).toContain(r.kind);
    }
  });

  it('points every reward at something that actually exists', () => {
    for (const r of allRewards) {
      const pool =
        r.kind === 'card'
          ? content.units
          : r.kind === 'upgrade'
            ? content.upgrades
            : r.kind === 'doctrine'
              ? content.doctrines
              : r.kind === 'commander'
                ? content.commanders
                : content.capital;
      expect(pool.some((x) => x.id === r.id), `${r.kind} ${r.id}`).toBe(true);
    }
  });

  it('never grants the same thing twice — a duplicate would be a stat, not a choice', () => {
    const keys = allRewards.map((r) => `${r.kind}:${r.id}`);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it('never grants a card the player already starts with', () => {
    // "Breadth" has to mean something you did not have. Two of these originally
    // handed back a starter card, which is breadth on paper and nothing at all
    // in the hand.
    const starters = ['persian-archer', 'spara-bearer', 'median-spearman', 'persian-cavalry'];
    for (const r of allRewards) {
      if (r.kind !== 'card') continue;
      expect(starters, `mission reward ${r.id} is already in the starting deck`).not.toContain(r.id);
    }
  });

  it('teaches the trait and doctrine system through the book', () => {
    // Ways of fighting carry no date gate, which makes them the honest thing for
    // a 550 BCE revolt to hand out — most of the unit roster postdates it.
    const kinds = allRewards.map((r) => r.kind);
    expect(kinds.filter((k) => k === 'upgrade').length).toBeGreaterThanOrEqual(
      content.upgrades.length,
    );
    expect(kinds.filter((k) => k === 'doctrine').length).toBeGreaterThanOrEqual(
      content.doctrines.length,
    );
  });

  it('opens both commanders across the book', () => {
    const commanders = allRewards.filter((r) => r.kind === 'commander').map((r) => r.id);
    expect(new Set(commanders)).toEqual(new Set(content.commanders.map((c) => c.id)));
  });
});

describe('missions unlock in order', () => {
  it('starts with exactly one mission open', () => {
    const c = freshCampaign();
    expect(bookOne.filter((m) => isUnlocked(m, c))).toHaveLength(1);
    expect(nextMission(c)?.number).toBe(1);
  });

  it('opens the next one only when the one before it is done', () => {
    let c = freshCampaign();
    for (const m of bookOne) {
      expect(isUnlocked(m, c), `${m.id} should be open now`).toBe(true);
      expect(isComplete(m, c)).toBe(false);
      const after = bookOne.find((x) => x.number === m.number + 1);
      if (after) expect(isUnlocked(after, c), `${after.id} should still be shut`).toBe(false);
      c = completeMission(c, m.id, m.choices?.[0]?.id);
    }
    expect(bookProgress(c)).toEqual({ done: 14, total: 14 });
    expect(nextMission(c)).toBeNull();
  });

  it('cannot be completed twice', () => {
    const once = completeMission(freshCampaign(), 'small-court');
    expect(completeMission(once, 'small-court')).toBe(once);
  });
});

describe('objectives', () => {
  const survive = getMission('retreat-to-persis');
  const defeat = getMission('last-stand');

  it('a defeat mission needs the full win count', () => {
    expect(missionSucceeded(defeat, { a: defeat.winsNeeded, b: 1 }, 'a')).toBe(true);
    expect(missionSucceeded(defeat, { a: defeat.winsNeeded - 1, b: 4 }, 'a')).toBe(false);
  });

  it('a survival mission is won by taking one round, not by winning the match', () => {
    // Losing 1–2 is a success here. That is the entire point of the mission:
    // you got the army out, and the scoreline says you lost.
    expect(missionSucceeded(survive, { a: 1, b: 2 }, 'a')).toBe(true);
    expect(missionSucceeded(survive, { a: 0, b: 2 }, 'a')).toBe(false);
  });

  it('a choice mission always succeeds — the branch is the outcome', () => {
    expect(missionSucceeded(getMission('tribal-council'), { a: 0, b: 0 }, 'a')).toBe(true);
  });

  it('gives a choice mission the reward of the branch actually taken', () => {
    const m = getMission('tribal-council');
    for (const c of m.choices ?? []) {
      expect(rewardFor(m, c.id)).toEqual(c.reward);
    }
    expect(rewardFor(m, 'not-a-branch')).toBeNull();
  });
});

describe('the capital', () => {
  it('is built in order and only by finishing the book', () => {
    let c = freshCampaign();
    expect(capitalProgress(c)).toBe(0);
    for (const m of bookOne) c = completeMission(c, m.id, m.choices?.[0]?.id);
    // Only the pieces the book actually awards are built; the rest wait for a
    // later book rather than appearing for free.
    const awarded = bookOne.filter((m) => m.reward?.kind === 'capital').map((m) => m.reward!.id);
    expect(c.capital).toEqual(awarded);
    expect(capitalProgress(c)).toBeCloseTo(awarded.length / capitalOrder.length, 5);
  });

  it('never touches a number the simulation can read', async () => {
    // The capital is narrative and cosmetic. If the battle simulation ever
    // learns about it, this fails.
    const src = await import('node:fs').then((fs) =>
      fs.readFileSync(new URL('../sim/battle.ts', import.meta.url), 'utf8'),
    );
    expect(src).not.toMatch(/capital/i);
    expect(src).not.toMatch(/campaign/i);
    expect(src).not.toMatch(/mission/i);
  });
});

describe('historical honesty', () => {
  it('labels every mission and says what is disputed about it', () => {
    for (const m of bookOne) {
      expect(m.confidence, m.id).toBeTruthy();
      expect(m.disputed.length, `${m.id} disputes nothing`).toBeGreaterThan(0);
      expect(m.sourceRefs.length, `${m.id} cites nothing`).toBeGreaterThan(0);
    }
  });

  it('does not claim fourteen documented battles', () => {
    // Most of the book is scenes built on a known framework. If a majority ever
    // came out as attested, someone has overclaimed.
    const attested = bookOne.filter((m) => m.confidence === 'attested');
    expect(attested.length).toBeLessThan(bookOne.length / 2);
  });

  it('has no mission claiming a dossier it does not have', () => {
    // The flag and the document must agree in both directions, so the flag can
    // never be set without the work.
    for (const m of bookOne) {
      expect(Boolean(dossierFor(m.id)), `${m.id} flag says ${m.dossier}`).toBe(m.dossier);
    }
    expect(bookOne.every((m) => m.dossier)).toBe(true);
  });
});

/**
 * The Historical Battle Dossier — v0.1 §14.
 *
 * The field these tests care most about is `mustNotClaim`. A dossier that lists
 * evidence but never says what must NOT be claimed is a bibliography, not a
 * guard-rail, and the guard-rail is the reason the document exists.
 */
describe('the dossiers', () => {
  it('gives every mission the full document', () => {
    for (const m of bookOne) {
      const d = dossierFor(m.id)!;
      expect(d, m.id).toBeTruthy();
      expect(d.whatWeKnow.length, `${m.id} whatWeKnow`).toBeGreaterThan(40);
      expect(d.location.text.length, `${m.id} location`).toBeGreaterThan(0);
      expect(d.combatants.length, `${m.id} combatants`).toBeGreaterThan(0);
      expect(d.reviewStatus, m.id).toBe('drafted');
    }
  });

  it('tells every mission something it must never claim', () => {
    for (const m of bookOne) {
      const d = dossierFor(m.id)!;
      expect(d.mustNotClaim.length, `${m.id} names nothing it must not claim`).toBeGreaterThan(0);
    }
  });

  it('explains every gameplay abstraction it makes', () => {
    for (const m of bookOne) {
      const d = dossierFor(m.id)!;
      expect(d.abstractions.length, `${m.id} abstracts nothing`).toBeGreaterThan(0);
      for (const a of d.abstractions) {
        expect(a.what.length, `${m.id} abstraction without a name`).toBeGreaterThan(0);
        expect(a.why.length, `${m.id}: "${a.what}" has no reason`).toBeGreaterThan(20);
      }
    }
  });

  it('is honest that most of the book is not documented', () => {
    // If most missions started claiming contemporary evidence of their own,
    // someone has overclaimed — four facts underpin the whole book.
    const withOwnEvidence = bookOne.filter((m) => (dossierFor(m.id)!.specificEvidence ?? []).length > 0);
    expect(withOwnEvidence.length).toBeLessThan(bookOne.length / 2);
  });

  /*
   * The distinction the whole document exists to hold. Herodotus writing a
   * century later is not contemporary evidence, and filing him as such is
   * exactly the blurring the source hierarchy in v0.1 §14 forbids — the game may
   * use all five levels but must never present a lower one as a higher one.
   *
   * This caught four real miscategorisations on the first run.
   */
  it('never files a later narrative source as contemporary evidence', () => {
    const later = /Herodotus|Strabo|Ctesias|Xenophon|Nicolaus/i;
    for (const m of bookOne) {
      for (const e of dossierFor(m.id)!.specificEvidence) {
        expect(later.test(e), `${m.id} files a later source as contemporary: "${e.slice(0, 50)}…"`).toBe(
          false,
        );
      }
    }
    for (const e of dossiers.book.contemporaryEvidence) {
      expect(later.test(e), `book-level: "${e.slice(0, 50)}…"`).toBe(false);
    }
  });

  it('flags every later source as later, where one is used', () => {
    const later = /Herodotus|Strabo|Ctesias|Xenophon|Nicolaus/i;
    const usesLater = bookOne.filter((m) => (dossierFor(m.id)!.laterSources ?? []).length > 0);
    expect(usesLater.length).toBeGreaterThan(0);
    for (const m of usesLater) {
      const joined = (dossierFor(m.id)!.laterSources ?? []).join(' ');
      expect(later.test(joined), m.id).toBe(true);
    }
  });

  it("bars the Cyrus Cylinder-as-human-rights claim at the book level", () => {
    // The most common modern misreading of this material, and the one most
    // likely to reach a child in this audience. It is barred by name.
    const book = dossiers.book;
    expect(book.mustNotClaim.join(' ')).toMatch(/human rights/i);
    expect(book.mustNotClaim.join(' ')).toMatch(/Cyrus Cylinder/i);
  });

  it('bars writing the Medes as villains, and names the Persian Gulf rule', () => {
    const care = dossiers.book.sensitivities.join(' ');
    expect(care).toMatch(/Medes/);
    expect(care).toMatch(/Persian Gulf/);
    expect(care).not.toMatch(/Arabian Gulf(?!')/);
  });

  it('never states a date as certain when the sources disagree', () => {
    expect(dossiers.book.dateRange.confidence).not.toBe('attested');
    expect(dossiers.book.dateRange.text).toMatch(/553/);
    expect(dossiers.book.dateRange.text).toMatch(/550/);
  });
});

/**
 * Counter-History — v0.1 §4. The other side, opened only after the documented
 * path is finished, labelled as alternate history, and paying nothing.
 */
describe('Counter-History', () => {
  const finished = (): CampaignState => {
    let c = freshCampaign();
    for (const m of bookOne) c = completeMission(c, m.id, m.choices?.[0]?.id);
    return c;
  };

  it('will not open before the book is finished the way it happened', () => {
    let c = freshCampaign();
    expect(bookFinished(c)).toBe(false);
    expect(setCounterHistory(c, true).counterHistory).toBe(false);

    // Even one mission short is short.
    for (const m of bookOne.slice(0, 13)) c = completeMission(c, m.id, m.choices?.[0]?.id);
    expect(setCounterHistory(c, true).counterHistory).toBe(false);
  });

  it('opens once the book is done', () => {
    const c = setCounterHistory(finished(), true);
    expect(c.counterHistory).toBe(true);
  });

  it('starts the other side from the beginning rather than handing it over', () => {
    const c = setCounterHistory(finished(), true);
    // The historical book is complete; the Median one is not.
    expect(bookProgress(c)).toEqual({ done: 0, total: 14 });
    expect(nextMission(c)?.number).toBe(1);
    expect(isUnlocked(bookOne[1], c)).toBe(false);
  });

  it('pays nothing — an outcome that did not happen should not reward', () => {
    const before = setCounterHistory(finished(), true);
    const after = completeMission(before, 'small-court');
    expect(after.counterCompleted).toEqual(['small-court']);
    // Nothing else moved: no capital, no commanders, no new historical progress.
    expect(after.capital).toEqual(before.capital);
    expect(after.commanders).toEqual(before.commanders);
    expect(after.completed).toEqual(before.completed);
  });

  it('has the reward path guarded in both places', async () => {
    // `completeMission` refuses to record a Counter-History reward. The store
    // computes the grant separately, and on the first run it paid out anyway —
    // so the guard has to exist on both sides, and this checks the second one.
    const src = await import('node:fs').then((fs) =>
      fs.readFileSync(new URL('../state/store.ts', import.meta.url), 'utf8'),
    );
    expect(src).toMatch(/counterHistory/);
    // Both the battle path and the choice path must consult it.
    const guards = src.match(/counterHistory/g) ?? [];
    expect(guards.length).toBeGreaterThanOrEqual(2);
  });

  it('leaves the historical record intact when switched back', () => {
    let c = setCounterHistory(finished(), true);
    c = completeMission(c, 'small-court');
    c = setCounterHistory(c, false);
    expect(bookProgress(c)).toEqual({ done: 14, total: 14 });
    expect(c.counterCompleted).toEqual(['small-court']);
  });
});
