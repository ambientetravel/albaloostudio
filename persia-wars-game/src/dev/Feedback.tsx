import { useState } from 'react';
import { getArena } from '../content';
import { arenaForTrophies } from '../game/progression';
import { useGame } from '../state/store';

/**
 * Test-build feedback capture.
 *
 * Shown only when the build is served with `SERVE_DIST=1` (see App.tsx), so it
 * never appears in a real release. A note is worth far more with the state it
 * was written in attached — which screen, which arena, how many trophies — so
 * every note carries that automatically and the tester only writes the opinion.
 *
 * There is no backend, and adding one for an internal test would mean standing
 * up storage and a privacy story for a children's product. Notes live in
 * localStorage and export as one markdown file the tester sends back.
 */
const KEY = 'persia-at-war/feedback';

interface Note {
  at: string;
  kind: 'bug' | 'idea' | 'confusing';
  text: string;
  screen: string;
  arena: string;
  trophies: number;
  build: string;
  viewport: string;
}

function load(): Note[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]') as Note[];
  } catch {
    return [];
  }
}

export function Feedback() {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<Note['kind']>('idea');
  const [text, setText] = useState('');
  const [saved, setSaved] = useState(load().length);
  const state = useGame();

  const submit = (): void => {
    if (!text.trim()) return;
    const note: Note = {
      at: new Date().toISOString(),
      kind,
      text: text.trim(),
      screen: state.screen,
      arena: getArena(state.matchState?.arena ?? arenaForTrophies(state.trophies)).name,
      trophies: state.trophies,
      build: 'test',
      viewport: `${window.innerWidth}x${window.innerHeight}`,
    };
    const all = [...load(), note];
    localStorage.setItem(KEY, JSON.stringify(all));
    setSaved(all.length);
    setText('');
    setOpen(false);
  };

  const exportAll = (): void => {
    const all = load();
    if (all.length === 0) return;
    const md =
      `# Persia at War — test feedback\n\n` +
      `${all.length} note${all.length === 1 ? '' : 's'}, exported ${new Date().toLocaleString()}\n\n` +
      all
        .map(
          (n, i) =>
            `## ${i + 1}. ${n.kind.toUpperCase()}\n\n${n.text}\n\n` +
            `> screen \`${n.screen}\` · arena ${n.arena} · ${n.trophies} trophies · ` +
            `${n.viewport} · ${new Date(n.at).toLocaleString()}\n`,
        )
        .join('\n');
    const blob = new Blob([md], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `persia-feedback-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <>
      <button className="fb-fab" type="button" onClick={() => setOpen(true)} aria-label="Send feedback">
        <span aria-hidden="true">✎</span>
        {saved > 0 && <i className="fb-fab__count">{saved}</i>}
      </button>

      {open && (
        <div className="modal-backdrop" onClick={() => setOpen(false)}>
          <div className="modal modal--fb" onClick={(e) => e.stopPropagation()}>
            <h3>Tell us what you think</h3>
            <p className="muted fb-context">
              On <strong>{state.screen}</strong> · {getArena(state.matchState?.arena ?? arenaForTrophies(state.trophies)).name}{' '}
              · {state.trophies} trophies — all attached automatically.
            </p>

            <div className="fb-kinds">
              {(['bug', 'confusing', 'idea'] as Note['kind'][]).map((k) => (
                <button
                  key={k}
                  type="button"
                  className={`chip${kind === k ? ' is-on' : ''}`}
                  onClick={() => setKind(k)}
                >
                  {k === 'bug' ? 'Something broke' : k === 'confusing' ? 'Confusing' : 'Idea'}
                </button>
              ))}
            </div>

            <textarea
              className="fb-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
              placeholder="What happened, or what would you change?"
              autoFocus
            />

            <button className="btn btn--gold" type="button" onClick={submit} disabled={!text.trim()}>
              SAVE NOTE
            </button>

            {saved > 0 && (
              <>
                <button className="btn btn--teal" type="button" onClick={exportAll}>
                  Export {saved} note{saved === 1 ? '' : 's'} to send back
                </button>
                <button
                  className="btn btn--ghost"
                  type="button"
                  onClick={() => {
                    localStorage.removeItem(KEY);
                    setSaved(0);
                  }}
                >
                  Clear
                </button>
              </>
            )}

            <p className="tiny">
              Notes stay on this device until you export them. Nothing is sent anywhere.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
