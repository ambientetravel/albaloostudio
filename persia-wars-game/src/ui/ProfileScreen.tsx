import { useState } from 'react';
import { assignedName } from '../game/playerNames';
import { useGame } from '../state/store';
import { Avatar } from './Avatar';
import { AVATARS } from './avatars';
import { ACHAEMENID_PALETTE, bannerAt } from './palette';

/**
 * First screen on a fresh install. Afterwards the same fields live in the
 * settings sheet's profile tab. The name is shown to strangers in online
 * matches, so it is sanitised here and again on the server.
 */
export function ProfileScreen() {
  const { profile, saveProfile } = useGame();
  // Nobody types a name. The display name is the only thing this game sends to
  // a stranger and the audience is nine to fourteen, so it is chosen from a
  // closed set rather than typed — which removes the risk instead of gating it.
  const [shuffle, setShuffle] = useState(0);
  const name = assignedName(shuffle);
  const [avatar, setAvatar] = useState(profile?.avatar ?? 0);
  const [banner, setBanner] = useState(profile?.banner ?? 0);
  const chosen = bannerAt(banner);

  return (
    <div className="screen profile-screen">
      <h2>Choose your name</h2>
      <p className="muted">This is what other players see. Tap for a different one.</p>

      <div className="profile-preview" style={{ background: chosen.hex, color: chosen.ink }}>
        <Avatar index={avatar} size={80} />
        <span className="profile-preview__name">{name}</span>
      </div>

      <button
        className="btn btn--teal name-shuffle"
        type="button"
        onClick={() => setShuffle((n) => n + 1)}
      >
        Give me a different name
      </button>

      <p className="settings-label">Pick a badge</p>
      <div className="avatar-grid">
        {AVATARS.map((_, i) => (
          <button
            key={i}
            type="button"
            className={`avatar-option${avatar === i ? ' is-on' : ''}`}
            onClick={() => setAvatar(i)}
            aria-label={`Badge ${i + 1}`}
            aria-pressed={avatar === i}
          >
            <Avatar index={i} size={48} />
          </button>
        ))}
      </div>

      {/* The official Achaemenid palette, used only for the player's banner. */}
      <p className="settings-label">
        Banner colour <span className="settings-label__note">Achaemenid palette</span>
      </p>
      <div className="banner-grid">
        {ACHAEMENID_PALETTE.map((c, i) => (
          <button
            key={c.id}
            type="button"
            className={`banner-swatch${banner === i ? ' is-on' : ''}`}
            style={{ background: c.hex }}
            onClick={() => setBanner(i)}
            aria-label={`${c.name} (${c.code})`}
            aria-pressed={banner === i}
          />
        ))}
      </div>
      <p className="banner-caption">
        {chosen.name} · {chosen.code}
      </p>

      <button
        className="btn btn--gold btn--big"
        type="button"
        onClick={() => saveProfile(name, avatar, banner)}
      >
        LET&apos;S GO
      </button>
    </div>
  );
}
