import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Button, Form, InputGroup } from 'react-bootstrap';

/**
 * Offset entry for calibration (Phase 3, step 1): a typed number and a slider bound to one value.
 *
 * - The text field keeps what the operator is typing ("-", "0.", "-.05"), so negative and
 *   partial numbers can be entered. A number is committed as soon as the text parses, and
 *   always on blur/Enter; invalid text never reaches Preview or Commit.
 * - Hard limit ±10 m (same as the API). Above ±1 m shows a warning but is allowed.
 * - The slider covers ±0.5 m around zero for fine control (1 mm steps); it widens to include
 *   a typed value beyond that, so it never pins at an edge.
 * - Arrow keys nudge by 1 mm (Shift: 1 cm); the buttons do the same.
 * - A suggestion from Auto-Suggest is shown with a "Use" button instead of overwriting input.
 *
 * Props:
 *   value        number — current offset in metres (filters.calibrationOffset)
 *   onChange     (number) => void — called with a finite, in-range number only
 *   onValidity   (boolean) => void — false while the text is not a usable number
 *   suggestion   { value: number, confidence?: string } | null
 *   disabled     boolean
 */
export const MAX_OFFSET_M = 10;
export const WARN_OFFSET_M = 1;
const SLIDER_SPAN_M = 0.5;
const STEP = 0.001;
const BIG_STEP = 0.01;

// Text that is a number in progress: "", "-", "+", ".", "-.", "0.", "-0.0"
const PARTIAL_RE = /^[+-]?(\d+)?(\.\d*)?$/;

export function parseOffset(text) {
  const t = String(text ?? '').trim().replace(',', '.');
  if (t === '' || t === '-' || t === '+' || t === '.' || t === '-.' || t === '+.') {
    return { ok: false, partial: true, error: 'Enter a number in metres' };
  }
  if (!PARTIAL_RE.test(t)) return { ok: false, partial: false, error: 'Enter a number in metres' };
  const n = Number(t);
  if (!Number.isFinite(n)) return { ok: false, partial: false, error: 'Enter a number in metres' };
  if (Math.abs(n) > MAX_OFFSET_M) return { ok: false, partial: false, error: `Max ±${MAX_OFFSET_M} m` };
  return { ok: true, value: n, warn: Math.abs(n) > WARN_OFFSET_M };
}

const round3 = (n) => Math.round(n * 1000) / 1000;
const fmt = (n) => (Number.isFinite(n) ? `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(3)}` : '—');
const NUDGE_STYLE = { color: '#C8D6E8', borderColor: '#2a3f5f', background: 'transparent' };
const clamp = (n) => Math.max(-MAX_OFFSET_M, Math.min(MAX_OFFSET_M, n));

