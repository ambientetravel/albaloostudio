import { dossierFor, getBattle, getMission, getUnit, kingsById } from '../content';
import { winnerOf } from '../sim/match';
import type { Side } from '../sim/types';
import { useGame } from '../state/store';
import { UnitGlyph } from './UnitGlyph';

export function Result() {
  const {
    reading,
    mode,
    match,
    battleId,
    matchState,
    missionId,
    lastMissionReward,
    lastUnlocked,
    lastRewards,
    rematch,
    go,
    conn,
    campaign,
  } = useGame();

  // A `choice` mission finishes without a match at all, so the mission result
  // has to be able to stand on its own.
  const mission = missionId ? getMission(missionId) : null;
  const counter = campaign.counterHistory;
  const missionDone = mission
    ? (counter ? campaign.counterCompleted : campaign.completed).includes(mission.id)
    : false;
  const dossier = mission ? dossierFor(mission.id) : null;
  if (mission && !matchState) return <MissionOutcome />;
  if (!matchState || !battleId) return null;

  const battle = getBattle(battleId);
  const summary = reading === 'older' ? battle.summaryOlder : battle.summary;
  const online = mode === 'online';
  const mySide: Side = online && match ? match.you : 'a';
  const theirSide: Side = mySide === 'a' ? 'b' : 'a';
  const winner = winnerOf(matchState);

  // Side 'a' always plays the side listed first in the scenario, so the game's
  // winner and history's winner are directly comparable.
  const matchedHistory = winner !== 'draw' && winner === battle.victorSide;

  // A mission is judged on its objective. Mission 10 is won by getting the army
  // out, which can and should read as a win on a scoreline that says otherwise.
  const held = mission?.objective === 'survive' && missionDone;
  const headline = held
    ? 'You got them out'
    : mission && missionDone
      ? 'Mission complete'
      : mission
        ? 'Not this time'
        : winner === 'draw'
          ? 'A draw'
          : winner === mySide
            ? 'You won'
            : 'You lost';

  const unlockedCount = lastUnlocked.battles.length + lastUnlocked.kings.length + lastUnlocked.units.length;

  return (
    <div className="screen result">
      <h2 className={`result__headline winner-${winner === mySide ? 'me' : 'them'}`}>{headline}</h2>

      <p className="result__score">
        <strong>{matchState.score[mySide]}</strong>
        <span> – </span>
        <strong>{matchState.score[theirSide]}</strong>
        <span className="result__score-note">
          {' '}
          in {matchState.history.length} round{matchState.history.length === 1 ? '' : 's'} · first to{' '}
          {/* The match's own target, not the ranked constant — a campaign
              mission is shorter and said so on the way in. */}
          {matchState.winsNeeded}
        </span>
      </p>

      {/* Round by round, so a close match reads as close and a sweep reads as one. */}
      <ol className="round-tape">
        {matchState.history.map((r) => (
          <li
            key={r.round}
            className={r.winner === 'draw' ? 'is-draw' : r.winner === mySide ? 'is-mine' : 'is-theirs'}
          >
            <span className="round-tape__no">{r.round}</span>
            <span className="round-tape__mark">
              {r.winner === 'draw' ? '–' : r.winner === mySide ? '✓' : '✕'}
            </span>
          </li>
        ))}
      </ol>

      {mission && (
        <p className="result__objective">
          {mission.name} ·{' '}
          {mission.objective === 'survive'
            ? 'take one round and your army lives'
            : `first to ${mission.winsNeeded}`}
        </p>
      )}

      {lastMissionReward && (
        <section className="mission-reward">
          <h3>Unlocked</h3>
          <p>
            <strong>{lastMissionReward.name}</strong>
            <span className="muted"> · {lastMissionReward.kind}</span>
          </p>
          <p className="muted mission-reward__note">
            Campaign rewards give you more to choose from. They never make anything you already have
            hit harder.
          </p>
        </section>
      )}

      <ul className="reward-strip">
        <li className={lastRewards.trophies >= 0 ? 'good' : 'bad'}>
          <span aria-hidden="true">🏆</span>
          {lastRewards.trophies >= 0 ? '+' : ''}
          {lastRewards.trophies}
        </li>
        <li>
          <span aria-hidden="true">🪙</span>+{lastRewards.coins}
        </li>
        <li>
          <span aria-hidden="true">🃏</span>+{lastRewards.cards.length}
        </li>
      </ul>

      {/*
        The educational payload. The game's outcome never overwrites the real one —
        whichever way the match went, the true result is stated here.

        In Counter-History the framing inverts: the player is on the side that
        lost, so a WIN is the alternate history and has to be labelled as one
        (v0.1 §4). The documented outcome is stated either way.
      */}
      <section
        className={`truth ${counter ? 'is-counter' : matchedHistory ? 'is-true' : 'is-reshaped'}`}
      >
        <h3>{counter ? 'Alternate history' : 'True, or reshaped?'}</h3>
        <p className="truth__verdict">
          {counter
            ? winner === mySide
              ? 'You changed it. Media did not win this war — this is a story about what did not happen.'
              : 'It went the way it really went.'
            : matchedHistory
              ? 'Your battle ended the way the real one did.'
              : 'You reshaped it. History went the other way — and it still does.'}
        </p>
        <p className="truth__real">
          <strong>What really happened: </strong>
          {battle.victor}
        </p>
        <p className="truth__summary">{summary}</p>
        <ul className="teaches">
          {battle.teaches.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      </section>

      {/* v0.1 §5.1 step 6 — the optional "what we know" card, after the mission
          rather than before it, so it lands on a player who now has a reason to
          care. It is the dossier's plain-language field, not a second essay. */}
      {dossier && (
        <section className="what-we-know">
          <h3>What we actually know</h3>
          <p>{dossier.whatWeKnow}</p>
          {dossier.mustNotClaim.length > 0 && (
            <>
              <h4>And what people get wrong</h4>
              <ul>
                {dossier.mustNotClaim.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {unlockedCount > 0 && (
        <section className="unlocks">
          <h3>
            Unlocked · {unlockedCount} new codex card{unlockedCount === 1 ? '' : 's'}
          </h3>
          <ul className="unlock-list">
            {lastUnlocked.battles.map((id) => (
              <li key={id} className="unlock unlock--battle">
                {getBattle(id).name}
              </li>
            ))}
            {lastUnlocked.kings.map((id) => {
              const k = kingsById.get(id);
              return k ? (
                <li key={id} className="unlock unlock--king">
                  {k.name}
                </li>
              ) : null;
            })}
            {lastUnlocked.units.map((id) => (
              <li key={id} className="unlock unlock--unit">
                <UnitGlyph kind={getUnit(id).art.silhouette} size={22} unitId={id} />
                {getUnit(id).name}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="result__actions">
        <button className="btn btn--gold" type="button" onClick={rematch} disabled={online && conn !== 'online'}>
          {online ? 'FIND ANOTHER MATCH' : 'PLAY AGAIN'}
        </button>
        <button className="btn btn--teal" type="button" onClick={() => go('codex')}>
          Open the codex
        </button>
        {mission ? (
          <button className="btn btn--teal" type="button" onClick={() => go('campaign')}>
            Back to the book
          </button>
        ) : null}
        <button className="btn btn--ghost" type="button" onClick={() => go('lobby')}>
          Lobby
        </button>
      </div>
    </div>
  );
}

/** A `choice` mission has no battle to report, only what the decision bought. */
function MissionOutcome() {
  const { missionId, lastMissionReward, campaign, go } = useGame();
  if (!missionId) return null;
  const mission = getMission(missionId);
  const choice = mission.choices?.find((c) => c.id === campaign.choices[mission.id]);

  return (
    <div className="screen result">
      <h2 className="result__headline winner-me">Decided</h2>
      <p className="result__objective">{mission.name}</p>

      {choice && (
        <div className="scroll">
          <span className="scroll__cap scroll__cap--l" aria-hidden="true" />
          <p>
            <strong>{choice.label}.</strong> {choice.reads}
          </p>
          <span className="scroll__cap scroll__cap--r" aria-hidden="true" />
        </div>
      )}

      {lastMissionReward && (
        <section className="mission-reward">
          <h3>Unlocked</h3>
          <p>
            <strong>{lastMissionReward.name}</strong>
            <span className="muted"> · {lastMissionReward.kind}</span>
          </p>
        </section>
      )}

      <div className="result__actions">
        <button className="btn btn--gold" type="button" onClick={() => go('campaign')}>
          Back to the book
        </button>
      </div>
    </div>
  );
}
