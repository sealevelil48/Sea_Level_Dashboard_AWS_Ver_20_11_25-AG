import React from 'react';
import { Card, Button } from 'react-bootstrap';
import './DeltaDisplay.css';

/**
 * DeltaDisplay Component
 *
 * Displays calculated delta information between two selected stations
 * Includes station names, values, timestamps, and calculated delta with visual indicators
 *
 * Props:
 * - station1: { name, value, timestamp } - First station data
 * - station2: { name, value, timestamp } - Second station data
 * - delta: Number - Calculated difference (station2 - station1)
 * - onClear: Function - Callback to clear the selection
 * - position: String - 'overlay' | 'panel' | 'tooltip' (default: 'overlay')
 * - isMobile: Boolean - Mobile device flag for responsive styling
 */
const DeltaDisplay = ({
  station1,
  station2,
  delta,
  onClear,
  position = 'overlay',
  isMobile = false
}) => {
  // Don't render if we don't have both stations
  if (!station1 || !station2) {
    return null;
  }

  // Determine delta color and arrow based on value
  const getDeltaColor = () => {
    if (delta > 0) return 'positive';
    if (delta < 0) return 'negative';
    return 'neutral';
  };

  const getDeltaArrow = () => {
    if (delta > 0) return '↑';
    if (delta < 0) return '↓';
    return '→';
  };

  // Format timestamp for display
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    try {
      const date = new Date(timestamp);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return timestamp;
    }
  };

  // Format value to 3 decimal places
  const formatValue = (value) => {
    if (value === null || value === undefined || isNaN(value)) return 'N/A';
    return Number(value).toFixed(3);
  };

  const deltaColor = getDeltaColor();
  const deltaArrow = getDeltaArrow();

  // Render different layouts based on position prop
  if (position === 'tooltip') {
    return (
      <div className={`delta-tooltip ${isMobile ? 'mobile' : ''}`}>
        <div className="delta-tooltip-content">
          <div className="delta-tooltip-header">
            <span className="delta-tooltip-title">Station Comparison</span>
            <Button
              variant="link"
              size="sm"
              onClick={onClear}
              className="delta-close-btn"
              aria-label="Clear selection"
            >
              ✕
            </Button>
          </div>
          <div className="delta-tooltip-body">
            <div className="station-info compact">
              <span className="station-name">{station1.name}</span>
              <span className="station-value">{formatValue(station1.value)} m</span>
            </div>
            <div className={`delta-arrow ${deltaColor}`}>{deltaArrow}</div>
            <div className="station-info compact">
              <span className="station-name">{station2.name}</span>
              <span className="station-value">{formatValue(station2.value)} m</span>
            </div>
            <div className={`delta-result compact ${deltaColor}`}>
              <span className="delta-label">Δ</span>
              <span className="delta-value">{formatValue(Math.abs(delta))} m</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (position === 'panel') {
    return (
      <Card className={`delta-panel ${isMobile ? 'mobile' : ''}`}>
        <Card.Body>
          <div className="delta-panel-header">
            <h6 className="delta-panel-title">Station Comparison</h6>
            <Button
              variant="outline-danger"
              size="sm"
              onClick={onClear}
              className="delta-clear-btn"
            >
              Clear Selection
            </Button>
          </div>

          <div className="delta-panel-content">
            <div className="station-card">
              <div className="station-header">
                <span className="station-label">Station 1</span>
                <span className="station-name">{station1.name}</span>
              </div>
              <div className="station-data">
                <div className="data-row">
                  <span className="data-label">Sea Level:</span>
                  <span className="data-value">{formatValue(station1.value)} m</span>
                </div>
                <div className="data-row">
                  <span className="data-label">Timestamp:</span>
                  <span className="data-value timestamp">{formatTimestamp(station1.timestamp)}</span>
                </div>
              </div>
            </div>

            <div className={`delta-divider ${deltaColor}`}>
              <div className="delta-arrow-large">{deltaArrow}</div>
              <div className="delta-line"></div>
            </div>

            <div className="station-card">
              <div className="station-header">
                <span className="station-label">Station 2</span>
                <span className="station-name">{station2.name}</span>
              </div>
              <div className="station-data">
                <div className="data-row">
                  <span className="data-label">Sea Level:</span>
                  <span className="data-value">{formatValue(station2.value)} m</span>
                </div>
                <div className="data-row">
                  <span className="data-label">Timestamp:</span>
                  <span className="data-value timestamp">{formatTimestamp(station2.timestamp)}</span>
                </div>
              </div>
            </div>
          </div>

          <div className={`delta-result-panel ${deltaColor}`}>
            <span className="delta-result-label">Calculated Delta:</span>
            <span className="delta-result-value">
              {delta >= 0 ? '+' : ''}{formatValue(delta)} m
            </span>
            <span className="delta-result-description">
              {deltaColor === 'positive' && 'Station 2 is higher'}
              {deltaColor === 'negative' && 'Station 1 is higher'}
              {deltaColor === 'neutral' && 'Levels are equal'}
            </span>
          </div>
        </Card.Body>
      </Card>
    );
  }

  // Default: overlay position
  return (
    <div className={`delta-overlay ${isMobile ? 'mobile' : ''}`}>
      <Card className="delta-overlay-card">
        <Card.Body>
          <div className="delta-overlay-header">
            <div className="delta-overlay-title">
              <span className="delta-icon">Δ</span>
              <span>Station Comparison</span>
            </div>
            <Button
              variant="link"
              size="sm"
              onClick={onClear}
              className="delta-close-btn"
              aria-label="Clear selection"
            >
              ✕
            </Button>
          </div>

          <div className="delta-overlay-body">
            <div className="station-info">
              <div className="station-label-small">Station 1</div>
              <div className="station-name-large">{station1.name}</div>
              <div className="station-value-large">{formatValue(station1.value)} m</div>
              <div className="station-timestamp-small">{formatTimestamp(station1.timestamp)}</div>
            </div>

            <div className={`delta-indicator ${deltaColor}`}>
              <div className="delta-arrow-icon">{deltaArrow}</div>
              <div className="delta-value-main">{formatValue(Math.abs(delta))}</div>
              <div className="delta-unit">meters</div>
            </div>

            <div className="station-info">
              <div className="station-label-small">Station 2</div>
              <div className="station-name-large">{station2.name}</div>
              <div className="station-value-large">{formatValue(station2.value)} m</div>
              <div className="station-timestamp-small">{formatTimestamp(station2.timestamp)}</div>
            </div>
          </div>

          <div className="delta-overlay-footer">
            <Button
              variant="outline-primary"
              size="sm"
              onClick={onClear}
              className="w-100"
            >
              Clear Selection
            </Button>
          </div>
        </Card.Body>
      </Card>
    </div>
  );
};

export default React.memo(DeltaDisplay);
