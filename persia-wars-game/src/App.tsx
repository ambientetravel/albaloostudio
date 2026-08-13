import { Suspense, lazy, useEffect, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { getArena } from './content';
import { arenaForTrophies } from './game/progression';
import { useGame } from './state/store';
import { applyArenaTheme } from './ui/arenaTheme';
import { ArenaBackdrop } from './ui/ArenaBackdrop';
import { GameFrame } from './ui/GameFrame';
import { LoadingScreen } from './ui/LoadingScreen';
import { MatchScreen } from './ui/MatchScreen';
import { BottomNav } from './ui/Chrome';
import { Campaign, Capital, MissionBrief } from './ui/Campaign';
import { Codex } from './ui/Codex';
import { Ladder } from './ui/Ladder';
import { Collection } from './ui/Collection';
import { Lobby } from './ui/Lobby';
import { Matchmaking } from './ui/Matchmaking';
import { ProfileScreen } from './ui/ProfileScreen';
import { Result } from './ui/Result';
import { ScenarioSelect } from './ui/ScenarioSelect';
import { Shop } from './ui/Shop';

/** Screens that keep the bottom navigation. A match takes over the whole app. */
const NAV_SCREENS = new Set(['lobby', 'collection', 'shop', 'codex', 'ladder', 'campaign', 'capital']);

/**
 * Dev-only theme sampler at `?themelab`. Lazy so it stays out of the main chunk
 * and costs shipped players nothing.
 */
const ThemeLab = lazy(() => import('./dev/ThemeLab'));
const wantsThemeLab = (): boolean =>
  typeof location !== 'undefined' && new URLSearchParams(location.search).has('themelab');

/**
 * Feedback capture, shown only in a test build. `import.meta.env.VITE_TEST_BUILD`
 * is set by `npm run share`, so a real release never carries it. Lazy for the
 * same reason the theme lab is.
 */
const Feedback = lazy(() => import('@feedback').then((m) => ({ default: m.Feedback })));
declare const __TEST_BUILD__: boolean;
const isTestBuild = __TEST_BUILD__;

export function App() {
  const { screen, profile, connect, notice, dismissNotice, trophies, matchState } = useGame();
  const [booting, setBooting] = useState(true);

  // The whole interface takes the colour of the ground you are standing on.
  // During a match that is the match's arena (the server's, when online);
  // everywhere else it is your own rung of the ladder.
  //
  // Scoped to the match screens on purpose: `matchState` outlives the match it
  // belongs to, and reading it unconditionally pins the theme to whatever was
  // last played instead of following the ladder.
  const inMatch = screen === 'battle' || screen === 'result';
  const arenaId = inMatch && matchState ? matchState.arena : arenaForTrophies(trophies);
  useEffect(() => {
    applyArenaTheme(getArena(arenaId).slug);
  }, [arenaId]);

  // Connect as soon as there is an identity to announce, and stay connected —
  // the lobby's online count depends on it.
  useEffect(() => {
    if (profile) connect();
  }, [profile, connect]);

  const showNav = NAV_SCREENS.has(screen);

  if (wantsThemeLab()) {
    return (
      <div className="app">
        <Suspense fallback={<p className="muted">Loading theme lab…</p>}>
          <ThemeLab />
        </Suspense>
      </div>
    );
  }

  return (
    <GameFrame>
    <div className={`app${showNav ? ' has-nav has-backdrop' : ''}`}>
      {showNav && <ArenaBackdrop />}

      <AnimatePresence>
        {booting && <LoadingScreen key="loading" onDone={() => setBooting(false)} />}
      </AnimatePresence>

      <main>
        {screen === 'profile' && <ProfileScreen />}
        {screen === 'lobby' && <Lobby />}
        {screen === 'collection' && <Collection />}
        {screen === 'shop' && <Shop />}
        {screen === 'codex' && <Codex />}
        {screen === 'ladder' && <Ladder />}
        {screen === 'matchmaking' && <Matchmaking />}
        {screen === 'scenario' && <ScenarioSelect />}
        {screen === 'campaign' && <Campaign />}
        {screen === 'mission' && <MissionBrief />}
        {screen === 'capital' && <Capital />}
        {screen === 'battle' && <MatchScreen />}
        {screen === 'result' && <Result />}
      </main>

      {showNav && <BottomNav />}

      {isTestBuild && (
        <Suspense fallback={null}>
          <Feedback />
        </Suspense>
      )}

      {notice && (
        <div className="modal-backdrop" onClick={dismissNotice}>
          <div className="modal modal--notice" onClick={(e) => e.stopPropagation()}>
            <p>{notice}</p>
            <button className="btn btn--gold" type="button" onClick={dismissNotice}>
              OK
            </button>
          </div>
        </div>
      )}
    </div>
    </GameFrame>
  );
}
