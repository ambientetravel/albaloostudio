import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { getArena, getBattle, getCommander, getDoctrine, getUnit, getUpgrade } from '../content';
import { arenaForTrophies } from '../game/progression';
import { BattleCanvas } from '../render/BattleCanvas';
import { thinkTime } from '../sim/ai';
import { deficitOf, finalClash, holdsRally } from '../sim/match';
import {
  ROUNDS_MAX,
  TIER_NAME,
  WINS_NEEDED,
  tierOf,
  type Ledger,
  type OfferCard,
  type Side,
  type Tier,
} from '../sim/roundCore.ts';
import { useGame } from '../state/store';
import { ArenaIntro } from './ArenaIntro';
import { Avatar } from './Avatar';
import { UnitCard } from './UnitCard';
import { UnitGlyph } from './UnitGlyph';

const SPEEDS = [1, 2, 4];
const ROMAN = ['I', 'II', 'III', 'IV'] as const;
/** How long the round banner holds before the next offer opens. */
const BANNER_MS = 2200;

/**
 * The whole contest, on one screen.
 *
 * Up to seven rounds, first to four. The offer slides up **over** the
 * battlefield rather than replacing it (Concept v0.2 §8) — with seven rounds
 * you must never leave the field, or the match becomes a slideshow of screen
 * transitions.
 *
 * The field itself is only a canvas while a round is being fought. During the
 * offer it is the two ranks standing in formation, which is both cheaper and
 * more legible than a paused simulation.
 */
