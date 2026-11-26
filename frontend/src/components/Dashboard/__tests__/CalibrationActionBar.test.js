import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import CalibrationActionBar from '../CalibrationActionBar';

const base = {
  mode: 'relative', offset: 0, station: 'Haifa', error: null, isCommitting: false, isReverting: false,
  commitResult: null, onConfirm: jest.fn(), onCancel: jest.fn(), onRevert: jest.fn(),
};
const preview = (over) => ({
  start_datetime: '2026-10-08T12:00:00', end_datetime: '2026-10-08T18:00:00', rows_affected: 361,
  change_summary: { min: -0.2, max: -0.19, mean: -0.2 },
  parameters: { reference_station: 'Acre', strength: 'follow', min_coverage: 0.95, tolerance_seconds: 120 },
  ...over,
});

test('below the required coverage: clear warning and commit disabled', () => {
  render(<CalibrationActionBar {...base} preview={preview({ coverage: 0.834, commit_allowed: false })} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Reference covers 83% of the window — 95% is required');
  expect(screen.getByRole('alert')).toHaveTextContent('use Level shift');
  expect(screen.getByRole('button', { name: /Review & commit/ })).toBeDisabled();
});

test('enough coverage: coverage shown, commit allowed, listed in the confirmation', () => {
  render(<CalibrationActionBar {...base} preview={preview({ coverage: 0.997, commit_allowed: true })} />);
  expect(screen.queryByRole('alert')).toBeNull();
  expect(screen.getByText(/reference coverage 100%/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Review & commit/ }));
  expect(screen.getByText('Reference coverage')).toBeInTheDocument();
  expect(screen.getByText(/Acre, ±120 s/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Commit correction' })).toBeEnabled();
});

test('offset mode is unaffected by coverage logic', () => {
  render(<CalibrationActionBar {...base} mode="offset" offset={-0.08}
                               preview={preview({ coverage: undefined, commit_allowed: true, parameters: { offset: -0.08 } })} />);
  expect(screen.getByRole('button', { name: /Review & commit/ })).toBeEnabled();
  expect(screen.getByText(/−0.080|-0.080/)).toBeInTheDocument();
});
