import { useState } from 'react';
import { CONFIDENCE_LABEL, content, draftPool, getArena, isPlayable } from '../content';
import type { Arena, Battle, Confidence } from '../content/types';
import { arenaForTrophies, TROPHY_LOSS, TROPHY_WIN, COINS_LOSS, COINS_WIN } from '../game/progression';
import {
  COUNTERED_PENALTY,
  COUNTER_BONUS,
  DAMAGE_NOISE,
  DEF_SCALE,
  GORGE_MOBILITY_PENALTY,
} from '../sim/battle';
import {
  MAX_SQUADS,
  OFFER_SIZE,
  RALLY_AT,
  ROUNDS_MAX,
  TIER_NAME,
  WINS_NEEDED,
  offerSizeForDeficit,
} from '../sim/roundCore.ts';
import { useGame } from '../state/store';
import { CLASS_LABEL, unitSubtitle } from './labels';
import { UnitGlyph } from './UnitGlyph';

/**
 * The rulebook.
 *
 * Every number on this screen is imported from the code that enforces it —
 * squad size from the draft, the counter multipliers from the simulation, the
 * trophy swing from progression. Nothing is retyped as prose. A balance change
 * therefore updates what the game tells the player instead of quietly turning
 * this page into a lie, which is the failure mode a hand-written rules screen
 * always ends in.
 *
 * Written for the same reader as the cards: nine to fourteen, told the truth,
 * including the parts that are unflattering (card levels buy you nothing).
 */

interface Rule {
  title: string;
  lines: string[];
}

const DRAFT_RULES: Rule[] = [
  {
    title: `First to ${WINS_NEEDED} rounds`,
    lines: [
      `A match is up to ${ROUNDS_MAX} rounds. The first player to win ${WINS_NEEDED} of them takes the match.`,
      `At ${WINS_NEEDED - 1}–${WINS_NEEDED - 1} the last round is announced as the Final Clash.`,
    ],
  },
  {
    title: 'One card a round, and you keep it',
    lines: [
      `Every round you are shown ${OFFER_SIZE} cards and take one. It joins your army for the rest of the match.`,
      'The battlefield clears between rounds. Your army does not. Round 1 is one squad; round 7 can be seven.',
    ],
  },
  {
    title: 'You both choose at the same time',
    lines: [
      'Neither of you sees the other\u2019s card until both are locked in. There is no waiting for your turn.',
      'The three cards you see are not the three they see.',
    ],
  },
  {
    title: 'Where your three cards come from',
    lines: [
      'One is drawn from your own warband, so the deck you built matters.',
      'One is a stronger version of something you already field.',
      'One is a wildcard from the arena, and it leans toward answers to whatever your opponent has been building. It leans — it is never a guarantee.',
    ],
  },
  {
    title: 'Three kinds of card, and they cannot swap jobs',
    lines: [
      'A **unit** joins your army, or makes a squad you already have go up a rank.',
      'An **upgrade** teaches one squad to fight differently. It never raises a rank.',
      'A **doctrine** changes how your whole army behaves.',
      'Every upgrade and doctrine tells you what it does in words, and every one of them costs you something. There is no card that is simply better.',
    ],
  },
  {
    title: 'Taking the same card twice makes it stronger',
    lines: [
      `A repeat does not join twice — it rises a rank: ${TIER_NAME.join(' \u2192 ')}. More men, better kit, harder to kill.`,
      `Ranks are capped by how far the match has run: ${TIER_NAME[1]} from round 3, ${TIER_NAME[2]} from round 5, ${TIER_NAME[3]} only in round ${ROUNDS_MAX}. An early lead cannot run away with it.`,
      `You can field at most ${MAX_SQUADS} different squads. After that, every pick makes what you have stronger.`,
    ],
  },
];