const OffsetInput = ({ value, onChange, onValidity, suggestion, disabled = false, id = 'calibration-offset' }) => {
  const numeric = Number.isFinite(Number(value)) ? Number(value) : 0;
  const [text, setText] = useState(() => String(numeric));
  const editing = useRef(false);          // true while typing: don't overwrite the text from props
  const [focused, setFocused] = useState(false); // drives error display (state, so blur re-renders)

  // Follow external changes (slider, Suggest "Use", reset) unless the operator is typing.
  useEffect(() => {
    if (!editing.current) setText(String(numeric));
  }, [numeric]);

  const parsed = useMemo(() => parseOffset(text), [text]);

  useEffect(() => {
    if (onValidity) onValidity(parsed.ok);
  }, [parsed.ok, onValidity]);

  const commit = (n) => {
    const v = round3(clamp(n));
    setText(String(v));
    onChange(v);
  };

  const handleText = (e) => {
    const t = e.target.value;
    if (t !== '' && !PARTIAL_RE.test(t.replace(',', '.'))) return; // ignore letters etc.
    editing.current = true;
    setText(t);
    const p = parseOffset(t);
    if (p.ok) onChange(p.value); // live preview while typing a valid number
  };

  const handleBlur = () => {
    editing.current = false;
    setFocused(false);
    const p = parseOffset(text);
    if (p.ok) commit(p.value);
    // invalid text stays visible with its error; Preview/Commit are disabled via onValidity
  };

  const nudge = (delta) => commit((parsed.ok ? parsed.value : numeric) + delta);

  const handleKey = (e) => {
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      e.preventDefault();
      const step = e.shiftKey ? BIG_STEP : STEP;
      nudge(e.key === 'ArrowUp' ? step : -step);
    } else if (e.key === 'Enter') {
      handleBlur();
    }
  };

  const span = Math.max(SLIDER_SPAN_M, Math.ceil(Math.abs(numeric) * 10) / 10);
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  // A number in progress ("-", "") is not an error while the field has focus.
  const showError = !parsed.ok && !(parsed.partial && focused);

  return (
    <Form.Group className="mb-2">
      <Form.Label htmlFor={id} className="small mb-1" style={{ fontSize: '0.7rem' }}>
        Offset (metres)
      </Form.Label>

      <InputGroup size="sm" style={{ flexWrap: 'nowrap' }}>
        <Button variant="outline-secondary" onClick={() => nudge(-STEP)} disabled={disabled}
                aria-label="Decrease by 1 mm" style={{ ...NUDGE_STYLE, minWidth: 32 }}>−</Button>
        <Form.Control
          id={id}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          spellCheck={false}
          value={text}
          onChange={handleText}
          onFocus={() => setFocused(true)}
          onBlur={handleBlur}
          onKeyDown={handleKey}
          disabled={disabled}
          isInvalid={showError}
          aria-invalid={showError}
          aria-describedby={`${showError ? errorId : ''} ${hintId}`.trim()}
          placeholder="0.000"
          style={{ textAlign: 'center', fontVariantNumeric: 'tabular-nums', fontSize: '0.9rem', minWidth: 0 }}
        />
        <InputGroup.Text style={{ fontSize: '0.75rem', padding: '0 6px', background: '#0c1c35', color: '#C8D6E8', borderColor: '#2a3f5f' }}>m</InputGroup.Text>
        <Button variant="outline-secondary" onClick={() => nudge(STEP)} disabled={disabled}
                aria-label="Increase by 1 mm" style={{ ...NUDGE_STYLE, minWidth: 32 }}>+</Button>
      </InputGroup>

      {showError && (
        <div id={errorId} role="alert" className="text-danger mt-1" style={{ fontSize: '0.7rem' }}>
          {parsed.error}
        </div>
      )}
      {parsed.ok && parsed.warn && (
        <div className="text-warning mt-1" style={{ fontSize: '0.7rem' }}>
          Large correction ({fmt(parsed.value)} m) — double-check before committing.
        </div>
      )}

      <div className="d-flex align-items-center gap-1 mt-2">
        <Button variant="outline-secondary" size="sm" className="py-0 px-1" onClick={() => nudge(-BIG_STEP)}
                disabled={disabled} aria-label="Decrease by 1 cm" style={{ ...NUDGE_STYLE, fontSize: '0.65rem', minHeight: 24 }}>−1cm</Button>
        <Form.Range
          aria-label="Offset slider"
          min={-span}
          max={span}
          step={STEP}
          value={clamp(numeric)}
          onChange={(e) => { editing.current = false; commit(Number(e.target.value)); }}
          disabled={disabled}
          style={{ flex: 1, minWidth: 0 }}
        />
        <Button variant="outline-secondary" size="sm" className="py-0 px-1" onClick={() => nudge(BIG_STEP)}
                disabled={disabled} aria-label="Increase by 1 cm" style={{ ...NUDGE_STYLE, fontSize: '0.65rem', minHeight: 24 }}>+1cm</Button>
      </div>
      <div className="d-flex justify-content-between" aria-hidden="true"
           style={{ fontSize: '0.65rem', color: '#8FA3BD', fontVariantNumeric: 'tabular-nums', padding: '0 38px' }}>
        <span>{fmt(-span)}</span><span>0</span><span>{fmt(span)}</span>
      </div>

      {suggestion && Number.isFinite(suggestion.value) && (
        <div className="d-flex align-items-center justify-content-between gap-2 mt-1" style={{ fontSize: '0.72rem' }}>
          <span style={{ color: '#7FD3FF' }}>
            Suggested {fmt(suggestion.value)} m{suggestion.confidence ? ` (${suggestion.confidence})` : ''}
          </span>
          <Button size="sm" variant="outline-info" className="py-0 px-2" style={{ fontSize: '0.7rem' }}
                  onClick={() => { editing.current = false; commit(suggestion.value); }} disabled={disabled}>
            Use
          </Button>
        </div>
      )}

      <small id={hintId} className="d-block mt-1" style={{ fontSize: '0.65rem', color: '#8FA3BD' }}>
        Type a value or drag. ↑/↓ = 1 mm, Shift = 1 cm.
      </small>
    </Form.Group>
  );
};

export default OffsetInput;
