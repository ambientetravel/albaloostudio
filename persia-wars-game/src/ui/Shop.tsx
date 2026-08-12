import { useState } from 'react';
import { arenaForTrophies, rollCardReward } from '../game/progression';
import { useGame } from '../state/store';
import { CurrencyBar, formatCount } from './Chrome';
import { SettingsModal } from './SettingsModal';

/**
 * The shop.
 *
 * Everything priced in gems or coins is real and works — those are earned by
 * playing. Everything priced in euros is a DISPLAY-ONLY SHELL: there is no
 * payment provider, no store integration, and no age gate, and pressing one
 * says so. See DECISIONS.md for why that line is drawn where it is.
 *
 * Card packs list their exact contents rather than rolling a hidden table. A
 * randomised paid pack is a loot box, and this is a product for nine-year-olds.
 */

type Tab = 'offers' | 'packs' | 'gems' | 'daily';

const TABS: { id: Tab; icon: string; label: string }[] = [
  { id: 'offers', icon: '%', label: 'Offers' },
  { id: 'packs', icon: '🎟️', label: 'Packs' },
  { id: 'gems', icon: '💎', label: 'Gems' },
  { id: 'daily', icon: '📅', label: 'Daily' },
];

export function Shop() {
  const [tab, setTab] = useState<Tab>('offers');
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="screen shop">
      <CurrencyBar onSettings={() => setSettingsOpen(true)} />

      <div className="shop-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`shop-tab${tab === t.id ? ' is-on' : ''}`}
            onClick={() => setTab(t.id)}
            aria-label={t.label}
          >
            <span aria-hidden="true">{t.icon}</span>
          </button>
        ))}
      </div>

      {tab === 'offers' && <Offers />}
      {tab === 'packs' && <Packs />}
      {tab === 'gems' && <Gems />}
      {tab === 'daily' && <Daily />}

      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}

function NotWired({ label }: { label: string }) {
  const { notify } = useGame();
  return (
    <button
      className="btn btn--gold btn--price"
      type="button"
      onClick={() =>
        notify(
          'Real-money purchases are not connected in this build. No payment provider, no store integration, and no age check exists yet.',
        )
      }
    >
      {label}
    </button>
  );
}

function Offers() {
  return (
    <>
      <h2 className="shop-title">Offers</h2>

      <section className="offer-hero">
        <span className="offer-hero__flag">BEST VALUE</span>
        <h3>Upgrade to the Royal Pass</h3>
        <ul className="offer-hero__perks">
          <li>
            <span aria-hidden="true">🚫</span> No ads
          </li>
          <li>
            <span aria-hidden="true">🪙</span> Double coins
          </li>
          <li>
            <span aria-hidden="true">🎁</span> Daily premium rewards
          </li>
        </ul>
        <div className="offer-hero__buy">
          <span className="from">from €5.99</span>
          <NotWired label="VIEW PASSES" />
        </div>
      </section>

      <p className="shop-note">
        Prices are shown for layout only. Nothing here can be bought in this build.
      </p>
    </>
  );
}

function Packs() {
  const { wallet, trophies, grantCards, notify, setDeckSlot: _unused } = useGame();
  void _unused;

  // Contents are stated up front and identical every time — this is a bundle,
  // not a gamble. The card list is drawn from what the player's arena unlocks.
  const packs = [
    { id: 'silver', name: 'Silver Pack', cards: 6, coins: 500, gems: 100, tone: 'silver' },
    { id: 'gold', name: 'Gold Pack', cards: 14, coins: 1500, gems: 200, tone: 'gold' },
    { id: 'diamond', name: 'Diamond Pack', cards: 34, coins: 5000, gems: 500, tone: 'diamond' },
  ];

  const buy = (pack: (typeof packs)[number]): void => {
    if (wallet.gems < pack.gems) {
      notify(`Not enough gems. You need ${pack.gems} and have ${wallet.gems}.`);
      return;
    }
    const arena = arenaForTrophies(trophies);
    const cards = rollCardReward(arena, (Date.now() ^ pack.cards) >>> 0, pack.cards);
    grantCards(cards);
    useGame.setState({
      wallet: { coins: wallet.coins + pack.coins, gems: wallet.gems - pack.gems },
      notice: `${pack.name} opened: ${pack.cards} cards and ${pack.coins} coins.`,
    });
  };

  return (
    <>
      <h2 className="shop-title">Card Packs</h2>
      <div className="pack-grid">
        {packs.map((p) => (
          <article key={p.id} className={`pack pack--${p.tone}`}>
            <h3>{p.name}</h3>
            <div className="pack__art" aria-hidden="true">
              🎴
            </div>
            <p className="pack__contents">
              <strong>{p.cards}</strong> cards
              <br />
              <strong>{formatCount(p.coins)}</strong> coins
            </p>
            <button className="btn btn--buy btn--price" type="button" onClick={() => buy(p)}>
              💎 {p.gems}
            </button>
          </article>
        ))}
      </div>
      <p className="shop-note">
        Every pack lists exactly what it contains. There are no randomised paid packs in this game.
      </p>
    </>
  );
}

