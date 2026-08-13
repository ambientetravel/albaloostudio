import { useState } from 'react';
import { content, getArena, getUnit } from '../content';
import type { Spell, Unit } from '../content/types';
import {
  DECK_SIZE,
  MAX_CARD_LEVEL,
  arenaForTrophies,
  canUpgrade,
  cardsToUpgrade,
  coinsToUpgrade,
} from '../game/progression';
import { TOTAL_SPELL_CARDS, TOTAL_UNIT_CARDS, useGame } from '../state/store';
import { CurrencyBar, formatCount } from './Chrome';
import { SettingsModal } from './SettingsModal';
import { CLASS_LABEL } from './labels';
import { UnitGlyph } from './UnitGlyph';

export function Collection() {
  const { deck, collection, trophies, setDeckSlot } = useGame();
  const [tab, setTab] = useState<'units' | 'spells'>('units');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [detail, setDetail] = useState<string | null>(null);
  const [swapSlot, setSwapSlot] = useState<number | null>(null);

  const arena = arenaForTrophies(trophies);
  const owned = Object.keys(collection).length;

  const onCardTap = (unit: Unit): void => {
    // Tapping a deck slot first, then a card, swaps it in. Otherwise it opens.
    if (swapSlot !== null && collection[unit.id]) {
      setDeckSlot(swapSlot, unit.id);
      setSwapSlot(null);
      return;
    }
    setDetail(unit.id);
  };

  return (
    <div className="screen collection">
      <CurrencyBar onSettings={() => setSettingsOpen(true)} />

      <div className="coll-tabs">
        <button type="button" className={tab === 'units' ? 'is-on' : ''} onClick={() => setTab('units')}>
          Units
        </button>
        <button type="button" className={tab === 'spells' ? 'is-on' : ''} onClick={() => setTab('spells')}>
          <span aria-hidden="true">🔒</span> Spells
        </button>
      </div>

      {/* The four cards you take into battle. Tap a slot, then tap a card. */}
      <section className="deck-panel">
        <p className="deck-panel__title">
          Battle deck
          {swapSlot !== null && <span className="deck-panel__hint">Pick a card to put in slot {swapSlot + 1}</span>}
        </p>
        <ul className="deck-panel__slots">
          {Array.from({ length: DECK_SIZE }, (_, i) => {
            const unit = getUnit(deck[i]);
            const level = collection[unit.id]?.level ?? 1;
            return (
              <li key={i}>
                <button
                  type="button"
                  className={`deck-slot${swapSlot === i ? ' is-picking' : ''}`}
                  onClick={() => setSwapSlot(swapSlot === i ? null : i)}
                  aria-pressed={swapSlot === i}
                >
                  <span className="deck-slot__level">{level}</span>
                  <UnitGlyph kind={unit.art.silhouette} size={40} unitId={unit.id} />
                  <span className="deck-slot__name">{unit.name}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      {tab === 'units' ? (
        <>
          <div className="coll-header">
            <span>Unit collection</span>
            <span className="coll-count">
              {owned}/{TOTAL_UNIT_CARDS}
            </span>
          </div>
          <div className="card-grid">
            {content.units.map((u) => (
              <UnitCardTile
                key={u.id}
                unit={u}
                arena={arena}
                state={collection[u.id]}
                onTap={() => onCardTap(u)}
              />
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="coll-header">
            <span>Spell collection</span>
            <span className="coll-count">0/{TOTAL_SPELL_CARDS}</span>
          </div>
          <p className="spells-note">
            Spells come from Iranian legend — the Shahnameh and the Avesta — not from the historical record. They are
            written but not yet fact-checked, so none of them can be played. Each card says which story it comes from.
          </p>
          <div className="card-grid">
            {content.spells.map((s) => (
              <SpellTile key={s.id} spell={s} onTap={() => setDetail(`spell:${s.id}`)} />
            ))}
          </div>
        </>
      )}

      {detail && <CardDetail id={detail} onClose={() => setDetail(null)} />}
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}

function UnitCardTile({
  unit,
  arena,
  state,
  onTap,
}: {
  unit: Unit;
  arena: number;
  state?: { count: number; level: number };
  onTap: () => void;
}) {
  const lockedByArena = unit.arena > arena;
  const owned = Boolean(state);

  if (lockedByArena) {
    return (
      <div className="card-tile is-locked">
        <span className="card-tile__lock" aria-hidden="true">
          🔒
        </span>
        <span className="card-tile__name">{unit.name}</span>
        <span className="card-tile__arena">{getArena(unit.arena).name}</span>
      </div>
    );
  }

  const level = state?.level ?? 1;
  const need = cardsToUpgrade(level);
  const have = state?.count ?? 0;
  const frac = level >= MAX_CARD_LEVEL ? 1 : Math.min(1, have / need);

  return (
    <button className={`card-tile${owned ? '' : ' is-unowned'}`} type="button" onClick={onTap}>
      <span className="card-tile__arena-pip">{unit.arena}</span>
      <UnitGlyph kind={unit.art.silhouette} size={46} unitId={unit.id} />
      <span className="card-tile__name">{unit.name}</span>
      <span className="card-tile__bar">
        <span className="card-tile__level">{level}</span>
        <span className="card-tile__track">
          <span className="card-tile__fill" style={{ width: `${Math.round(frac * 100)}%` }} />
          <span className="card-tile__count">{level >= MAX_CARD_LEVEL ? 'MAX' : `${have}/${need}`}</span>
        </span>
      </span>
    </button>
  );
}

function SpellTile({ spell, onTap }: { spell: Spell; onTap: () => void }) {
  return (
    <button className="card-tile card-tile--spell is-unowned" type="button" onClick={onTap}>
      <span className="card-tile__arena-pip">{spell.arena}</span>
      <UnitGlyph kind={spell.art.silhouette} size={46} />
      <span className="card-tile__name">{spell.name}</span>
      <span className="card-tile__arena">{spell.source}</span>
    </button>
  );
}

function CardDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const { collection, wallet, upgradeCard } = useGame();

  if (id.startsWith('spell:')) {
    const spell = content.spells.find((s) => s.id === id.slice(6))!;
    return (
      <div className="modal-backdrop" onClick={onClose}>
        <div className="modal modal--codex" onClick={(e) => e.stopPropagation()}>
          <h3>{spell.name}</h3>
          <p className="modal__sub">Legend · {spell.source}</p>
          <p className="legend-banner">
            This is a story, not an event. It is recorded in Iranian literature, and it has not yet been checked by a
            historian for this game.
          </p>
          <p>{spell.blurb}</p>
          <p className="muted">{spell.blurbOlder}</p>
          {spell.disputed.length > 0 && (
            <section className="disputed">
              <h4>What&apos;s disputed</h4>
              <ul>
                {spell.disputed.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </section>
          )}
          <h4>Sources</h4>
          <ul className="sources">
            {spell.sourceRefs.map((s) => (
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

  const unit = getUnit(id);
  const state = collection[unit.id];
  const level = state?.level ?? 1;
  const maxed = level >= MAX_CARD_LEVEL;
  const upgradable = state ? canUpgrade(state, wallet.coins) : false;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal--codex" onClick={(e) => e.stopPropagation()}>
        <h3>{unit.name}</h3>
        <p className="modal__sub">
          {CLASS_LABEL[unit.class]} · Level {level} · Unlocks in {getArena(unit.arena).name}
        </p>
        <p>{unit.blurb}</p>
        <p className="detail__evidence">{unit.blurbOlder}</p>

        <dl className="stats stats--detail">
          <div>
            <dt>ATK</dt>
            <dd>{unit.atk}</dd>
          </div>
          <div>
            <dt>DEF</dt>
            <dd>{unit.def}</dd>
          </div>
          <div>
            <dt>HP</dt>
            <dd>{unit.hp}</dd>
          </div>
        </dl>

        {!state && <p className="legend-banner">You do not own this card yet. Win battles to find it.</p>}

        {state && !maxed && (
          <button className="btn btn--buy" type="button" disabled={!upgradable} onClick={() => upgradeCard(unit.id)}>
            UPGRADE · {state.count}/{cardsToUpgrade(level)} cards · 🪙 {formatCount(coinsToUpgrade(level))}
          </button>
        )}
        {state && maxed && <p className="legend-banner">This card is at maximum level.</p>}

        {unit.attestationNote && (
          <>
            <h4>Why it is date-locked</h4>
            <p>{unit.attestationNote}</p>
          </>
        )}

        {unit.disputed.length > 0 && (
          <section className="disputed">
            <h4>What&apos;s disputed</h4>
            <ul>
              {unit.disputed.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          </section>
        )}

        <h4>Sources</h4>
        <ul className="sources">
          {unit.sourceRefs.map((s) => (
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
