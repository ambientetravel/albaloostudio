import { useState } from 'react';
import { CONFIDENCE_LABEL, content } from '../content';
import type { Confidence, Silhouette } from '../content/types';
import { useGame } from '../state/store';
import { unitSubtitle } from './labels';
import { Rules } from './Rules';
import { UnitGlyph } from './UnitGlyph';

type Tab = 'battles' | 'kings' | 'units' | 'rules';

const TAB_LABEL: Record<Tab, string> = {
  battles: 'Battles',
  kings: 'Figures',
  units: 'Units',
  rules: 'Rules',
};

/** The rules are not something you earn; they are how the game works. */
const ALWAYS_OPEN: Tab[] = ['rules'];

export function Codex() {
  const { codex, go } = useGame();
  const [tab, setTab] = useState<Tab>('battles');
  const [open, setOpen] = useState<string | null>(null);

  const total = codex.battles.length + codex.kings.length + codex.units.length;

  return (
    <div className="screen codex">
      <h2>Codex</h2>

      <div className="tabs">
        {(['battles', 'kings', 'units', 'rules'] as Tab[]).map((tb) => (
          <button key={tb} type="button" className={`chip${tab === tb ? ' is-on' : ''}`} onClick={() => setTab(tb)}>
            {TAB_LABEL[tb]}
          </button>
        ))}
      </div>

      {total === 0 && !ALWAYS_OPEN.includes(tab) && (
        <p className="muted">Nothing here yet. Play a battle and the cards you earn appear here.</p>
      )}

      {tab === 'rules' && <Rules />}

      <div className="codex-grid">
        {tab === 'battles' &&
          content.battles.map((b) => (
            <CodexTile
              key={b.id}
              unlocked={codex.battles.includes(b.id)}
              title={b.name}
              subtitle={b.year}
              onOpen={() => setOpen(`battle:${b.id}`)}
            />
          ))}

        {tab === 'kings' &&
          content.kings.map((k) => (
            <CodexTile
              key={k.id}
              unlocked={codex.kings.includes(k.id)}
              title={k.name}
              subtitle={k.reign}
              onOpen={() => setOpen(`king:${k.id}`)}
            />
          ))}

        {tab === 'units' &&
          content.units.map((u) => (
            <CodexTile
              key={u.id}
              unlocked={codex.units.includes(u.id)}
              title={u.name}
              subtitle={unitSubtitle(u)}
              glyph={u.art.silhouette}
              glyphId={u.id}
              onOpen={() => setOpen(`unit:${u.id}`)}
            />
          ))}
      </div>

      <button className="btn btn--ghost" type="button" onClick={() => go('lobby')}>
        Back
      </button>

      {open && <CodexDetail id={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

function CodexTile({
  unlocked,
  title,
  subtitle,
  glyph,
  glyphId,
  onOpen,
}: {
  unlocked: boolean;
  title: string;
  subtitle: string;
  glyph?: Silhouette;
  glyphId?: string;
  onOpen: () => void;
}) {
  if (!unlocked) {
    return (
      <div className="codex-tile is-locked">
        <span className="lock" aria-hidden="true">
          🔒
        </span>
        <span className="codex-tile__title">Locked</span>
      </div>
    );
  }
  return (
    <button className="codex-tile" type="button" onClick={onOpen}>
      {glyph && <UnitGlyph kind={glyph} size={44} unitId={glyphId} />}
      <span className="codex-tile__title">{title}</span>
      <span className="codex-tile__sub">{subtitle}</span>
    </button>
  );
}

function CodexDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const [kind, key] = id.split(':');

  let title = '';
  let subtitle = '';
  let bodyParts: string[] = [];
  let teaches: string[] = [];
  let disputed: string[] = [];
  let sources: string[] = [];
  let confidence: Confidence = 'probable';

  if (kind === 'battle') {
    const b = content.battles.find((x) => x.id === key)!;
    title = b.name;
    subtitle = `${b.year} · ${b.site}`;
    bodyParts = [
      `${b.opponents.a} × ${b.opponents.b}`,
      b.summary,
      b.evidence,
      `What really happened: ${b.victor}`,
    ];
    teaches = b.teaches;
    disputed = b.disputed;
    sources = b.sourceRefs;
    confidence = b.confidence;
  } else if (kind === 'king') {
    const k = content.kings.find((x) => x.id === key)!;
    title = k.name;
    subtitle = `${k.title} · ${k.reign}`;
    bodyParts = [k.bio, k.achievement];
    disputed = k.disputed;
    sources = k.sourceRefs;
    confidence = k.confidence;
  } else {
    const u = content.units.find((x) => x.id === key)!;
    title = u.name;
    subtitle = unitSubtitle(u);
    // Both, always. The sourced paragraph is where Herodotus, the Persepolis
    // reliefs and the daric live — 24 of 25 units cite a source there and 1 of
    // 25 does in the short line. Behind a settings toggle that defaulted to off,
    // almost nobody ever saw the half of this game that teaches how we know.
    bodyParts = [u.blurb, u.evidence];
    if (u.attestationNote) bodyParts.push(u.attestationNote);
    disputed = u.disputed;
    sources = u.sourceRefs;
    confidence = u.confidence;
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal--codex" onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        <p className="modal__sub">
          {subtitle}
          {/* How far this record can be trusted, on the record itself rather than
              buried in a rules page. v0.1 §3.4. */}
          <span className={`confidence confidence--${confidence}`}>{CONFIDENCE_LABEL[confidence]}</span>
        </p>
        {bodyParts.map((p, i) => (
          <p key={i}>{p}</p>
        ))}

        {teaches.length > 0 && (
          <>
            <h4>This battle teaches</h4>
            <ul>
              {teaches.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </>
        )}

        {/* Disputes are shown, never hidden — decision #6 and §9 of the brief. */}
        {disputed.length > 0 && (
          <section className="disputed">
            <h4>What&apos;s disputed</h4>
            <ul>
              {disputed.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          </section>
        )}

        <h4>Sources</h4>
        <ul className="sources">
          {sources.map((s) => (
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