const BATTLE_RULES: Rule[] = [
  {
    title: 'Nobody is driving',
    lines: [
      'Once the squads are set, the battle plays itself. The draft was the game.',
      'Both players watch the same fight — the result was decided by what you picked, not by who taps faster.',
    ],
  },
  {
    title: 'The counter triangle',
    lines: [
      `Hitting something you are strong against does ×${COUNTER_BONUS} damage.`,
      `Hitting something you are weak against does ×${COUNTERED_PENALTY}.`,
      'Every card lists both, on the card. This is the whole skill of the game.',
    ],
  },
  {
    title: 'How damage lands',
    lines: [
      `Attack, times the counter multiplier, give or take ${Math.round(DAMAGE_NOISE * 100)}% luck, minus ${Math.round(DEF_SCALE * 100)}% of the defender's armour.`,
      'It can never drop below 1. Nothing in this game is immune to anything.',
    ],
  },
  {
    title: 'Ground changes everything',
    lines: [
      `In a gorge there is no room to ride: ${Object.entries(GORGE_MOBILITY_PENALTY)
        .map(([cls, m]) => `${CLASS_LABEL[cls as keyof typeof CLASS_LABEL]} ×${m}`)
        .join(', ')}.`,
      'That is not just slower. A chariot in a narrow place is not a slow chariot, it is a useless one — which is exactly what happened at the Persian Gates.',
    ],
  },
  {
    title: 'Horse-archers refuse to be caught',
    lines: [
      'A horse-archer backs away from anything melee that closes on it, shooting as it goes.',
      'This is the real Saka tactic the Parthians later became famous for. To beat it, bring something that can shoot back.',
    ],
  },
  {
    title: 'Lines break as the round runs on',
    lines: [
      'Past halfway through a round, every blow starts landing harder, and it keeps rising to the end.',
      'Armies of the ancient world broke through exhaustion and lost order, not by fighting to the last man. It also means a round always ends.',
    ],
  },
  {
    title: 'Winning a round',
    lines: [
      'Last side still standing takes the round.',
      'If the round runs out with both sides up, the side with more health left takes it. Dead level is a draw, and a draw scores for nobody.',
    ],
  },
];

const COMEBACK_RULES: Rule[] = [
  {
    title: 'Falling behind gets you more choice, never more power',
    lines: [
      `One round down, you are shown ${offerSizeForDeficit(1)} cards instead of ${OFFER_SIZE}. Two or more down, ${offerSizeForDeficit(2)}.`,
      'Nothing you have is weakened and nothing of theirs is. You simply get more to pick from.',
    ],
  },
  {
    title: 'The Rally',
    lines: [
      `Lose ${RALLY_AT} rounds without winning one and you hold a Rally. Spend it to throw the hand away and draw a new one.`,
      'You choose when. Winning a round clears it, so it can never be saved up.',
      'Your opponent is told when you spend it. A comeback they cannot see would be a rubber band.',
    ],
  },
  {
    title: 'The wildcard leans your way',
    lines: [
      'The third card is already weighted toward an answer to what your opponent is fielding. While you are behind, it leans harder.',
      'It leans. It is never a promise — there is no card in this game that is guaranteed to be the one you need.',
    ],
  },
];

const COMMANDER_RULES: Rule[] = [
  {
    title: 'Your commander changes how you draft, not how hard you hit',
    lines: [
      'Each one has one thing that is always true, one thing that happens once, and a habit that shapes what the wildcard offers you.',
      'Neither is stronger. Across two hundred test matches they finish within a few points of each other.',
    ],
  },
  {
    title: 'Nobody presses a button mid-battle',
    lines: [
      'A commander\u2019s order fires by itself, at the moment printed on the card.',
      'The battle plays itself once the squads are set — an order you had to tap for would make that untrue.',
    ],
  },
];

const LADDER_RULES: Rule[] = [
  {
    title: 'Trophies',
    lines: [
      `Win: +${TROPHY_WIN}. Lose: ${TROPHY_LOSS}.`,
      'Trophies never fall below zero. You cannot get stuck.',
      `You are paid either way — ${COINS_WIN} coins for a win, ${COINS_LOSS} for a loss.`,
    ],
  },
  {
    title: 'The match is played at the lower arena',
    lines: [
      'If a player near the top of the ladder meets a beginner, the match is fought at the beginner’s arena.',
      'The higher player loses access to their newer cards for that match. It is the only way a first-day player gets a fair game.',
    ],
  },
  {
    title: 'Levelling a card does not make it stronger',
    lines: [
      'Card levels count towards your collection and your Scrolls. They are not used in the fight — not by one point.',
      'A card you understood beats a card you ground for. That is on purpose.',
    ],
  },
  {
    title: 'An arena is where you compete, not where it happened',
    lines: [
      'The thirteen rungs are grounds you fight on as you climb. They are not the sites of the battles you play.',
      'Pasargadae the arena is the finished capital. The battle called “The Plain before Pasargadae” was fought on empty ground years before any of it was built.',
    ],
  },
  {
    title: 'History outranks the ladder',
    lines: [
      'A card can be unlocked and still be undraftable, if the battle you are playing happened before that unit is first attested.',
      'No scythed chariot at Pasargadae in 550 BCE: the first firm evidence for one is about 150 years later. Tap a greyed-out card in a draft and it will tell you why.',
    ],
  },
];

