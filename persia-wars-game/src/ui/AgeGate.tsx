import { useState } from 'react';
import { bracketFor, isPlausibleYear, EARLIEST_YEAR } from '../game/age';
import { useGame } from '../state/store';

/**
 * The first screen on a fresh install, before the name.
 *
 * It asks for a birth YEAR rather than "are you over 13?", because a yes/no
 * question with an obvious right answer teaches a child to lie to it. Nothing
 * on this screen says what any answer unlocks, for the same reason.
 *
 * Only the resulting bracket is stored — never the year. See game/age.ts.
 */
export function AgeGate() {
  const { setAgeBracket } = useGame();
  const [year, setYear] = useState('');
  const [touched, setTouched] = useState(false);

  // The current year is read once, here, rather than inside the pure age module
  // — that module has to stay testable without stubbing the clock.
  const thisYear = new Date().getFullYear();
  const n = Number(year);
  const ok = year.length === 4 && isPlausibleYear(n, thisYear);
  const showError = touched && year.length > 0 && !ok;

  return (
    <div className="screen age-gate">
      <h2>Before we start</h2>
      <p className="muted">
        What year were you born? We only use this to set up your account safely — it is
        not saved and nobody else sees it.
      </p>

      <label className="field">
        <span>Year of birth</span>
        <input
          className="text-input"
          value={year}
          onChange={(e) => setYear(e.target.value.replace(/\D/g, '').slice(0, 4))}
          onBlur={() => setTouched(true)}
          inputMode="numeric"
          placeholder="e.g. 2014"
          autoComplete="off"
          aria-invalid={showError}
        />
      </label>

      {showError && (
        <p className="age-gate__error">
          That does not look like a year. It should be four digits between {EARLIEST_YEAR} and{' '}
          {thisYear}.
        </p>
      )}

      <button
        className="btn btn--gold"
        type="button"
        disabled={!ok}
        onClick={() => setAgeBracket(bracketFor(n, thisYear))}
      >
        CONTINUE
      </button>

      <p className="age-gate__note">
        If you are not sure, ask a grown-up. You can play the whole game either way.
      </p>
    </div>
  );
}
