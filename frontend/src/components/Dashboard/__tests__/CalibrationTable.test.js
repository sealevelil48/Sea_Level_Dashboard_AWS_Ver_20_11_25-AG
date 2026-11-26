import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import CalibrationTable, { parseTyped } from '../CalibrationTable';

const samples = [
  { Tab_DateTime: '2026-10-09 10:00:00', raw_value: 0.1, offset: 0, value: 0.1, deleted: false },
  { Tab_DateTime: '2026-10-09 10:01:00', raw_value: 0.9, offset: 0, value: null, deleted: true },
];

const setup = (over = {}) => {
  const props = {
    show: true, onHide: jest.fn(), station: 'Haifa', samples, selection: new Set(), edits: {},
    onToggle: jest.fn(), onSetSelected: jest.fn(), onEdit: jest.fn(), onClearEdits: jest.fn(),
    onPreviewEdits: jest.fn(), ...over,
  };
  render(<CalibrationTable {...props} />);
  return props;
};

test('parseTyped accepts comma decimals and rejects text', () => {
  expect(parseTyped('0,125')).toBe(0.125);
  expect(parseTyped('')).toBeNull();
  expect(parseTyped('abc')).toBeUndefined();
});

test('shows raw and validated values and the deleted state', () => {
  setup();
  expect(screen.getByText('2026-10-09 10:01:00')).toBeInTheDocument();
  expect(screen.getByText('deleted')).toBeInTheDocument();
  expect(screen.getByText('0.900')).toBeInTheDocument();
});

test('typing a value and pressing Enter records an edit; invalid text does not', () => {
  const p = setup();
  const input = screen.getByLabelText('New value for 2026-10-09 10:00:00');
  fireEvent.change(input, { target: { value: '0.123' } });
  fireEvent.keyDown(input, { key: 'Enter' });
  expect(p.onEdit).toHaveBeenCalledWith('2026-10-09 10:00:00', 0.123);
  p.onEdit.mockClear();
  fireEvent.change(input, { target: { value: 'x' } });
  fireEvent.keyDown(input, { key: 'Enter' });
  expect(p.onEdit).not.toHaveBeenCalled();
});

test('row checkbox toggles the shared selection; preview needs typed values', () => {
  const p = setup({ edits: { '2026-10-09 10:00:00': 0.2 } });
  fireEvent.click(screen.getByLabelText('Select 2026-10-09 10:01:00'));
  expect(p.onToggle).toHaveBeenCalledWith('2026-10-09 10:01:00');
  fireEvent.click(screen.getByText('Preview typed values'));
  expect(p.onPreviewEdits).toHaveBeenCalled();
});
