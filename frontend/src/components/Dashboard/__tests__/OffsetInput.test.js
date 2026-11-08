import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import OffsetInput, { parseOffset } from '../OffsetInput';

function Harness({ initial = 0, suggestion = null }) {
  const [value, setValue] = useState(initial);
  const [valid, setValid] = useState(true);
  return (
    <>
      <OffsetInput value={value} onChange={setValue} onValidity={setValid} suggestion={suggestion} />
      <output data-testid="value">{String(value)}</output>
      <output data-testid="valid">{String(valid)}</output>
    </>
  );
}

const field = () => screen.getByLabelText('Offset (metres)');
const value = () => Number(screen.getByTestId('value').textContent);
const valid = () => screen.getByTestId('valid').textContent === 'true';

// Simulate typing one keystroke at a time (fireEvent is wrapped in act(), so React 18 flushes).
function typeFresh(text) {
  const el = field();
  fireEvent.focus(el);
  fireEvent.change(el, { target: { value: '' } });
  for (let i = 1; i <= text.length; i++) {
    fireEvent.change(el, { target: { value: text.slice(0, i) } });
  }
}

describe('parseOffset', () => {
  test.each([
    ['-0.2', -0.2], ['-.05', -0.05], ['0.0035', 0.0035], ['+0.1', 0.1], ['0,25', 0.25], ['10', 10], ['-10', -10],
  ])('accepts %s', (t, n) => {
    const p = parseOffset(t);
    expect(p.ok).toBe(true);
    expect(p.value).toBeCloseTo(n, 6);
  });

  test.each(['', '-', '.', '-.'])('treats %p as a number in progress', (t) => {
    const p = parseOffset(t);
    expect(p.ok).toBe(false);
    expect(p.partial).toBe(true);
  });

  test.each(['abc', '1e5', '--1', '1.2.3', '10.001', '-11'])('rejects %p', (t) => {
    expect(parseOffset(t).ok).toBe(false);
  });

  test('warns above 1 m', () => {
    expect(parseOffset('1.5').warn).toBe(true);
    expect(parseOffset('0.5').warn).toBe(false);
  });
});

describe('OffsetInput', () => {
  test('typing a negative value works keystroke by keystroke (regression: "-" reset to 0)', () => {
    render(<Harness />);
    typeFresh('-0.2');
    expect(field()).toHaveValue('-0.2');
    expect(value()).toBeCloseTo(-0.2);
    expect(valid()).toBe(true);
  });

  test('accepts -.05 and 0.0035 (rounded to mm on blur)', () => {
    render(<Harness />);
    typeFresh('-.05');
    expect(value()).toBeCloseTo(-0.05);
    typeFresh('0.0035');
    fireEvent.blur(field());
    expect(value()).toBeCloseTo(0.004, 6);
  });

  test('a lone "-" is accepted while typing but blocks Preview/Commit', () => {
    render(<Harness initial={0.1} />);
    typeFresh('-');
    expect(field()).toHaveValue('-');
    expect(valid()).toBe(false);
    expect(value()).toBeCloseTo(0.1);         // last valid value is kept, never a silent 0
    expect(screen.queryByRole('alert')).toBeNull(); // no error while still typing
    fireEvent.blur(field());
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a number in metres');
  });

  test('empty field shows an error instead of becoming 0', () => {
    render(<Harness initial={0.3} />);
    fireEvent.focus(field());
    fireEvent.change(field(), { target: { value: '' } });
    fireEvent.blur(field());
    expect(valid()).toBe(false);
    expect(value()).toBeCloseTo(0.3);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  test('values beyond ±10 m are rejected', () => {
    render(<Harness />);
    typeFresh('12');
    fireEvent.blur(field());
    expect(valid()).toBe(false);
    expect(screen.getByRole('alert')).toHaveTextContent('Max ±10 m');
  });

  test('letters are ignored', () => {
    render(<Harness />);
    typeFresh('0.1x');
    expect(field()).toHaveValue('0.1');
  });

  test('above 1 m warns but is allowed', () => {
    render(<Harness />);
    typeFresh('1.5');
    expect(valid()).toBe(true);
    expect(screen.getByText(/Large correction/)).toBeInTheDocument();
  });

  test('arrow keys nudge 1 mm, Shift 1 cm', () => {
    render(<Harness initial={0} />);
    fireEvent.keyDown(field(), { key: 'ArrowUp' });
    expect(value()).toBeCloseTo(0.001);
    fireEvent.keyDown(field(), { key: 'ArrowDown', shiftKey: true });
    expect(value()).toBeCloseTo(-0.009);
  });

  test('nudge buttons', () => {
    render(<Harness initial={0} />);
    fireEvent.click(screen.getByRole('button', { name: 'Increase by 1 cm' }));
    fireEvent.click(screen.getByRole('button', { name: 'Decrease by 1 mm' }));
    expect(value()).toBeCloseTo(0.009);
    expect(field()).toHaveValue('0.009');
  });

  test('slider and text stay in sync', () => {
    render(<Harness initial={0} />);
    fireEvent.change(screen.getByLabelText('Offset slider'), { target: { value: '-0.123' } });
    expect(value()).toBeCloseTo(-0.123);
    expect(field()).toHaveValue('-0.123');
    typeFresh('0.25');
    expect(screen.getByLabelText('Offset slider')).toHaveValue('0.25');
  });

  test('slider gives fine control (±0.5 m) and widens for larger typed values', () => {
    render(<Harness initial={0} />);
    expect(screen.getByLabelText('Offset slider')).toHaveAttribute('max', '0.5');
    typeFresh('2.34');
    fireEvent.blur(field());
    expect(screen.getByLabelText('Offset slider')).toHaveAttribute('max', '2.4');
  });

  test('suggestion is offered, not applied, until "Use"', () => {
    render(<Harness initial={0.05} suggestion={{ value: -0.2003, confidence: 'high' }} />);
    expect(value()).toBeCloseTo(0.05);
    expect(screen.getByText(/Suggested −0.200 m \(high\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Use' }));
    expect(value()).toBeCloseTo(-0.2);
    expect(field()).toHaveValue('-0.2');
  });
});
