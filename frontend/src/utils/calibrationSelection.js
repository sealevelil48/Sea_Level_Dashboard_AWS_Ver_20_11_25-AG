/**
 * Point selection for the calibration editor (graph box/click selection and the table).
 *
 * Samples come from POST /api/calibration/samples:
 *   { Tab_DateTime: "2026-10-09 10:20:00", raw_value, offset, value (null = deleted), deleted }
 * Tab_DateTime is local wall-clock time without a zone; it is the sample's identity and is sent
 * back unchanged as `timestamps` / `values[].Tab_DateTime`.
 */

/** Parse a DB timestamp as local time (same as the chart does). */
export const sampleTime = (ts) => new Date(String(ts).replace(' ', 'T')).getTime();

/** The level a sample is drawn at: validated value, or the raw value when it is deleted. */
export const sampleLevel = (s) => (s.value ?? s.raw_value);

/**
 * Timestamps of samples inside a rectangle drawn on the chart.
 * box = { xMin, xMax, yMin, yMax } in chart units (ms since epoch, metres); y bounds optional.
 */
export function selectInBox(samples, box) {
  if (!Array.isArray(samples) || !box) return [];
  const x0 = Math.min(box.xMin, box.xMax);
  const x1 = Math.max(box.xMin, box.xMax);
  const hasY = Number.isFinite(box.yMin) && Number.isFinite(box.yMax);
  const y0 = hasY ? Math.min(box.yMin, box.yMax) : -Infinity;
  const y1 = hasY ? Math.max(box.yMin, box.yMax) : Infinity;
  const out = [];
  for (const s of samples) {
    const t = sampleTime(s.Tab_DateTime);
    const y = sampleLevel(s);
    if (t >= x0 && t <= x1 && y != null && y >= y0 && y <= y1) out.push(s.Tab_DateTime);
  }
  return out;
}

/** Timestamp of the sample closest in time to x (ms), or null if none is within maxDistanceMs. */
export function nearestSample(samples, x, maxDistanceMs = Infinity) {
  if (!Array.isArray(samples) || samples.length === 0 || !Number.isFinite(x)) return null;
  let best = null;
  let bestDist = Infinity;
  for (const s of samples) {
    const d = Math.abs(sampleTime(s.Tab_DateTime) - x);
    if (d < bestDist) { bestDist = d; best = s.Tab_DateTime; }
  }
  return bestDist <= maxDistanceMs ? best : null;
}

/** Combine a new selection with the current one: replace, add (Shift) or toggle (Ctrl/⌘). */
export function mergeSelection(current, picked, how = 'replace') {
  if (how === 'replace') return new Set(picked);
  const next = new Set(current);
  if (how === 'add') picked.forEach((t) => next.add(t));
  else picked.forEach((t) => (next.has(t) ? next.delete(t) : next.add(t)));
  return next;
}

/** Earliest and latest selected timestamp (for "fit window to selection"). */
export function selectionExtent(selection) {
  const list = [...(selection || [])];
  if (!list.length) return null;
  list.sort((a, b) => sampleTime(a) - sampleTime(b));
  return { start: list[0], end: list[list.length - 1] };
}

/** Days between two datetime-local strings. */
export const windowDays = (start, end) => (sampleTime(end) - sampleTime(start)) / 86400000;
