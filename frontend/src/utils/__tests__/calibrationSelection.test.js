import {
  selectInBox, nearestSample, mergeSelection, selectionExtent, sampleTime, windowDays,
} from '../calibrationSelection';

const S = [
  { Tab_DateTime: '2026-10-09 10:00:00', raw_value: 0.10, offset: 0, value: 0.10, deleted: false },
  { Tab_DateTime: '2026-10-09 10:01:00', raw_value: 0.90, offset: 0, value: 0.90, deleted: false }, // spike
  { Tab_DateTime: '2026-10-09 10:02:00', raw_value: 0.11, offset: 0, value: null, deleted: true },
  { Tab_DateTime: '2026-10-09 10:03:00', raw_value: 0.12, offset: 0, value: 0.12, deleted: false },
];
const t = (s) => sampleTime(s);

test('box selects by time and level (spike only)', () => {
  const box = { xMin: t('2026-10-09 09:59:00'), xMax: t('2026-10-09 10:05:00'), yMin: 0.5, yMax: 1.0 };
  expect(selectInBox(S, box)).toEqual(['2026-10-09 10:01:00']);
});

test('box selects deleted samples at their raw level, box drawn in any direction', () => {
  const box = { xMin: t('2026-10-09 10:02:30'), xMax: t('2026-10-09 10:01:30'), yMin: 0.2, yMax: 0.0 };
  expect(selectInBox(S, box)).toEqual(['2026-10-09 10:02:00']);
});

test('box without y bounds selects the whole time range', () => {
  expect(selectInBox(S, { xMin: t('2026-10-09 10:00:30'), xMax: t('2026-10-09 10:03:00') })).toHaveLength(3);
});

test('nearest sample within distance', () => {
  expect(nearestSample(S, t('2026-10-09 10:01:10'), 30000)).toBe('2026-10-09 10:01:00');
  expect(nearestSample(S, t('2026-10-09 11:00:00'), 30000)).toBeNull();
});

test('merge: replace, add, toggle', () => {
  const cur = new Set(['a', 'b']);
  expect([...mergeSelection(cur, ['c'])]).toEqual(['c']);
  expect([...mergeSelection(cur, ['c'], 'add')].sort()).toEqual(['a', 'b', 'c']);
  expect([...mergeSelection(cur, ['b', 'c'], 'toggle')].sort()).toEqual(['a', 'c']);
});

test('extent and window length', () => {
  expect(selectionExtent(new Set(['2026-10-09 10:03:00', '2026-10-09 10:01:00'])))
    .toEqual({ start: '2026-10-09 10:01:00', end: '2026-10-09 10:03:00' });
  expect(selectionExtent(new Set())).toBeNull();
  expect(windowDays('2026-10-01T00:00', '2026-10-15T00:00')).toBe(14);
});
