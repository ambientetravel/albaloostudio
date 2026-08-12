import { content, dossierFor, dossiers, getMission } from '../content';
import type { Mission } from '../content/types';
import {
  bookFinished,
  bookProgress,
  capitalProgress,
  chapterOf,
  isComplete,
  isUnlocked,
  nextMission,
} from '../game/campaign';
import { useState } from 'react';
import { useGame } from '../state/store';

const CHAPTER_TITLE: Record<1 | 2, string> = {
  1: 'Chapter One · King of Anshan',
  2: 'Chapter Two · The Median War',
};

/**
 * The Chronicle — Book One, Rise of Cyrus.
 *
 * Fourteen missions in two chapters, unlocked strictly in order. A book that can
 * be played out of sequence cannot tell a story, and this is a story before it
 * is a ladder.
 *
 * The banner at the top is not decoration. v0.1 §11 requires the chapter to be
 * presented as a careful dramatic reconstruction rather than as a claim that
 * fourteen documented engagements happened — so the screen says so before the
 * player reads a single mission name.
 */
export function Campaign() {
  const { campaign, openMission, toggleCounterHistory, go } = useGame();
  const progress = bookProgress(campaign);
  const next = nextMission(campaign);
  const finished = bookFinished(campaign);
  const counter = campaign.counterHistory;

  return (
    <div className={`screen campaign${counter ? ' is-counter' : ''}`}>
      <h2>{counter ? 'The Median War' : 'Rise of Cyrus'}</h2>
      <p className="campaign__book">
        {counter ? 'Counter-History · ' : 'Book One · '}
        {progress.done} of {progress.total} missions
      </p>

      {counter ? (
        <p className="campaign__warning campaign__warning--counter">
          <strong>This is not what happened.</strong> You are playing the Median side of a war Media
          lost. Anything you win here is <strong>alternate history</strong>, and every result will
          tell you what the record actually says.
        </p>
      ) : (
        <p className="campaign__warning">
          This book is a <strong>dramatic reconstruction</strong>. The framework of the revolt is on
          the record; almost none of these scenes are. Each mission says how much of it is known.
        </p>
      )}

      {/* v0.1 §4 — the other side opens only after the documented path is done,
          so nobody meets the alternate version before the real one. */}
      {finished && (
        <button
          type="button"
          className={`btn btn--counter${counter ? ' is-on' : ''}`}
          onClick={toggleCounterHistory}
        >
          {counter ? 'Back to the history' : 'Play it the other way — Counter-History'}
        </button>
      )}

      {([1, 2] as const).map((chapter) => (
        <section key={chapter} className="campaign__chapter">
          <h3>{CHAPTER_TITLE[chapter]}</h3>
          <ol className="mission-list">
            {chapterOf(chapter).map((m) => (
              <MissionRow
                key={m.id}
                mission={m}
                done={isComplete(m, campaign)}
                open={isUnlocked(m, campaign)}
                isNext={next?.id === m.id}
                onOpen={() => openMission(m.id)}
              />
            ))}
          </ol>
        </section>
      ))}

      <button className="btn btn--teal" type="button" onClick={() => go('capital')}>
        Your capital · {Math.round(capitalProgress(campaign) * 100)}%
      </button>
      <button className="btn btn--ghost" type="button" onClick={() => go('lobby')}>
        Back
      </button>
    </div>
  );
}

function MissionRow({
  mission,
  done,
  open,
  isNext,
  onOpen,
}: {
  mission: Mission;
  done: boolean;
  open: boolean;
  isNext: boolean;
  onOpen: () => void;
}) {
  return (
    <li className={`mission${done ? ' is-done' : ''}${isNext ? ' is-next' : ''}${open ? '' : ' is-locked'}`}>
      <button type="button" onClick={onOpen} disabled={!open}>
        <span className="mission__no">{done ? '✓' : open ? mission.number : '🔒'}</span>
        <span className="mission__body">
          <span className="mission__name">{mission.name}</span>
          <span className="mission__kind">
            {mission.objective === 'choice'
              ? 'A decision, not a battle'
              : mission.objective === 'survive'
                ? `Get your army out · first to ${mission.winsNeeded}`
                : `First to ${mission.winsNeeded} rounds`}
          </span>
        </span>
      </button>
    </li>
  );
}

/**
 * The mission's setup card. v0.1 §5.1 step 2: fifteen to thirty seconds of
 * history, and always skippable — a campaign that makes you read is a campaign
 * you stop reading.
 */
