// frontend/src/components/SimpleDatePicker.js
// Simplified date range picker with native HTML5 inputs
// Zero bundle size impact - uses native browser date pickers
// Dark theme matching dashboard (#142950)
// Mobile-responsive with preset quick-select buttons

import React, { useState, useEffect } from 'react';
import { Row, Col, Button, Form } from 'react-bootstrap';
import { format, subDays, subMonths, startOfMonth, endOfMonth } from 'date-fns';

/**
 * SimpleDatePicker - A lightweight date range picker component
 *
 * @param {Object} props
 * @param {Date} props.startDate - Start date (controlled)
 * @param {Date} props.endDate - End date (controlled)
 * @param {Function} props.onChange - Callback(startDate, endDate) when dates change
 * @param {boolean} props.showPresets - Show quick-select preset buttons (default: true)
 * @param {boolean} props.inline - Use inline layout (default: false)
 */
const SimpleDatePicker = ({
  startDate,
  endDate,
  onChange,
  showPresets = true,
  inline = false
}) => {
  // Internal state for validation
  const [localStartDate, setLocalStartDate] = useState('');
  const [localEndDate, setLocalEndDate] = useState('');
  const [validationError, setValidationError] = useState('');

  // Convert Date objects to YYYY-MM-DD strings for HTML5 inputs
  useEffect(() => {
    if (startDate && startDate instanceof Date && !isNaN(startDate)) {
      setLocalStartDate(format(startDate, 'yyyy-MM-dd'));
    }
    if (endDate && endDate instanceof Date && !isNaN(endDate)) {
      setLocalEndDate(format(endDate, 'yyyy-MM-dd'));
    }
  }, [startDate, endDate]);

  /**
   * Validate and propagate date changes
   */
  const handleDateChange = (type, value) => {
    const newStart = type === 'start' ? value : localStartDate;
    const newEnd = type === 'end' ? value : localEndDate;

    // Update local state immediately for responsive UI
    if (type === 'start') {
      setLocalStartDate(value);
    } else {
      setLocalEndDate(value);
    }

    // Validate both dates are present
    if (!newStart || !newEnd) {
      setValidationError('');
      return;
    }

    // Validate start < end
    const startDateObj = new Date(newStart);
    const endDateObj = new Date(newEnd);

    if (startDateObj > endDateObj) {
      setValidationError('Start date must be before end date');
      return;
    }

    // Clear validation error and propagate to parent
    setValidationError('');
    onChange(startDateObj, endDateObj);
  };

  /**
   * Preset date range handlers
   */
  const applyPreset = (preset) => {
    const now = new Date();
    let start, end;

    switch (preset) {
      case 'today':
        start = now;
        end = now;
        break;
      case 'last24h':
        start = subDays(now, 1);
        end = now;
        break;
      case 'last7d':
        start = subDays(now, 7);
        end = now;
        break;
      case 'last30d':
        start = subDays(now, 30);
        end = now;
        break;
      case 'thisMonth':
        start = startOfMonth(now);
        end = now;
        break;
      case 'lastMonth':
        start = startOfMonth(subMonths(now, 1));
        end = endOfMonth(subMonths(now, 1));
        break;
      default:
        return;
    }

    setLocalStartDate(format(start, 'yyyy-MM-dd'));
    setLocalEndDate(format(end, 'yyyy-MM-dd'));
    setValidationError('');
    onChange(start, end);
  };

  // Dark theme colors matching dashboard
  const inputStyle = {
    backgroundColor: '#2a3f5f',
    color: 'white',
    border: '1px solid #444',
    padding: '8px 12px',
    borderRadius: '4px',
    fontSize: '14px',
    width: '100%',
    height: '38px',
    cursor: 'pointer',
    // Custom styling for date input calendar icon
    colorScheme: 'dark'
  };

  const labelStyle = {
    color: '#8899aa',
    fontSize: '14px',
    marginBottom: '6px',
    fontWeight: '500'
  };

  const errorStyle = {
    color: '#ff6b6b',
    fontSize: '12px',
    marginTop: '4px',
    fontWeight: '500'
  };

  const presetButtonStyle = {
    backgroundColor: '#2a3f5f',
    color: 'white',
    border: '1px solid #444',
    fontSize: '13px',
    padding: '6px 12px',
    transition: 'all 0.2s ease'
  };

  const presets = [
    { label: 'Today', value: 'today' },
    { label: 'Last 24h', value: 'last24h' },
    { label: 'Last 7d', value: 'last7d' },
    { label: 'Last 30d', value: 'last30d' },
    { label: 'This Month', value: 'thisMonth' },
    { label: 'Last Month', value: 'lastMonth' }
  ];

  return (
    <div style={{ width: '100%' }}>
      {/* Date Inputs Row */}
      <Row className={inline ? 'g-2' : 'g-3 mb-2'}>
        <Col xs={12} sm={6} md={inline ? 6 : 5}>
          <Form.Group>
            <Form.Label style={labelStyle}>Start Date</Form.Label>
            <input
              type="date"
              value={localStartDate}
              onChange={(e) => handleDateChange('start', e.target.value)}
              style={inputStyle}
              max={localEndDate || undefined}
              className="form-control"
              aria-label="Start date"
            />
          </Form.Group>
        </Col>

        <Col xs={12} sm={6} md={inline ? 6 : 5}>
          <Form.Group>
            <Form.Label style={labelStyle}>End Date</Form.Label>
            <input
              type="date"
              value={localEndDate}
              onChange={(e) => handleDateChange('end', e.target.value)}
              style={inputStyle}
              min={localStartDate || undefined}
              className="form-control"
              aria-label="End date"
            />
          </Form.Group>
        </Col>
      </Row>

      {/* Validation Error */}
      {validationError && (
        <Row>
          <Col>
            <div style={errorStyle}>
              ⚠ {validationError}
            </div>
          </Col>
        </Row>
      )}

      {/* Preset Quick Select Buttons */}
      {showPresets && (
        <Row className="mt-2">
          <Col>
            <div className="d-flex flex-wrap gap-2">
              {presets.map((preset) => (
                <Button
                  key={preset.value}
                  variant="outline-secondary"
                  size="sm"
                  onClick={() => applyPreset(preset.value)}
                  style={presetButtonStyle}
                  onMouseEnter={(e) => {
                    e.target.style.backgroundColor = '#3a4f6f';
                    e.target.style.borderColor = '#5a7fa0';
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.backgroundColor = '#2a3f5f';
                    e.target.style.borderColor = '#444';
                  }}
                >
                  {preset.label}
                </Button>
              ))}
            </div>
          </Col>
        </Row>
      )}
    </div>
  );
};

export default SimpleDatePicker;
