import type { Unit } from '../content/types';
import { CLASS_LABEL, listClasses } from './labels';
import { UnitGlyph } from './UnitGlyph';

interface Props {
  unit: Unit;
  side?: 'a' | 'b';
  onClick?: () => void;
  disabled?: boolean;
  showStats?: boolean;
  /**
   * `compact` stacks the card and trims it to what a pick actually needs, so
   * three of them sit side by side on a phone without pushing the field off
   * screen. The blurb survives — it is the history, and it is the reason the
   * game exists — but clamped to two lines.
   */
  variant?: 'full' | 'compact';
  /** Overrides the glyph size — a widened comeback hand needs smaller art. */
  glyphSize?: number;
}

export function UnitCard({
  unit,
  side = 'a',
  onClick,
  disabled,
  showStats = true,
  variant = 'full',
  glyphSize,
}: Props) {
  // The card carries the hook only; the sourced paragraph lives in the codex,
  // where there is room for it and where it is shown to everyone.
  const blurb = unit.blurb;
  const Tag = onClick ? 'button' : 'div';
  const compact = variant === 'compact';

  return (
    <Tag
      className={`unit-card unit-card--${variant} side-${side}${disabled ? ' is-disabled' : ''}`}
      onClick={onClick}
      disabled={onClick ? disabled : undefined}
      type={onClick ? 'button' : undefined}
    >
      <div className="unit-card__art">
        <UnitGlyph kind={unit.art.silhouette} size={glyphSize ?? (compact ? 46 : 48)} unitId={unit.id} />
      </div>
      <div className="unit-card__text">
        <h3>{unit.name}</h3>
        <p className="unit-card__class">{CLASS_LABEL[unit.class]}</p>
        <p className="unit-card__blurb">{blurb}</p>

        {showStats && (
          <>
            <dl className="stats">
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
            {compact ? (
              // One line instead of two: the arrows carry the meaning, and the
              // full wording is still on the card in the collection.
              <p className="matchup matchup--tight">
                <span className="good">▲ {listClasses(unit.counters)}</span>
                <span className="bad">▼ {listClasses(unit.counteredBy)}</span>
              </p>
            ) : (
              <>
                <p className="matchup">
                  <span className="good">Strong vs </span>
                  {listClasses(unit.counters)}
                </p>
                <p className="matchup">
                  <span className="bad">Weak vs </span>
                  {listClasses(unit.counteredBy)}
                </p>
              </>
            )}
          </>
        )}
      </div>
    </Tag>
  );
}
