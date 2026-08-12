import { useGame, type Screen } from '../state/store';

/** Top strip: soft currencies and the settings gear, as in the reference lobby. */
export function CurrencyBar({ onSettings }: { onSettings: () => void }) {
  const { wallet, trophies } = useGame();
  return (
    <div className="currency-bar">
      <span className="pill pill--trophy">
        <i aria-hidden="true">🏆</i>
        {trophies}
      </span>
      <span className="pill pill--gem">
        <i aria-hidden="true">💎</i>
        {wallet.gems}
      </span>
      <span className="pill pill--coin">
        <i aria-hidden="true">🪙</i>
        {formatCount(wallet.coins)}
      </span>
      <button className="gear" type="button" onClick={onSettings} aria-label="Settings">
        <span aria-hidden="true">⚙</span>
      </button>
    </div>
  );
}

/** 15,500 → "15.5K". Keeps the bar from reflowing as the number grows. */
export function formatCount(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}K`;
  return `${(n / 1_000_000).toFixed(1)}M`;
}

/**
 * Five slots, named from the mockup where the name matches what the screen
 * actually does. Its fifth slot was "Foes"; the collection holds your own army,
 * not your enemies, so that slot became the trophy ladder instead of inventing
 * a screen with nothing behind it.
 */
const TABS: { screen: Screen; label: string; icon: string }[] = [
  { screen: 'shop', label: 'Bazaar', icon: '🏪' },
  { screen: 'collection', label: 'Army', icon: '🃏' },
  { screen: 'lobby', label: 'Battle', icon: '⚔️' },
  { screen: 'codex', label: 'Scrolls', icon: '📜' },
  { screen: 'ladder', label: 'Trophies', icon: '🏆' },
];

export function BottomNav() {
  const { screen, go } = useGame();
  return (
    <nav className="bottom-nav" aria-label="Main">
      {TABS.map((tab) => (
        <button
          key={tab.screen}
          type="button"
          className={`nav-tab${screen === tab.screen ? ' is-on' : ''}`}
          onClick={() => go(tab.screen)}
          aria-current={screen === tab.screen ? 'page' : undefined}
        >
          <span className="nav-tab__icon" aria-hidden="true">
            {tab.icon}
          </span>
          <span className="nav-tab__label">{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