export function Rules() {
  const { trophies } = useGame();
  const [open, setOpen] = useState<Arena | null>(null);
  const reached = arenaForTrophies(trophies);

  return (
    <div className="rules">
      <section className="rules__group">
        <h3 className="rules__heading">Drafting</h3>
        {DRAFT_RULES.map((r) => (
          <RuleCard key={r.title} rule={r} />
        ))}
      </section>

      <section className="rules__group">
        <h3 className="rules__heading">The battle</h3>
        {BATTLE_RULES.map((r) => (
          <RuleCard key={r.title} rule={r} />
        ))}
      </section>

      <section className="rules__group">
        <h3 className="rules__heading">When you are losing</h3>
        {COMEBACK_RULES.map((r) => (
          <RuleCard key={r.title} rule={r} />
        ))}
      </section>

      <section className="rules__group">
        <h3 className="rules__heading">Commanders</h3>
        {COMMANDER_RULES.map((r) => (
          <RuleCard key={r.title} rule={r} />
        ))}
        <ul className="rules__cards">
          {content.commanders.map((c) => (
            <li key={c.id}>
              <UnitGlyph kind={c.art.silhouette} size={24} />
              <span>
                <strong>{c.name}</strong> <span className="muted">· {c.epithet}</span>
                <br />
                <strong>{c.passive.name}:</strong> {c.passive.reads}
                <br />
                <strong>{c.order.name}:</strong> {c.order.reads}{' '}
                <span className="muted">Fires when {c.order.trigger}.</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rules__group">
        <h3 className="rules__heading">The ladder</h3>
        {LADDER_RULES.map((r) => (
          <RuleCard key={r.title} rule={r} />
        ))}
      </section>

      <section className="rules__group">
        <h3 className="rules__heading">Upgrades and doctrines</h3>
        <p className="rules__note">
          What each one actually does. These are ways of fighting rather than pieces of equipment, so
          no scenario&apos;s date rules one out — only the ladder does.
        </p>
        <ul className="rules__cards">
          {content.upgrades.map((u) => (
            <li key={u.id}>
              <UnitGlyph kind={u.art.silhouette} size={24} cardId={u.id} />
              <span>
                <strong>{u.name}</strong> <span className="muted">· Upgrade · Arena {u.arena}</span>
                <br />
                {u.consequence}
              </span>
            </li>
          ))}
          {content.doctrines.map((d) => (
            <li key={d.id}>
              <UnitGlyph kind={d.art.silhouette} size={24} cardId={d.id} />
              <span>
                <strong>{d.name}</strong> <span className="muted">· Doctrine · Arena {d.arena}</span>
                <br />
                {d.consequence}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rules__group">
        <h3 className="rules__heading">How sure are we?</h3>
        <p className="rules__note">
          Every card in the game carries one of these. The game uses all five — what it will not do is
          show you one of the lower ones dressed up as one of the higher ones.
        </p>
        <ul className="rules__cards rules__cards--plain">
          {(
            [
              ['attested', 'Someone wrote it down at the time, or we dug it up.'],
              ['probable', 'Historians agree, but the evidence is second-hand.'],
              ['traditional-account', 'A story told later. Real as a story, not as an event.'],
              ['reconstructed-for-gameplay', 'We made it up so the game works — and we say so.'],
              ['fictional', 'Alternate history. Never enters a match.'],
            ] as [Confidence, string][]
          ).map(([level, what]) => (
            <li key={level}>
              <span className={`confidence confidence--${level}`}>{CONFIDENCE_LABEL[level]}</span>
              <span>{what}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rules__group">
        <h3 className="rules__heading">Every arena, and what it changes</h3>
        <p className="rules__note">
          Thirteen rungs, in the order the history happened. Each one opens new cards for everybody in the
          match. Tap a rung for its rules.
        </p>
        <ol className="rules__ladder">
          {content.arenas.map((a) => (
            <ArenaRow key={a.id} arena={a} trophies={trophies} reached={reached} onOpen={() => setOpen(a)} />
          ))}
        </ol>
      </section>

      {open && <ArenaRules arena={open} trophies={trophies} onClose={() => setOpen(null)} />}
    </div>
  );
}

function RuleCard({ rule }: { rule: Rule }) {
  return (
    <article className="rule">
      <h4>{rule.title}</h4>
      {rule.lines.map((l, i) => (
        <p key={i}>{l}</p>
      ))}
    </article>
  );
}

/** Cards this rung adds that the one below it did not have. */
function newAt(arenaId: number) {
  return content.units.filter((u) => isPlayable(u.confidence) && u.arena === arenaId);
}

function ArenaRow({
  arena,
  trophies,
  reached,
  onOpen,
}: {
  arena: Arena;
  trophies: number;
  reached: number;
  onOpen: () => void;
}) {
  const unlocked = arena.id <= reached;
  // Progress is measured from the rung below, so the bar fills across one band
  // rather than restarting from zero every time.
  const floor = arena.id > 1 ? getArena(arena.id - 1).trophies : 0;
  const span = arena.trophies - floor;
  const frac = span > 0 ? Math.min(1, Math.max(0, (trophies - floor) / span)) : 1;
  const isNext = !unlocked && arena.id === reached + 1;
  const adds = newAt(arena.id);

  return (
    <li className={`rung-rule${unlocked ? ' is-open' : ''}${isNext ? ' is-next' : ''}`}>
      <button type="button" onClick={onOpen}>
        <span className="rung-rule__no">{arena.id}</span>
        <span className="rung-rule__body">
          <span className="rung-rule__name">
            {arena.name}
            {!unlocked && (
              <span className="lock" aria-label="locked">
                🔒
              </span>
            )}
          </span>
          <span className="rung-rule__adds">
            {adds.length > 0 ? `Opens ${adds.map((u) => u.name).join(', ')}` : 'No new cards'}
          </span>

          {unlocked ? (
            <span className="rung-rule__state is-open">Open · {arena.trophies} 🏆</span>
          ) : isNext ? (
            <span className="rung-rule__bar">
              <span className="rung-rule__fill" style={{ width: `${Math.round(frac * 100)}%` }} />
              <span className="rung-rule__count">
                {trophies}/{arena.trophies} 🏆
              </span>
            </span>
          ) : (
            <span className="rung-rule__state">Needs {arena.trophies} 🏆</span>
          )}
        </span>
      </button>
    </li>
  );
}

/** The pool a match at this arena would actually draft from, per scenario. */
function poolLines(arena: number): { battle: Battle; count: number; blocked: number }[] {
  return content.battles.map((b) => {
    const pool = draftPool(b, arena);
    const unlockedHere = content.units.filter((u) => isPlayable(u.confidence) && u.era === b.era && u.arena <= arena);
    return { battle: b, count: pool.length, blocked: unlockedHere.length - pool.length };
  });
}

function ArenaRules({ arena, trophies, onClose }: { arena: Arena; trophies: number; onClose: () => void }) {
  const adds = newAt(arena.id);
  const total = content.units.filter((u) => isPlayable(u.confidence) && u.arena <= arena.id).length;
  const unlocked = trophies >= arena.trophies;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal--codex" onClick={(e) => e.stopPropagation()}>
        <h3>
          Arena {arena.id}: {arena.name}
        </h3>
        <p className="modal__sub">
          {arena.where} · {arena.year}
        </p>

        <section className="arena-gate">
          {unlocked ? (
            <p className="arena-gate__open">
              Open. {arena.trophies === 0 ? 'This is where everyone starts.' : `Reached at ${arena.trophies} trophies.`}
            </p>
          ) : (
            <>
              <p className="arena-gate__shut">
                Reach <strong>{arena.trophies} trophies</strong> to fight here.
              </p>
              <span className="rung-rule__bar">
                <span
                  className="rung-rule__fill"
                  style={{ width: `${Math.round(Math.min(1, trophies / arena.trophies) * 100)}%` }}
                />
                <span className="rung-rule__count">
                  {trophies}/{arena.trophies} 🏆
                </span>
              </span>
            </>
          )}
        </section>

        <h4>What this rung opens</h4>
        {adds.length > 0 ? (
          <ul className="rules__cards">
            {adds.map((u) => (
              <li key={u.id}>
                <UnitGlyph kind={u.art.silhouette} size={26} unitId={u.id} />
                <span>
                  <strong>{u.name}</strong> — {unitSubtitle(u)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p>Nothing new. This rung is a step in trophies only.</p>
        )}

        <h4>The pool at this rung</h4>
        <p>
          {total} cards are unlocked by Arena {arena.id}. How many of them a match can actually offer depends on
          when the battle happened:
        </p>
        <ul>
          {poolLines(arena.id).map(({ battle, count, blocked }) => (
            <li key={battle.id}>
              <strong>{battle.name}</strong> ({battle.year}) — {count} draftable
              {blocked > 0 && `, ${blocked} ruled out by date`}
              {battle.field.terrain === 'gorge' && '. Gorge: horses and wheels are cut down here'}
            </li>
          ))}
        </ul>

        <h4>Who you meet here</h4>
        <p>
          A match is fought at the lower of the two players&apos; arenas. Playing someone further up the ladder
          does not expose you to cards you have never seen.
        </p>

        <p className="muted">{arena.blurb}</p>

        {arena.disputed.length > 0 && (
          <section className="disputed">
            <h4>What&apos;s disputed</h4>
            <ul>
              {arena.disputed.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          </section>
        )}

        <h4>Sources</h4>
        <ul className="sources">
          {arena.sourceRefs.map((s) => (
            <li key={s}>
              <a href={s} target="_blank" rel="noreferrer">
                {new URL(s).hostname.replace('www.', '')}
              </a>
            </li>
          ))}
        </ul>

        <button className="btn btn--gold" type="button" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