export function MissionBrief() {
  const { missionId, reading, campaign, startMission, takeMissionChoice, go } = useGame();
  const [showDossier, setShowDossier] = useState(false);
  if (!missionId) return null;
  const mission = getMission(missionId);
  const taken = campaign.choices[mission.id];
  const dossier = dossierFor(mission.id);

  return (
    <div className="screen mission-brief">
      <p className="mission-brief__chapter">
        {CHAPTER_TITLE[mission.chapter]} · {mission.number} of 14
      </p>
      <h2>{mission.name}</h2>

      <div className="scroll">
        <span className="scroll__cap scroll__cap--l" aria-hidden="true" />
        <p>{mission.setup}</p>
        <span className="scroll__cap scroll__cap--r" aria-hidden="true" />
      </div>

      <section className="mission-brief__teaches">
        <h4>What this one is about</h4>
        <ul>
          {mission.teaches.map((t, i) => (
            <li key={i}>{t}</li>
          ))}
        </ul>
      </section>

      {mission.objective === 'choice' ? (
        <div className="mission-choices">
          {mission.choices?.map((c) => (
            <button
              key={c.id}
              type="button"
              className={`btn btn--teal${taken === c.id ? ' is-on' : ''}`}
              onClick={() => takeMissionChoice(mission.id, c.id)}
            >
              <strong>{c.label}</strong>
              <span>{c.reads}</span>
            </button>
          ))}
        </div>
      ) : (
        <button className="btn btn--gold" type="button" onClick={() => startMission(mission.id)}>
          {mission.objective === 'survive' ? 'HOLD THEM OFF' : 'TAKE THE FIELD'}
        </button>
      )}

      {/*
        How much of this is known, on the mission itself. The dossier flag is
        honest about the work that has not been done yet rather than quietly
        presenting a stub as finished research.
      */}
      <section className="mission-brief__truth">
        <p className="muted">
          {reading === 'older'
            ? 'How far this mission can be trusted:'
            : 'How much of this really happened:'}
        </p>
        <ul className="disputed-list">
          {mission.disputed.map((d, i) => (
            <li key={i}>{d}</li>
          ))}
        </ul>
        {dossier ? (
          <button type="button" className="link" onClick={() => setShowDossier(true)}>
            Read the full dossier
          </button>
        ) : (
          <p className="muted mission-brief__pending">
            The full historical dossier for this mission is still to be written.
          </p>
        )}
        <ul className="sources">
          {mission.sourceRefs.map((src) => (
            <li key={src}>
              <a href={src} target="_blank" rel="noreferrer">
                {new URL(src).hostname.replace('www.', '')}
              </a>
            </li>
          ))}
        </ul>
      </section>

      <button className="btn btn--ghost btn--small" type="button" onClick={() => go('campaign')}>
        Back to the book
      </button>

      {showDossier && dossier && (
        <DossierSheet missionId={mission.id} onClose={() => setShowDossier(false)} />
      )}
    </div>
  );
}

/**
 * The Historical Battle Dossier — v0.1 §14, shown to the player rather than kept
 * in a drawer. `Never present as fact` leads, because it is the field that earns
 * the document: the things that are widely believed, or dramatically convenient,
 * and are not supported.
 */
export function DossierSheet({ missionId, onClose }: { missionId: string; onClose: () => void }) {
  const d = dossierFor(missionId);
  const book = dossiers.book;
  const mission = getMission(missionId);
  if (!d) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal--sheet dossier" onClick={(e) => e.stopPropagation()}>
        <h3>{mission.name}</h3>
        <p className="modal__sub">Historical dossier · {d.reviewStatus.replace('-', ' ')}</p>

        <h4>What we actually know</h4>
        <p>{d.whatWeKnow}</p>

        <dl className="dossier__facts">
          <div>
            <dt>Where</dt>
            <dd>
              {d.location.text} <span className={`confidence confidence--${d.location.confidence}`}>{d.location.confidence.replace(/-/g, ' ')}</span>
            </dd>
          </div>
          <div>
            <dt>Who</dt>
            <dd>{d.combatants}</dd>
          </div>
          <div>
            <dt>When</dt>
            <dd>{book.dateRange.text}</dd>
          </div>
        </dl>

        <h4>Never present as fact</h4>
        <ul className="dossier__never">
          {[...d.mustNotClaim, ...book.mustNotClaim].map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>

        {d.specificEvidence.length > 0 && (
          <>
            <h4>Contemporary evidence</h4>
            <ul>
              {d.specificEvidence.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </>
        )}

        {(d.laterSources ?? []).length > 0 && (
          <>
            <h4>Later sources — treat as later</h4>
            <ul>
              {(d.laterSources ?? []).map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </>
        )}

        <h4>What we changed, and why</h4>
        <ul className="dossier__abstractions">
          {d.abstractions.map((a, i) => (
            <li key={i}>
              <strong>{a.what}.</strong> {a.why}
            </li>
          ))}
        </ul>

        {d.unitArchetypes.length > 0 && (
          <>
            <h4>Plausible units</h4>
            <p className="muted">{d.unitArchetypes.join(' · ')}</p>
          </>
        )}

        <h4>The book's evidence base</h4>
        <p>{book.framework}</p>
        <ul className="sources">
          {book.contemporaryEvidence.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>

        <h4>Handle with care</h4>
        <ul className="dossier__never">
          {book.sensitivities.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>

        <button className="btn btn--gold" type="button" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}

/**
 * The capital. v0.1 §3.3 — the home screen grows from a camp into Pasargadae as
 * the book runs. Narrative and cosmetic only; nothing here is ever read by the
 * simulation, and a test enforces that.
 */
export function Capital() {
  const { campaign, go } = useGame();
  const built = new Set(campaign.capital);

  return (
    <div className="screen capital">
      <h2>Pasargadae</h2>
      <p className="muted">
        It begins as a camp. What gets built here is decided by how far the book runs — and it
        changes nothing about how you fight.
      </p>

      <ol className="capital-list">
        {content.capital
          .slice()
          .sort((a, b) => a.order - b.order)
          .map((piece) => (
            <li key={piece.id} className={built.has(piece.id) ? 'is-built' : 'is-planned'}>
              <span className="capital__mark">{built.has(piece.id) ? '✓' : '—'}</span>
              <span>
                <strong>{piece.name}</strong>
                <br />
                {built.has(piece.id) ? piece.reads : 'Not yet.'}
              </span>
            </li>
          ))}
      </ol>

      <button className="btn btn--ghost" type="button" onClick={() => go('campaign')}>
        Back to the book
      </button>
    </div>
  );
}
