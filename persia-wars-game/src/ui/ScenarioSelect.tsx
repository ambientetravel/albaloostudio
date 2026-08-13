import { content, getEra } from '../content';
import { useGame } from '../state/store';

export function ScenarioSelect() {
  const { chooseBattle, go } = useGame();

  return (
    <div className="screen scenarios">
      <h2>Choose a battle</h2>
      <div className="scenario-list">
        {content.battles.map((battle) => {
          const era = getEra(battle.era);
          const summary = battle.summary;
          return (
            <article key={battle.id} className="scenario">
              <div className="scenario__head">
                <span className="era-chip" style={{ background: era.color, borderColor: era.accent }}>
                  {era.name}
                </span>
                <span className="scenario__year">{battle.year}</span>
              </div>
              <h3>{battle.name}</h3>
              <p className="scenario__site">
                {battle.site}
                {battle.onIranianSoil && <span className="soil"> · Fought on Iranian soil</span>}
              </p>
              <p className="scenario__vs">
                {battle.opponents.a} <span className="vs">×</span> {battle.opponents.b}
              </p>
              <p className="scenario__summary">{summary}</p>
              <p className="scenario__outcome">
                <strong>What really happened: </strong>
                {battle.victor}
              </p>
              <button className="btn btn--gold" type="button" onClick={() => chooseBattle(battle.id)}>
                PLAY THIS BATTLE
              </button>
            </article>
          );
        })}
      </div>
      <button className="btn btn--ghost" type="button" onClick={() => go('lobby')}>
        Back
      </button>
    </div>
  );
}
