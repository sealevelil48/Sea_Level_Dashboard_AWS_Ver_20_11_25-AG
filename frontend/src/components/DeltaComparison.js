/**
 * Delta Comparison Component
 * Displays delta calculation results between two selected data points
 * Can be integrated into GraphView for click-to-compare functionality
 */

import React, { useState, useEffect } from 'react';
import { Card, Badge, Button, Alert, Spinner } from 'react-bootstrap';
import {
  calculateDelta,
  formatDeltaOutput,
  generateCompactDeltaString,
  validateDataPoint
} from '../utils/deltaCalculator';
import './DeltaComparison.css';

const DeltaComparison = ({
  point1 = null,
  point2 = null,
  onClear = () => {},
  isLoading = false
}) => {
  const [deltaResult, setDeltaResult] = useState(null);
  const [error, setError] = useState(null);

  // Calculate delta whenever points change
  useEffect(() => {
    setDeltaResult(null);
    setError(null);

    if (!point1 || !point2) {
      return;
    }

    try {
      // Validate points first
      const validation1 = validateDataPoint(point1);
      const validation2 = validateDataPoint(point2);

      if (!validation1.isValid) {
        setError(`Point 1: ${validation1.error}`);
        return;
      }

      if (!validation2.isValid) {
        setError(`Point 2: ${validation2.error}`);
        return;
      }

      // Calculate delta
      const result = calculateDelta(point1, point2);

      if (!result.success) {
        setError(result.error);
        return;
      }

      setDeltaResult(result);
    } catch (err) {
      setError(`Unexpected error: ${err.message}`);
    }
  }, [point1, point2]);

  // Show placeholder if no points selected
  if (!point1 || !point2) {
    return (
      <Card className="delta-comparison-card delta-empty">
        <Card.Body className="text-center">
          <p className="text-muted mb-0">
            Select two data points to compare and calculate delta
          </p>
        </Card.Body>
      </Card>
    );
  }

  // Show loading state
  if (isLoading) {
    return (
      <Card className="delta-comparison-card">
        <Card.Body className="text-center">
          <Spinner animation="border" size="sm" className="mb-2" />
          <p className="text-muted mb-0">Calculating delta...</p>
        </Card.Body>
      </Card>
    );
  }

  // Show error if validation or calculation failed
  if (error) {
    return (
      <Card className="delta-comparison-card">
        <Card.Body>
          <Alert variant="danger" className="mb-0">
            <strong>Calculation Error:</strong> {error}
          </Alert>
          <Button
            variant="outline-secondary"
            size="sm"
            onClick={onClear}
            className="mt-3 w-100"
          >
            Clear Selection
          </Button>
        </Card.Body>
      </Card>
    );
  }

  // Show results
  if (deltaResult && deltaResult.success) {
    const { point1: p1, point2: p2, delta, scenario, timeDelta } = deltaResult;

    return (
      <Card className="delta-comparison-card delta-success">
        <Card.Header className="delta-header">
          <div className="d-flex justify-content-between align-items-center">
            <h6 className="mb-0">Delta Comparison</h6>
            <Button
              variant="outline-danger"
              size="sm"
              onClick={onClear}
              className="btn-close-custom"
            >
              ✕
            </Button>
          </div>
        </Card.Header>

        <Card.Body className="delta-body">
          {/* Compact Summary */}
          <div className="delta-compact">
            <code className="delta-compact-text">
              {generateCompactDeltaString(deltaResult)}
            </code>
          </div>

          {/* Points Details */}
          <div className="row mt-3 mb-3">
            <div className="col-6">
              <div className="delta-point">
                <div className="delta-label">Point 1</div>
                <div className="delta-station">{p1.station}</div>
                <div className="delta-value">{p1.value.toFixed(3)}m</div>
                <div className="delta-time-small">{p1.formattedTime}</div>
              </div>
            </div>
            <div className="col-6">
              <div className="delta-point">
                <div className="delta-label">Point 2</div>
                <div className="delta-station">{p2.station}</div>
                <div className="delta-value">{p2.value.toFixed(3)}m</div>
                <div className="delta-time-small">{p2.formattedTime}</div>
              </div>
            </div>
          </div>

          {/* Delta Value - Big Display */}
          <div className="delta-main-value">
            <div className="delta-arrow">
              {delta.isEqual ? '=' : delta.isPoint1Higher ? '↑' : '↓'}
            </div>
            <div className="delta-number">Δ{delta.valueDelta.toFixed(3)}m</div>
            <div className="delta-percentage">{delta.percentageDifference}%</div>
          </div>

          {/* Scenario Badges */}
          <div className="delta-badges mt-3 mb-3">
            {scenario.sameStation ? (
              <Badge bg="info">Same Station</Badge>
            ) : (
              <Badge bg="primary">Different Stations</Badge>
            )}

            {scenario.sameTime ? (
              <Badge bg="info">Same Time</Badge>
            ) : (
              <Badge bg="warning">Different Times</Badge>
            )}
          </div>

          {/* Time Difference (if applicable) */}
          {timeDelta && (
            <div className="delta-time-info">
              <small className="text-muted">
                <strong>Time Span:</strong> {timeDelta.formattedString}
              </small>
            </div>
          )}

          {/* Detailed Statistics */}
          <div className="delta-stats mt-3">
            <div className="stat-row">
              <span className="stat-label">Highest Level:</span>
              <span className="stat-value">{delta.highestValue.toFixed(3)}m</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Lowest Level:</span>
              <span className="stat-value">{delta.lowestValue.toFixed(3)}m</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Higher Point:</span>
              <span className="stat-value">
                {delta.isPoint1Higher ? p1.station : p2.station}
              </span>
            </div>
          </div>

          {/* Full Formatted Output */}
          <details className="delta-details mt-3">
            <summary className="delta-details-summary">
              View Full Details
            </summary>
            <pre className="delta-formatted-output">
              {formatDeltaOutput(deltaResult)}
            </pre>
          </details>
        </Card.Body>

        <Card.Footer className="delta-footer">
          <small className="text-muted">
            Comparison complete | Points validated
          </small>
        </Card.Footer>
      </Card>
    );
  }

  return null;
};

export default DeltaComparison;