export function MatchScreen() {
  const {
    mode,
    battleId,
    matchState,
    log,
    match,
    profile,
    aiOpponent,
    trophies,
    reading,
    turnDeadline,
    makePick,
    runAiPick,
    finishRound,
    advanceRound,
    finishMatch,
    leaveMatch,
    useRally,
  } = useGame();

  const [speed, setSpeed] = useState(1);
  const [introDone, setIntroDone] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);

  const online = mode === 'online';
  const mySide: Side = online && match ? match.you : 'a';
  const theirSide: Side = mySide === 'a' ? 'b' : 'a';
  const phase = matchState?.phase ?? 'offer';

  // The computer chooses at the same time you do, and hesitates like a person.
  useEffect(() => {
    if (mode !== 'ai' || !matchState || phase !== 'offer') return;
    if (matchState.picked.b !== null) return;
    const delay = thinkTime(matchState.round, matchState.seed, aiOpponent?.skill ?? 0.8);
    const timer = setTimeout(runAiPick, delay);
    return () => clearTimeout(timer);
  }, [mode, matchState, phase, aiOpponent, runAiPick]);

  // The round banner clears itself, so a match never waits on a tap it does not need.
  useEffect(() => {
    if (phase !== 'roundResult') return;
    const timer = setTimeout(advanceRound, BANNER_MS);
    return () => clearTimeout(timer);
  }, [phase, advanceRound]);

  // Online rounds are on a server clock; show it ticking so nobody wonders.
  useEffect(() => {
    if (!online || !turnDeadline || phase !== 'offer') {
      setSecondsLeft(null);
      return;
    }
    const tick = () => setSecondsLeft(Math.max(0, Math.ceil((turnDeadline - Date.now()) / 1000)));
    tick();
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, [online, turnDeadline, phase]);

  if (!matchState || !battleId) return null;
  const battle = getBattle(battleId);
  // The ground you fight on is your rung of the ladder, not the scenario.
  const arena = getArena(online ? matchState.arena : arenaForTrophies(trophies));

  const nameFor = (s: Side): string => {
    if (online && match) return s === match.you ? (profile?.name ?? 'You') : match.opponent.name;
    if (s === 'a') return profile?.name ?? 'You';
    return aiOpponent?.name ?? 'Computer';
  };
  const avatarFor = (s: Side): number => {
    if (online && match) return s === match.you ? (profile?.avatar ?? 0) : match.opponent.avatar;
    if (s === 'a') return profile?.avatar ?? 0;
    return aiOpponent?.avatar ?? 5;
  };
  /** The computer is never passed off as a person. */
  const isBot = (s: Side): boolean => !online && s === 'b';

  const chosen = matchState.picked[mySide];
  const waiting = phase === 'offer' && chosen !== null;
  const lastRound = matchState.history[matchState.history.length - 1];

  return (
    <div className="screen match">
      <AnimatePresence>
        {!introDone && <ArenaIntro key="intro" arena={arena} onDone={() => setIntroDone(true)} />}
      </AnimatePresence>

      <ScoreRow
        matchRound={matchState.round}
        score={matchState.score}
        mySide={mySide}
        names={{ a: nameFor('a'), b: nameFor('b') }}
        avatars={{ a: avatarFor('a'), b: avatarFor('b') }}
        bot={{ a: isBot('a'), b: isBot('b') }}
        commanders={matchState.commanders}
        final={finalClash(matchState)}
      />

      <div className="match__field">
        <LedgerBand ledger={matchState.ledgers[theirSide]} side={theirSide} where="top" />

        <div className="match__ground">
          {phase === 'battle' || phase === 'roundResult' ? (
            log && introDone ? (
              <BattleCanvas
                key={matchState.round}
                log={log}
                battle={battle}
                arenaId={arena.id}
                speed={speed}
                onFinished={finishRound}
              />
            ) : (
              <div className="battle-canvas" />
            )
          ) : (
            <Offer
              offer={matchState.offers[mySide]}
              ledger={matchState.ledgers[mySide]}
              round={matchState.round}
              reading={reading}
              side={mySide}
              chosen={chosen}
              waiting={waiting}
              secondsLeft={secondsLeft}
              onPick={makePick}
              rally={holdsRally(matchState, mySide)}
              deficit={deficitOf(matchState, mySide)}
              onRally={useRally}
            />
          )}
        </div>

        <LedgerBand ledger={matchState.ledgers[mySide]} side={mySide} where="bottom" />
      </div>

      <AnimatePresence>
        {phase === 'roundResult' && lastRound && (
          <motion.div
            className="round-banner"
            key={lastRound.round}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            onClick={advanceRound}
          >
            <span className="round-banner__label">Round {lastRound.round}</span>
            <strong>
              {lastRound.winner === 'draw'
                ? 'Nobody broke'
                : lastRound.winner === mySide
                  ? 'You take the round'
                  : `${nameFor(theirSide)} takes the round`}
            </strong>
            <span className="round-banner__score">
              {matchState.score[mySide]} – {matchState.score[theirSide]}
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="match__controls">
        {phase === 'battle' && (
          <>
            <span>Speed</span>
            {SPEEDS.map((s) => (
              <button
                key={s}
                type="button"
                className={`chip${speed === s ? ' is-on' : ''}`}
                onClick={() => setSpeed(s)}
              >
                {s}×
              </button>
            ))}
            <button type="button" className="chip" onClick={finishRound}>
              Skip
            </button>
          </>
        )}
        {phase === 'offer' && (
          <span className="match__hint">
            {battle.name} · Arena {arena.id}: {arena.name}
          </span>
        )}
        {phase === 'over' && (
          <button type="button" className="btn btn--gold btn--small" onClick={finishMatch}>
            See the result
          </button>
        )}
        {online && phase === 'offer' && (
          <button className="btn btn--ghost btn--small" type="button" onClick={leaveMatch}>
            Leave
          </button>
        )}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------- pieces

function ScoreRow({
  matchRound,
  score,
  mySide,
  names,
  avatars,
  bot,
  commanders,
  final,
}: {
  matchRound: number;
  score: Record<Side, number>;
  mySide: Side;
  names: Record<Side, string>;
  avatars: Record<Side, number>;
  bot: Record<Side, boolean>;
  commanders: Record<Side, string>;
  final: boolean;
}) {
  const theirSide: Side = mySide === 'a' ? 'b' : 'a';
  return (
    <header className="score-row">
      <Corner
        name={names[theirSide]}
        avatar={avatars[theirSide]}
        bot={bot[theirSide]}
        side={theirSide}
        commander={commanders[theirSide]}
      />
      <div className="score-row__middle">
        <span className={`score-row__round${final ? ' is-final' : ''}`}>
          {final ? 'FINAL CLASH' : `Round ${matchRound} of ${ROUNDS_MAX}`}
        </span>
        <div className="score-row__pips">
          <Pips won={score[theirSide]} side={theirSide} />
          <span className="score-row__dash">–</span>
          <Pips won={score[mySide]} side={mySide} />
        </div>
        <span className="score-row__goal">first to {WINS_NEEDED}</span>
      </div>
      <Corner
        name={names[mySide]}
        avatar={avatars[mySide]}
        bot={bot[mySide]}
        side={mySide}
        commander={commanders[mySide]}
      />
    </header>
  );
}

function Corner({
  name,
  avatar,
  bot,
  side,
  commander,
}: {
  name: string;
  avatar: number;
  bot: boolean;
  side: Side;
  commander: string;
}) {
  const c = getCommander(commander);
  return (
    <div className={`score-row__who side-${side}`}>
      <Avatar index={avatar} size={26} />
      <span className="score-row__name">{name}</span>
      {/* Who they are leading with decides how they will draft — worth knowing
          before you choose your own card, so it sits on the score row. */}
      <span className="score-row__commander" title={`${c.name} · ${c.passive.reads}`}>
        {c.name}
      </span>
      {bot && <span className="bot-tag">cpu</span>}
    </div>
  );
}

function Pips({ won, side }: { won: number; side: Side }) {
  return (
    <span className={`pips side-${side}`}>
      {Array.from({ length: WINS_NEEDED }, (_, i) => (
        <span key={i} className={`pip${i < won ? ' is-won' : ''}`} />
      ))}
    </span>
  );
}

/**
 * One side's Army Ledger. Persists across rounds — this is the escalation the
 * whole format is built around, so it stays on screen at all times.
 *
 * A squad shows its rank as a numeral and its traits as pips, because a trait
 * is not a rank and must not look like one.
 */
function LedgerBand({ ledger, side, where }: { ledger: Ledger; side: Side; where: 'top' | 'bottom' }) {
  return (
    <div className={`ledger-band ledger-band--${where}`}>
      <ul className={`ledger ledger--${where} side-${side}`}>
        <AnimatePresence>
          {ledger.squads.map((entry) => (
            <motion.li
              key={entry.unitId}
              layout
              initial={{ scale: 0.3, opacity: 0, y: where === 'top' ? -16 : 16 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              transition={{ type: 'spring', stiffness: 460, damping: 24 }}
              title={`${getUnit(entry.unitId).name}${entry.traits.length ? ` · ${entry.traits.map((t) => getUpgrade(t).name).join(', ')}` : ''}`}
            >
              <UnitGlyph kind={getUnit(entry.unitId).art.silhouette} size={26} unitId={entry.unitId} />
              {entry.tier > 1 && <span className="ledger__tier">{ROMAN[entry.tier - 1]}</span>}
              {entry.traits.length > 0 && (
                <span className="ledger__traits" aria-hidden="true">
                  {entry.traits.map((t) => (
                    <span key={t} className="ledger__trait" />
                  ))}
                </span>
              )}
            </motion.li>
          ))}
        </AnimatePresence>
        {ledger.squads.length === 0 && <li className="ledger__empty">no squads yet</li>}
      </ul>
      {ledger.doctrines.length > 0 && (
        <ul className="doctrine-strip">
          {ledger.doctrines.map((d) => (
            <li key={d}>{getDoctrine(d).name}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Offer({
  offer,
  ledger,
  round,
  reading,
  side,
  chosen,
  waiting,
  secondsLeft,
  onPick,
  rally,
  deficit,
  onRally,
}: {
  offer: OfferCard[];
  ledger: Ledger;
  round: number;
  reading: 'kid' | 'older';
  side: Side;
  chosen: OfferCard | null;
  waiting: boolean;
  secondsLeft: number | null;
  onPick: (id: string) => void;
  rally: boolean;
  deficit: number;
  onRally: () => void;
}) {
  return (
    <motion.div
      className="offer-sheet"
      initial={{ y: 40, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
    >
      <div className="offer-sheet__head">
        <span>{waiting ? 'Waiting for your opponent…' : 'Take one'}</span>
        {/* Comeback A, stated rather than slipped in. A wider offer with no
            explanation reads as luck; labelled, it reads as a rule. */}
        {deficit > 0 && offer.length > 3 && (
          <span className="behind-tag">
            {offer.length} cards — you are {deficit} behind
          </span>
        )}
        {secondsLeft !== null && (
          <span className={`turn-timer${secondsLeft <= 5 ? ' is-urgent' : ''}`}>{secondsLeft}s</span>
        )}
      </div>

      {/* The comeback widens this to four or five cards, so the grid has to be
          told how many it is laying out — three across only works for three. */}
      <div
        className={`offer${waiting ? ' is-waiting' : ''}${offer.length > 3 ? ' offer--wide' : ''}`}
        data-count={offer.length}
      >
        {offer.map((card) => (
          <div
            key={card.id}
            className={`offer__slot${chosen?.id === card.id ? ' is-chosen' : ''}`}
          >
            {card.kind === 'unit' ? (
              <UnitSlot
                card={card}
                ledger={ledger}
                reading={reading}
                side={side}
                waiting={waiting}
                onPick={onPick}
                wide={offer.length > 3}
              />
            ) : (
              <RuleSlot
                card={card}
                reading={reading}
                side={side}
                waiting={waiting}
                onPick={onPick}
                wide={offer.length > 3}
              />
            )}
          </div>
        ))}
      </div>
      {/* Comeback B. Shown only when held, and it costs the whole thing to use —
          the player decides when, which is what makes it agency rather than
          charity. The opponent is told it was spent. */}
      {rally && !waiting && (
        <button type="button" className="btn btn--rally" onClick={onRally}>
          ⟳ RALLY — draw a new hand
        </button>
      )}
      <p className="offer-sheet__note">
        {ledger.squads.length === 0
          ? 'Everything you take stays for the whole match.'
          : round >= 3
            ? 'A rank makes a squad stronger. A trait changes how it fights.'
            : 'A card you already have gets stronger instead of joining twice.'}
      </p>
    </motion.div>
  );
}

function UnitSlot({
  card,
  ledger,
  reading,
  side,
  waiting,
  onPick,
  wide,
}: {
  card: OfferCard;
  ledger: Ledger;
  reading: 'kid' | 'older';
  side: Side;
  waiting: boolean;
  onPick: (id: string) => void;
  wide: boolean;
}) {
  const owned = tierOf(ledger, card.id);
  const next = (owned === 0 ? 1 : owned + 1) as Tier;
  return (
    <>
      <UnitCard
        unit={getUnit(card.id)}
        reading={reading}
        side={side}
        variant="compact"
        glyphSize={wide ? 30 : 46}
        disabled={waiting}
        onClick={() => !waiting && onPick(card.id)}
      />
      <span className={`offer__tier${owned > 0 ? ' is-upgrade' : ''}`}>
        {owned > 0 ? `→ ${TIER_NAME[next - 1]} ${ROMAN[next - 1]}` : TIER_NAME[0]}
      </span>
    </>
  );
}

/**
 * An Upgrade or a Doctrine.
 *
 * Deliberately does not look like a unit card: no attack, no armour, no health.
 * What it shows instead is the `consequence` line — v0.1 §6.4 requires a stated
 * consequence and forbids a bare percentage, and that line is the whole card.
 */
function RuleSlot({
  card,
  reading,
  side,
  waiting,
  onPick,
  wide,
}: {
  card: OfferCard;
  reading: 'kid' | 'older';
  side: Side;
  waiting: boolean;
  onPick: (id: string) => void;
  wide: boolean;
}) {
  const def = card.kind === 'upgrade' ? getUpgrade(card.id) : getDoctrine(card.id);
  const blurb = reading === 'older' ? def.blurbOlder : def.blurb;
  return (
    <>
      <button
        type="button"
        className={`unit-card unit-card--compact rule-card rule-card--${card.kind} side-${side}${waiting ? ' is-disabled' : ''}`}
        disabled={waiting}
        onClick={() => !waiting && onPick(card.id)}
      >
        <div className="unit-card__art">
          <UnitGlyph kind={def.art.silhouette} size={wide ? 28 : 40} cardId={def.id} />
        </div>
        <div className="unit-card__text">
          <h3>{def.name}</h3>
          <p className="unit-card__class">{card.kind === 'upgrade' ? 'Upgrade' : 'Doctrine'}</p>
          <p className="rule-card__consequence">{def.consequence}</p>
          <p className="rule-card__blurb">{blurb}</p>
        </div>
      </button>
      <span className="offer__tier is-rule">
        {card.kind === 'upgrade'
          ? card.target
            ? `→ ${getUnit(card.target).name}`
            : 'no squad for it'
          : 'whole army'}
      </span>
    </>
  );
}
