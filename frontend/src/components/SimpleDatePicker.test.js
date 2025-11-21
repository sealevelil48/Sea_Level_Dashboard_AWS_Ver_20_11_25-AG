// frontend/src/components/SimpleDatePicker.test.js
// Test suite for SimpleDatePicker component

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SimpleDatePicker from './SimpleDatePicker';
import { format, subDays } from 'date-fns';

describe('SimpleDatePicker', () => {
  const mockOnChange = jest.fn();
  const startDate = new Date('2024-01-01');
  const endDate = new Date('2024-01-31');

  beforeEach(() => {
    mockOnChange.mockClear();
  });

  describe('Basic Rendering', () => {
    test('renders start and end date inputs', () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      expect(screen.getByLabelText('Start date')).toBeInTheDocument();
      expect(screen.getByLabelText('End date')).toBeInTheDocument();
    });

    test('displays preset buttons by default', () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      expect(screen.getByText('Today')).toBeInTheDocument();
      expect(screen.getByText('Last 24h')).toBeInTheDocument();
      expect(screen.getByText('Last 7d')).toBeInTheDocument();
      expect(screen.getByText('Last 30d')).toBeInTheDocument();
      expect(screen.getByText('This Month')).toBeInTheDocument();
      expect(screen.getByText('Last Month')).toBeInTheDocument();
    });

    test('hides preset buttons when showPresets is false', () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
          showPresets={false}
        />
      );

      expect(screen.queryByText('Today')).not.toBeInTheDocument();
      expect(screen.queryByText('Last 24h')).not.toBeInTheDocument();
    });
  });

  describe('Date Input Handling', () => {
    test('displays initial dates correctly', () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const startInput = screen.getByLabelText('Start date');
      const endInput = screen.getByLabelText('End date');

      expect(startInput.value).toBe('2024-01-01');
      expect(endInput.value).toBe('2024-01-31');
    });

    test('calls onChange when start date is modified', async () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const startInput = screen.getByLabelText('Start date');
      fireEvent.change(startInput, { target: { value: '2024-01-15' } });

      await waitFor(() => {
        expect(mockOnChange).toHaveBeenCalledWith(
          new Date('2024-01-15'),
          new Date('2024-01-31')
        );
      });
    });

    test('calls onChange when end date is modified', async () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const endInput = screen.getByLabelText('End date');
      fireEvent.change(endInput, { target: { value: '2024-02-15' } });

      await waitFor(() => {
        expect(mockOnChange).toHaveBeenCalledWith(
          new Date('2024-01-01'),
          new Date('2024-02-15')
        );
      });
    });
  });

  describe('Validation', () => {
    test('shows error when start date is after end date', async () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const startInput = screen.getByLabelText('Start date');
      fireEvent.change(startInput, { target: { value: '2024-02-15' } });

      await waitFor(() => {
        expect(screen.getByText(/Start date must be before end date/i)).toBeInTheDocument();
      });

      // Should not call onChange when invalid
      expect(mockOnChange).not.toHaveBeenCalled();
    });

    test('clears error when dates become valid', async () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const startInput = screen.getByLabelText('Start date');
      const endInput = screen.getByLabelText('End date');

      // Set invalid range
      fireEvent.change(startInput, { target: { value: '2024-02-15' } });
      await waitFor(() => {
        expect(screen.getByText(/Start date must be before end date/i)).toBeInTheDocument();
      });

      // Fix the range
      fireEvent.change(endInput, { target: { value: '2024-03-15' } });
      await waitFor(() => {
        expect(screen.queryByText(/Start date must be before end date/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Preset Buttons', () => {
    test('Last 24h preset sets correct date range', () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const button = screen.getByText('Last 24h');
      fireEvent.click(button);

      expect(mockOnChange).toHaveBeenCalled();
      const [start, end] = mockOnChange.mock.calls[0];

      // Check that start is approximately 1 day before end
      const diffInHours = (end - start) / (1000 * 60 * 60);
      expect(diffInHours).toBeCloseTo(24, 0);
    });

    test('Last 7d preset sets correct date range', () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const button = screen.getByText('Last 7d');
      fireEvent.click(button);

      expect(mockOnChange).toHaveBeenCalled();
      const [start, end] = mockOnChange.mock.calls[0];

      const diffInDays = (end - start) / (1000 * 60 * 60 * 24);
      expect(diffInDays).toBeCloseTo(7, 0);
    });

    test('Last 30d preset sets correct date range', () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const button = screen.getByText('Last 30d');
      fireEvent.click(button);

      expect(mockOnChange).toHaveBeenCalled();
      const [start, end] = mockOnChange.mock.calls[0];

      const diffInDays = (end - start) / (1000 * 60 * 60 * 24);
      expect(diffInDays).toBeCloseTo(30, 0);
    });

    test('Today preset sets same start and end date', () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const button = screen.getByText('Today');
      fireEvent.click(button);

      expect(mockOnChange).toHaveBeenCalled();
      const [start, end] = mockOnChange.mock.calls[0];

      expect(format(start, 'yyyy-MM-dd')).toBe(format(end, 'yyyy-MM-dd'));
    });
  });

  describe('Accessibility', () => {
    test('date inputs have proper labels', () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const startInput = screen.getByLabelText('Start date');
      const endInput = screen.getByLabelText('End date');

      expect(startInput).toHaveAttribute('type', 'date');
      expect(endInput).toHaveAttribute('type', 'date');
    });

    test('buttons are keyboard accessible', () => {
      render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const button = screen.getByText('Last 7d');
      expect(button.tagName).toBe('BUTTON');
    });
  });

  describe('Edge Cases', () => {
    test('handles invalid Date objects gracefully', () => {
      const invalidDate = new Date('invalid');

      render(
        <SimpleDatePicker
          startDate={invalidDate}
          endDate={endDate}
          onChange={mockOnChange}
        />
      );

      const startInput = screen.getByLabelText('Start date');
      expect(startInput.value).toBe('');
    });

    test('handles null dates', () => {
      render(
        <SimpleDatePicker
          startDate={null}
          endDate={null}
          onChange={mockOnChange}
        />
      );

      const startInput = screen.getByLabelText('Start date');
      const endInput = screen.getByLabelText('End date');

      expect(startInput.value).toBe('');
      expect(endInput.value).toBe('');
    });

    test('handles undefined dates', () => {
      render(
        <SimpleDatePicker
          startDate={undefined}
          endDate={undefined}
          onChange={mockOnChange}
        />
      );

      const startInput = screen.getByLabelText('Start date');
      const endInput = screen.getByLabelText('End date');

      expect(startInput.value).toBe('');
      expect(endInput.value).toBe('');
    });
  });

  describe('Responsive Design', () => {
    test('renders with inline layout when prop is set', () => {
      const { container } = render(
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={mockOnChange}
          inline={true}
        />
      );

      // Check for inline-specific classes
      const row = container.querySelector('.row.g-2');
      expect(row).toBeInTheDocument();
    });
  });
});
