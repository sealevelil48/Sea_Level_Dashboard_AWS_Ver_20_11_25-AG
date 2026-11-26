import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import DriftPanel, { buildStrip } from '../DriftPanel';

const drift = {
  reference_station: 'Ashdod',
  coverage: 0.997,
  drift_detected: true,
  episodes: [
    { start: '2026-11-02T10:00:00', end: '2026-11-02T13:59:00', duration_minutes: 239, samples: 240,
      max_deviation: 0.121, median_deviation: 0.12, type: 'plateau', suggested_offset: -0.12 },
    { start: '2026-11-05T08:00:00', end: '2026-11-05T09:29:00', duration_minutes: 89, samples: 90,
      max_deviation: 0.092, median_deviation: -0.09, type: 'step', suggested_offset: 0.09 },
  ],
  slow_drift: { mm_per_day: 4.2, ci_mm_per_day: [3.9, 4.5], since: '2026-11-01T00:00:00', total_change_m: 0.03 },
  deviation: [
    { t: '2026-11-01T00:00:00', d: 0 }, { t: '2026-11-02T11:00:00', d: 0.12 },
    { t: '2026-11-04T00:00:00', d: 0.0 }, { t: '2026-11-05T08:30:00', d: -0.09 }, { t: '2026-11-06T00:00:00', d: 0 },
  ],
};

test('renders nothing without results', () => {
  const { container } = render(<DriftPanel drift={null} threshold={0.05} onApplyEpisode={() => {}} />);
  expect(container).toBeEmptyDOMElement();
});

test('lists each episode separately with type and duration', () => {
  render(<DriftPanel drift={drift} threshold={0.05} onApplyEpisode={() => {}} />);
  expect(screen.getByText('2 drift episodes')).toBeInTheDocument();
  expect(screen.getByText(/11-02 10:00 → 11-02 13:59/)).toBeInTheDocument();
  expect(screen.getByText(/Plateau \(returns\)/)).toBeInTheDocument();
  expect(screen.getByText(/Step \(persists\)/)).toBeInTheDocument();
  expect(screen.getByText(/coverage 100%/)).toBeInTheDocument();
});

test('"Correct this" hands the episode to the form', () => {
  const onApply = jest.fn();
  render(<DriftPanel drift={drift} threshold={0.05} onApplyEpisode={onApply} />);
  fireEvent.click(screen.getByRole('button', { name: 'Correct episode starting 11-05 08:00' }));
  expect(onApply).toHaveBeenCalledWith(drift.episodes[1]);
});

test('slow drift is reported but labelled as not auto-corrected', () => {
  render(<DriftPanel drift={drift} threshold={0.05} onApplyEpisode={() => {}} />);
  expect(screen.getByRole('status')).toHaveTextContent('Slow drift +4.2 mm/day');
  expect(screen.getByRole('status')).toHaveTextContent('Not corrected automatically');
});

test('no-drift result', () => {
  render(<DriftPanel drift={{ ...drift, episodes: [], slow_drift: null, drift_detected: false }}
                     threshold={0.05} onApplyEpisode={() => {}} />);
  expect(screen.getByText('No drift')).toBeInTheDocument();
  expect(screen.queryByRole('button')).toBeNull();
});

test('strip geometry: band is symmetric around zero, episodes shaded in time order', () => {
  const s = buildStrip(drift.deviation, 0.05, drift.episodes);
  expect(s.bandTop + s.bandHeight / 2).toBeCloseTo(s.zero, 5);
  expect(s.shaded).toHaveLength(2);
  expect(s.shaded[0].x).toBeLessThan(s.shaded[1].x);
  expect(buildStrip([], 0.05, [])).toBeNull();
});
