import { useState } from 'react';
import { assignedName, isAssignedName } from '../game/playerNames';
import { TOTAL_UNIT_CARDS, totalCardsCollected, useGame } from '../state/store';
import { Avatar } from './Avatar';
import { AVATARS } from './avatars';
import { ACHAEMENID_PALETTE, bannerAt } from './palette';

/**
 * The gear opens this. Two tabs, matching the reference: the player's own
 * profile on the left, device and account settings on the right.
 */
export function SettingsModal({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<'profile' | 'settings'>('profile');

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="settings-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="settings-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'profile'}
            className={tab === 'profile' ? 'is-on' : ''}
            onClick={() => setTab('profile')}
          >
            <span aria-hidden="true">👤</span> Profile
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'settings'}
            className={tab === 'settings' ? 'is-on' : ''}
            onClick={() => setTab('settings')}
          >
            <span aria-hidden="true">⚙</span> Settings
          </button>
        </div>

        <div className="settings-body">{tab === 'profile' ? <ProfileTab /> : <SettingsTab />}</div>

        <button className="btn btn--gold" type="button" onClick={onClose}>
          CONFIRM
        </button>
      </div>
    </div>
  );
}

function ProfileTab() {
  const { profile, saveProfile, wins, losses, bestTrophies, collection } = useGame();
  const [name, setName] = useState(
    isAssignedName(profile?.name ?? '') ? (profile?.name ?? '') : assignedName(0),
  );
  const [shuffle, setShuffle] = useState(0);
  const [avatar, setAvatar] = useState(profile?.avatar ?? 0);
  const [banner, setBanner] = useState(profile?.banner ?? 0);

  const played = wins + losses;
  const rate = played > 0 ? Math.round((wins / played) * 100) : 0;
  const chosen = bannerAt(banner);

  // Saving from here keeps the player on the lobby; the modal closes over it.
  const commit = (patch: { name?: string; avatar?: number; banner?: number }): void => {
    saveProfile(patch.name ?? name, patch.avatar ?? avatar, patch.banner ?? banner);
  };

  return (
    <>
      {/* The pencil re-rolls rather than opening a field. Nobody types a name
          in this game — see game/playerNames.ts — and a text box here would be
          a second way in that the store would silently overrule anyway. */}
      <div className="edit-row">
        <span className="edit-row__value">{name}</span>
        <button
          className="pencil"
          type="button"
          onClick={() => {
            const next = assignedName(shuffle + 1);
            setShuffle((n) => n + 1);
            setName(next);
            commit({ name: next });
          }}
          aria-label="Give me a different name"
        >
          ⟳
        </button>
      </div>

      <p className="settings-label">Badge</p>
      <div className="avatar-grid">
        {AVATARS.map((_, i) => (
          <button
            key={i}
            type="button"
            className={`avatar-option${avatar === i ? ' is-on' : ''}`}
            onClick={() => {
              setAvatar(i);
              commit({ avatar: i });
            }}
            aria-label={`Badge ${i + 1}`}
            aria-pressed={avatar === i}
          >
            <Avatar index={i} size={44} />
          </button>
        ))}
      </div>

      {/*
        The banner colours are the official Achaemenid palette supplied for the
        project, kept with their reference codes so the sheet stays traceable.
      */}
      <p className="settings-label">
        Banner colour <span className="settings-label__note">Achaemenid palette</span>
      </p>
      <div className="banner-preview" style={{ background: chosen.hex, color: chosen.ink }}>
        <strong>{chosen.name}</strong>
        <span>{chosen.code}</span>
      </div>
      <div className="banner-grid">
        {ACHAEMENID_PALETTE.map((c, i) => (
          <button
            key={c.id}
            type="button"
            className={`banner-swatch${banner === i ? ' is-on' : ''}`}
            style={{ background: c.hex }}
            onClick={() => {
              setBanner(i);
              commit({ banner: i });
            }}
            aria-label={`${c.name} (${c.code})`}
            aria-pressed={banner === i}
          />
        ))}
      </div>


      <div className="stat-grid">
        <Stat icon="⬆" tone="good" label="Wins" value={wins} />
        <Stat icon="⬇" tone="bad" label="Losses" value={losses} />
        <Stat icon="🏅" label="Win rate" value={`${rate}%`} />
        <Stat icon="🏆" label="Best trophies" value={bestTrophies} />
        <Stat icon="🃏" label="Cards collected" value={`${totalCardsCollected(collection)}/${TOTAL_UNIT_CARDS}`} />
        <Stat icon="⚔️" label="Battles" value={played} />
      </div>
    </>
  );
}

function Stat({ icon, label, value, tone }: { icon: string; label: string; value: string | number; tone?: string }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className={`stat__value${tone ? ` tone-${tone}` : ''}`}>
        <i aria-hidden="true">{icon}</i>
        {value}
      </span>
    </div>
  );
}

function SettingsTab() {
  const { settings, setSettings, notify } = useGame();
  const stub = (what: string) => () => notify(`${what} is not wired up yet in this build.`);

  return (
    <>
      <div className="settings-block">
        <label className="slider-row">
          <span>
            Sound effects <strong>{settings.sfxVolume}</strong>
          </span>
          <input
            type="range"
            min={0}
            max={100}
            value={settings.sfxVolume}
            onChange={(e) => setSettings({ sfxVolume: Number(e.target.value) })}
          />
        </label>
        <label className="slider-row">
          <span>
            Music <strong>{settings.musicVolume}</strong>
          </span>
          <input
            type="range"
            min={0}
            max={100}
            value={settings.musicVolume}
            onChange={(e) => setSettings({ musicVolume: Number(e.target.value) })}
          />
        </label>
      </div>

      <div className="settings-block">
        <label className="check-row">
          <span>Haptic feedback</span>
          <input
            type="checkbox"
            checked={settings.haptics}
            onChange={(e) => setSettings({ haptics: e.target.checked })}
          />
        </label>
      </div>

      <div className="settings-links">
        <button type="button" className="btn btn--gold btn--link" onClick={stub('Language selection')}>
          Language
        </button>
        <button type="button" className="btn btn--gold btn--link" onClick={stub('Terms of service')}>
          Terms
        </button>
        <button type="button" className="btn btn--gold btn--link" onClick={stub('Privacy policy')}>
          Privacy
        </button>
        <button type="button" className="btn btn--gold btn--link" onClick={stub('News')}>
          News
        </button>
        <button type="button" className="btn btn--gold btn--link" onClick={stub('Your data')}>
          Your data
        </button>
        <button type="button" className="btn btn--gold btn--link" onClick={stub('Problem reporting')}>
          Report a problem
        </button>
        <button type="button" className="btn btn--gold btn--link" onClick={stub('Purchase restore')}>
          Restore purchases
        </button>
        <button type="button" className="btn btn--gold btn--link" onClick={stub('Credits')}>
          Credits
        </button>
      </div>

      <div className="settings-block settings-block--signin">
        <p>Sign in to save your progress</p>
        <button type="button" className="signin-btn" onClick={stub('Sign in with Apple')}>
          <span aria-hidden="true"></span> Sign in with Apple
        </button>
        <p className="tiny">
          No account system exists yet. Progress is stored on this device only.
        </p>
      </div>

      <p className="version">v0.3.0 · Achaemenid slice</p>
    </>
  );
}
