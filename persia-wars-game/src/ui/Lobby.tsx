import { useEffect, useState } from 'react';
import { commandersUnlockedAt, content, getArena, getUnit } from '../content';
import { bookProgress } from '../game/campaign';
import { arenaForTrophies, arenaProgress, nextArenaAt } from '../game/progression';
import { useGame } from '../state/store';
import { ArenaStage } from './ArenaStage';
import { Avatar } from './Avatar';
import { formatCount } from './Chrome';
import { Portrait } from './Portrait';
import { SettingsModal } from './SettingsModal';
import { UnitGlyph } from './UnitGlyph';

/**
 * The lobby, built to the supplied mockup: a titled arena plate flanked by two
 * character medallions, two progress bars, the battleground panel, a lore
 * scroll, and one very large BATTLE button.
 */
export function Lobby() {
  const {
    profile,
    trophies,
    wallet,
    deck,
    commander,
    setCommander,
    conn,
    onlineCount,
    wins,
    findMatch,
    startSolo,
    campaign,
    openCampaign,
    go,
  } = useGame();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [browseArena, setBrowseArena] = useState<number | null>(null);

  const currentArena = arenaForTrophies(trophies);
  const shownArena = browseArena ?? currentArena;

  // Browsing ahead is a peek, not a selection. Snap back the moment the player's
  // real arena changes, or winning a promotion leaves the lobby showing the
  // wrong ground indefinitely.
  useEffect(() => {
    setBrowseArena(null);
  }, [currentArena]);

  const arena = getArena(shownArena);
  const progress = arenaProgress(trophies);
  const next = nextArenaAt(trophies);
  const canPlayOnline = conn === 'online';

  const step = (delta: number): void => {
    setBrowseArena(Math.min(content.arenas.length, Math.max(1, shownArena + delta)));
  };

  return (
    <div className="screen lobby">
      {/* --- top bar: identity and purse ------------------------------------ */}
      <div className="topstrip">
        <button className="namepill" type="button" onClick={() => setSettingsOpen(true)}>
          <Avatar index={profile?.avatar ?? 0} size={26} />
          <span>{profile?.name ?? 'Player'}</span>
        </button>
        <span className="purse">
          <span className="purse__item">
            <i aria-hidden="true">💎</i>
            {wallet.gems}
          </span>
          <span className="purse__item">
            <i aria-hidden="true">🪙</i>
            {formatCount(wallet.coins)}
          </span>
          <button className="gear" type="button" onClick={() => setSettingsOpen(true)} aria-label="Settings">
            <span aria-hidden="true">⚙</span>
          </button>
        </span>
      </div>

      {/* --- titled plate, flanked by the arena's figures -------------------- */}
      <div className="crown">
        {arena.figures ? (
          <Portrait
            id={`${arena.slug}-left`}
            name={arena.figures.left.name}
            title={arena.figures.left.title}
            side="left"
          />
        ) : (
          <span className="crown__spacer" />
        )}

        <div className="crown__title">
          <span className="crown__trophies">
            <i aria-hidden="true">🏆</i>
            {trophies}
          </span>
          <h1>{arena.name}</h1>
          <p className="crown__goal">
            {next ? `Next: ${getArena(next.id).name} at ${next.trophies} trophies` : 'Top of the ladder'}
          </p>
        </div>

        {arena.figures ? (
          <Portrait
            id={`${arena.slug}-right`}
            name={arena.figures.right.name}
            title={arena.figures.right.title}
            side="right"
          />
        ) : (
          <span className="crown__spacer" />
        )}
      </div>

      {/* --- progress: the ladder, then this rung --------------------------- */}
      <p className="rowlabel">
        Arena {arena.id} · {arena.year}
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

      <div className="arena-picker">
        <button type="button" onClick={() => step(-1)} disabled={shownArena <= 1} aria-label="Previous arena">
          ◀
        </button>
        <span className="arena-picker__name">
          {arena.id}. {arena.name}
          {shownArena > currentArena && <span className="arena-picker__locked"> · locked</span>}
        </span>
        <button
          type="button"
          onClick={() => step(1)}
          disabled={shownArena >= content.arenas.length}
          aria-label="Next arena"
        >
          ▶
        </button>
      </div>

      {/* --- the battleground itself ---------------------------------------- */}
      <ArenaStage arena={arena} />

      {/* --- lore, on a scroll ---------------------------------------------- */}
      <div className="scroll">
        <span className="scroll__cap scroll__cap--l" aria-hidden="true" />
        <p>{arena.blurb}</p>
        <span className="scroll__cap scroll__cap--r" aria-hidden="true" />
      </div>

      {/* Who you lead with. v0.1 §7 — it changes how you draft, not how hard you
          hit, so it belongs next to the deck rather than in a stats screen. */}
      <div className="commander-strip">
        {commandersUnlockedAt(arena.id).map((c) => (
          <button
            key={c.id}
            type="button"
            className={`commander-pick${commander === c.id ? ' is-on' : ''}`}
            onClick={() => setCommander(c.id)}
          >
            <UnitGlyph kind={c.art.silhouette} size={26} />
            <span className="commander-pick__name">{c.name}</span>
            <span className="commander-pick__epithet">{c.epithet}</span>
            <span className="commander-pick__reads">{c.passive.reads}</span>
          </button>
        ))}
      </div>

      <div className="deck-strip">
        <span className="deck-strip__label">Your deck</span>
        <ul>
          {deck.map((id, i) => (
            <li key={`${id}-${i}`}>
              <UnitGlyph kind={getUnit(id).art.silhouette} size={26} unitId={id} />
            </li>
          ))}
        </ul>
        <button className="link" type="button" onClick={() => go('collection')}>
          Change
        </button>
      </div>

      {/* The Chronicle. A campaign entry that sits above the ranked button on
          purpose: a new player should meet the story before the ladder. */}
      <button className="btn btn--chronicle" type="button" onClick={openCampaign}>
        <span className="btn__label">THE CHRONICLE</span>
        <span className="btn__sub">
          Rise of Cyrus · {bookProgress(campaign).done}/{bookProgress(campaign).total}
        </span>
      </button>

      <button className="btn btn--gold btn--battle" type="button" onClick={findMatch} disabled={!canPlayOnline}>
        <span className="btn__lion" aria-hidden="true">
          🦁
        </span>
        <span className="btn__label">BATTLE</span>
        <span className="btn__hint">
          {conn === 'connecting'
            ? 'Connecting…'
            : canPlayOnline
              ? `${onlineCount} player${onlineCount === 1 ? '' : 's'} online · ${wins} wins`
              : 'Server unavailable'}
        </span>
      </button>

      <button className="btn btn--teal" type="button" onClick={startSolo}>
        <span className="btn__label">PRACTICE</span>
        <span className="btn__hint">Play the computer</span>
      </button>

      <p className={`conn-strip conn-strip--${conn}`}>
        <span className="dot" aria-hidden="true" />
        {conn === 'online' ? 'Connected to server' : conn === 'connecting' ? 'Connecting to server…' : 'Offline'}
      </p>

      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