function Gems() {
  const { wallet, notify } = useGame();

  const coinBundles = [
    { name: 'Pouch of Coins', coins: 5000, gems: 200 },
    { name: 'Barrel of Coins', coins: 25000, gems: 900, save: '10%' },
    { name: 'Chest of Coins', coins: 100000, gems: 3200, save: '20%' },
  ];

  const buyCoins = (b: (typeof coinBundles)[number]): void => {
    if (wallet.gems < b.gems) {
      notify(`Not enough gems. You need ${b.gems} and have ${wallet.gems}.`);
      return;
    }
    useGame.setState({
      wallet: { coins: wallet.coins + b.coins, gems: wallet.gems - b.gems },
      notice: `${formatCount(b.coins)} coins added.`,
    });
  };

  return (
    <>
      <h2 className="shop-title">Gems</h2>
      <div className="bundle-grid">
        {[
          { name: 'Handful', amount: 200, price: '€0.99' },
          { name: 'Pouch', amount: 1000, price: '€5.99' },
          { name: 'Barrel', amount: 4200, price: '€22.99', save: '5%' },
        ].map((g) => (
          <article key={g.name} className="bundle bundle--gem">
            {g.save && <span className="bundle__save">SAVE {g.save}</span>}
            <h3>{g.name}</h3>
            <div className="bundle__art" aria-hidden="true">
              💎
            </div>
            <p className="bundle__amount">{formatCount(g.amount)}</p>
            <NotWired label={g.price} />
          </article>
        ))}
      </div>

      <h2 className="shop-title">Coins</h2>
      <div className="bundle-grid">
        {coinBundles.map((b) => (
          <article key={b.name} className="bundle bundle--coin">
            {b.save && <span className="bundle__save">SAVE {b.save}</span>}
            <h3>{b.name}</h3>
            <div className="bundle__art" aria-hidden="true">
              🪙
            </div>
            <p className="bundle__amount">{formatCount(b.coins)}</p>
            <button className="btn btn--buy btn--price" type="button" onClick={() => buyCoins(b)}>
              💎 {b.gems}
            </button>
          </article>
        ))}
      </div>

      <p className="shop-note">Coin bundles work and spend gems you have earned. Gem prices in euros do not.</p>
    </>
  );
}

function Daily() {
  const { lastDailyClaim, claimDaily, wallet, trophies, grantCards, notify } = useGame();
  const today = new Date().toISOString().slice(0, 10);
  const claimed = lastDailyClaim === today;

  const deals = [
    { id: 'a', unit: 'Shield-bearer', count: 16, coins: 2400 },
    { id: 'b', unit: 'Persian Archer', count: 16, coins: 2400 },
    { id: 'c', unit: 'Median Spearman', count: 8, coins: 3200 },
  ];

  const buyDeal = (d: (typeof deals)[number]): void => {
    if (wallet.coins < d.coins) {
      notify(`Not enough coins. You need ${formatCount(d.coins)}.`);
      return;
    }
    const cards = rollCardReward(arenaForTrophies(trophies), (Date.now() ^ d.count) >>> 0, d.count);
    grantCards(cards);
    useGame.setState({
      wallet: { ...wallet, coins: wallet.coins - d.coins },
      notice: `${d.count} cards added.`,
    });
  };

  return (
    <>
      <h2 className="shop-title">Daily</h2>
      <div className="daily-grid">
        <article className="daily daily--free">
          <h3>Daily reward</h3>
          <div className="daily__art" aria-hidden="true">
            🎁
          </div>
          <p>500 coins + 5 gems</p>
          <button className="btn btn--buy btn--price" type="button" onClick={claimDaily} disabled={claimed}>
            {claimed ? 'Claimed today' : 'CLAIM'}
          </button>
        </article>

        {deals.map((d) => (
          <article key={d.id} className="daily">
            <h3>{d.unit}</h3>
            <div className="daily__art" aria-hidden="true">
              🃏
            </div>
            <p>+{d.count} cards</p>
            <button className="btn btn--buy btn--price" type="button" onClick={() => buyDeal(d)}>
              🪙 {formatCount(d.coins)}
            </button>
          </article>
        ))}
      </div>
      <p className="shop-note">
        No rewarded video ads are wired up. The reference game gives these away for watching one; that needs an ad
        network and, for this age group, a parental-consent flow.
      </p>
    </>
  );
}
