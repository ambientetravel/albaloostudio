import { useState } from 'react';
import { content, getArena, unitsUnlockedAt } from '../content';
import { arenaForTrophies, arenaProgress } from '../game/progression';
import { useGame } from '../state/store';
import { themeFor } from './arenaTheme';
import { CurrencyBar } from './Chrome';
import { SettingsModal } from './SettingsModal';

/**
 * The trophy ladder: all thirteen grounds in the order the empire reached them,
 * what each one unlocks, and where the player currently stands.
 *
 * It doubles as the game's timeline — the rungs are chronological, so scrolling
 * this list is scrolling from Cyrus's small inherited kingdom to Alexander at
 * the Persian Gates.
 */
export function Ladder() {
  const { trophies, bestTrophies, wins, losses } = useGame();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const here = arenaForTrophies(trophies);
  const progress = arenaProgress(trophies);

  return (
    <div className="screen ladder">
      <CurrencyBar onSettings={() => setSettingsOpen(true)} />

      <div className="ladder__head">
        <h2>Trophies</h2>
        <p className="muted">
          {trophies} now · {bestTrophies} best · {wins}W / {losses}L
        </p>
        <div className="trophy-bar">
          <span className="trophy-bar__icon" aria-hidden="true">
            🏆
          </span>
          <span className="trophy-bar__track">
            <span className="trophy-bar__fill" style={{ width: `${Math.round(progress.frac * 100)}%` }} />
            <span className="trophy-bar__text">
              {progress.current}/{progress.target}
            </span>
          </span>
        </div>
      </div>

      <ol className="ladder__list">
        {content.arenas.map((a) => {
          const reached = a.id <= here;
          const current = a.id === here;
          const theme = themeFor(a.slug);
          const unlocks = unitsUnlockedAt(a.id).filter((u) => u.arena === a.id);
          return (
            <li
              key={a.id}
              className={`rung${reached ? ' is-reached' : ''}${current ? ' is-current' : ''}`}
              style={{ borderInlineStartColor: theme.accent }}
            >
              <span className="rung__no" style={{ background: theme.accent }}>
                {a.id}
              </span>
              <span className="rung__body">
                <strong>
                  {a.name}
                  {current && <em className="rung__you">you are here</em>}
                </strong>
                <span className="rung__meta">
                  {a.year} · {a.where}
                </span>
                <span className="rung__meta">
                  {a.trophies} trophies
                  {unlocks.length > 0 && ` · unlocks ${unlocks.map((u) => u.name).join(', ')}`}
                </span>
              </span>
              {!reached && (
                <span className="rung__lock" aria-hidden="true">
                  🔒
                </span>
              )}
            </li>
          );
        })}
      </ol>

      <p className="muted ladder__note">
        The rungs run in the order each place entered the empire&apos;s story, so the ladder is also the timeline —
        from {getArena(1).name} in {getArena(1).year} to {getArena(13).name} in {getArena(13).year}.
      </p>

      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
