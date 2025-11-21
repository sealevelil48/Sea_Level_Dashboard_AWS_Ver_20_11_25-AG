/**
 * Unit Tests for Delta Calculator
 * Tests all scenarios: different stations, same stations, validation, edge cases
 */

import {
  calculateDelta,
  validateDataPoint,
  formatDeltaOutput,
  generateCompactDeltaString,
  generateDeltaSummary
} from '../utils/deltaCalculator';

// Mock data points for testing
const mockDataPoints = {
  yafo: {
    Tab_DateTime: '2024-11-20T12:00:00Z',
    Tab_Value_mDepthC1: 0.235,
    Station: 'Yafo'
  },
  ashdod: {
    Tab_DateTime: '2024-11-20T12:00:00Z',
    Tab_Value_mDepthC1: 0.215,
    Station: 'Ashdod'
  },
  yafoLater: {
    Tab_DateTime: '2024-11-20T18:30:00Z',
    Tab_Value_mDepthC1: 0.240,
    Station: 'Yafo'
  },
  yafoPrevious: {
    Tab_DateTime: '2024-11-19T12:00:00Z',
    Tab_Value_mDepthC1: 0.200,
    Station: 'Yafo'
  },
  null: null,
  invalid: {
    Station: 'Invalid'
  }
};

describe('Delta Calculator - Validation', () => {
  test('should validate correct data point', () => {
    const result = validateDataPoint(mockDataPoints.yafo);
    expect(result.isValid).toBe(true);
  });

  test('should reject null data point', () => {
    const result = validateDataPoint(null);
    expect(result.isValid).toBe(false);
    expect(result.error).toContain('null');
  });

  test('should reject data point without value', () => {
    const result = validateDataPoint(mockDataPoints.invalid);
    expect(result.isValid).toBe(false);
    expect(result.error).toContain('value');
  });

  test('should reject data point with non-numeric value', () => {
    const invalidPoint = {
      Tab_Value_mDepthC1: 'not-a-number',
      Tab_DateTime: '2024-11-20T12:00:00Z',
      Station: 'Test'
    };
    const result = validateDataPoint(invalidPoint);
    expect(result.isValid).toBe(false);
    expect(result.error).toContain('valid number');
  });

  test('should reject data point without timestamp', () => {
    const invalidPoint = {
      Tab_Value_mDepthC1: 0.235,
      Station: 'Test'
    };
    const result = validateDataPoint(invalidPoint);
    expect(result.isValid).toBe(false);
    expect(result.error).toContain('timestamp');
  });

  test('should reject data point with invalid timestamp format', () => {
    const invalidPoint = {
      Tab_Value_mDepthC1: 0.235,
      Tab_DateTime: 'not-a-date',
      Station: 'Test'
    };
    const result = validateDataPoint(invalidPoint);
    expect(result.isValid).toBe(false);
    expect(result.error).toContain('timestamp');
  });
});

describe('Delta Calculator - Different Stations (Same Time)', () => {
  test('should calculate delta between Yafo and Ashdod', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.ashdod);

    expect(result.success).toBe(true);
    expect(result.delta.valueDelta).toBe(0.020);
    expect(result.delta.isPoint1Higher).toBe(true);
    expect(result.scenario.sameStation).toBe(false);
    expect(result.scenario.sameTime).toBe(true);
  });

  test('should correctly identify higher point', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.ashdod);

    expect(result.delta.highestValue).toBe(0.235);
    expect(result.delta.lowestValue).toBe(0.215);
  });

  test('should calculate percentage difference', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.ashdod);

    // (0.020 / 0.235) * 100 ≈ 8.51%
    expect(result.delta.percentageDifference).toBeCloseTo(8.51, 1);
  });

  test('should handle reversed point order', () => {
    const result1 = calculateDelta(mockDataPoints.yafo, mockDataPoints.ashdod);
    const result2 = calculateDelta(mockDataPoints.ashdod, mockDataPoints.yafo);

    // Delta magnitude should be the same
    expect(result1.delta.valueDelta).toBe(result2.delta.valueDelta);

    // But higher/lower indicators should be reversed
    expect(result1.delta.isPoint1Higher).toBe(!result2.delta.isPoint1Higher);
  });

  test('should format output correctly for different stations', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.ashdod);
    const output = formatDeltaOutput(result);

    expect(output).toContain('Yafo');
    expect(output).toContain('Ashdod');
    expect(output).toContain('0.235m');
    expect(output).toContain('0.215m');
    expect(output).toContain('Δ0.020m');
  });
});

describe('Delta Calculator - Same Station (Different Times)', () => {
  test('should calculate delta for same station at different times', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.yafoLater);

    expect(result.success).toBe(true);
    expect(result.delta.valueDelta).toBe(0.005);
    expect(result.delta.isPoint1Higher).toBe(false); // 0.235 < 0.240
    expect(result.scenario.sameStation).toBe(true);
    expect(result.scenario.sameTime).toBe(false);
  });

  test('should calculate time difference correctly', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.yafoLater);

    expect(result.timeDelta).toBeDefined();
    expect(result.timeDelta.hours).toBe(6);
    expect(result.timeDelta.minutes).toBe(30);
    expect(result.timeDelta.formattedString).toContain('6h');
    expect(result.timeDelta.formattedString).toContain('30m');
  });

  test('should calculate large time delta (days)', () => {
    const result = calculateDelta(mockDataPoints.yafoPrevious, mockDataPoints.yafoLater);

    expect(result.timeDelta).toBeDefined();
    expect(result.timeDelta.days).toBe(1);
    expect(result.timeDelta.formattedString).toContain('1d');
  });

  test('should format output for same station different times', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.yafoLater);
    const output = formatDeltaOutput(result);

    expect(output).toContain('Station: Yafo');
    expect(output).toContain('Time Range');
    expect(output).toContain('12:00');
    expect(output).toContain('18:30');
  });
});

describe('Delta Calculator - Edge Cases', () => {
  test('should handle equal values correctly', () => {
    const point1 = {
      Tab_DateTime: '2024-11-20T12:00:00Z',
      Tab_Value_mDepthC1: 0.235,
      Station: 'Yafo'
    };
    const point2 = {
      Tab_DateTime: '2024-11-20T12:00:00Z',
      Tab_Value_mDepthC1: 0.235,
      Station: 'Ashdod'
    };

    const result = calculateDelta(point1, point2);

    expect(result.delta.valueDelta).toBe(0);
    expect(result.delta.isEqual).toBe(true);
    expect(result.delta.isPoint1Higher).toBe(false);
    expect(result.delta.isPoint2Higher).toBe(false);
  });

  test('should handle very small differences', () => {
    const point1 = {
      Tab_DateTime: '2024-11-20T12:00:00Z',
      Tab_Value_mDepthC1: 0.2351,
      Station: 'Station1'
    };
    const point2 = {
      Tab_DateTime: '2024-11-20T12:00:00Z',
      Tab_Value_mDepthC1: 0.2350,
      Station: 'Station2'
    };

    const result = calculateDelta(point1, point2);

    expect(result.delta.valueDelta).toBe(0.000); // Rounded to 3 decimals
  });

  test('should handle negative values', () => {
    const point1 = {
      Tab_DateTime: '2024-11-20T12:00:00Z',
      Tab_Value_mDepthC1: -0.050,
      Station: 'Station1'
    };
    const point2 = {
      Tab_DateTime: '2024-11-20T12:00:00Z',
      Tab_Value_mDepthC1: -0.100,
      Station: 'Station2'
    };

    const result = calculateDelta(point1, point2);

    expect(result.delta.valueDelta).toBe(0.050);
    expect(result.delta.isPoint1Higher).toBe(true); // -0.050 > -0.100
  });

  test('should return error for first point invalid', () => {
    const result = calculateDelta(null, mockDataPoints.yafo);

    expect(result.success).toBe(false);
    expect(result.error).toContain('Point 1');
  });

  test('should return error for second point invalid', () => {
    const result = calculateDelta(mockDataPoints.yafo, null);

    expect(result.success).toBe(false);
    expect(result.error).toContain('Point 2');
  });
});

describe('Delta Calculator - Alternative Field Names', () => {
  test('should handle alternative value field names', () => {
    const point1 = {
      timestamp: '2024-11-20T12:00:00Z',
      level: 0.235,
      station: 'Station1'
    };
    const point2 = {
      timestamp: '2024-11-20T12:00:00Z',
      value: 0.215,
      station: 'Station2'
    };

    const result = calculateDelta(point1, point2);

    expect(result.success).toBe(true);
    expect(result.delta.valueDelta).toBe(0.020);
  });

  test('should handle alternative station field names', () => {
    const point1 = {
      Tab_DateTime: '2024-11-20T12:00:00Z',
      Tab_Value_mDepthC1: 0.235,
      station: 'Station1'
    };
    const point2 = {
      Tab_DateTime: '2024-11-20T12:00:00Z',
      Tab_Value_mDepthC1: 0.215,
      name: 'Station2'
    };

    const result = calculateDelta(point1, point2);

    expect(result.success).toBe(true);
    expect(result.point1.station).toBe('Station1');
    expect(result.point2.station).toBe('Station2');
  });
});

describe('Delta Calculator - Formatting Functions', () => {
  test('should generate compact delta string', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.ashdod);
    const compact = generateCompactDeltaString(result);

    expect(compact).toContain('0.235m');
    expect(compact).toContain('0.215m');
    expect(compact).toContain('Δ0.020m');
    expect(compact).toContain('↑'); // Higher indicator
  });

  test('should generate summary for valid result', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.ashdod);
    const summary = generateDeltaSummary(result);

    expect(summary.success).toBe(true);
    expect(summary.point1.station).toBe('Yafo');
    expect(summary.point2.station).toBe('Ashdod');
    expect(summary.delta).toBe(0.020);
  });

  test('should handle formatting error results', () => {
    const result = calculateDelta(null, mockDataPoints.yafo);
    const output = formatDeltaOutput(result);

    expect(output).toContain('Error');
  });
});

describe('Delta Calculator - Real-world Scenarios', () => {
  test('Scenario 1: Different stations same time', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.ashdod);

    expect(result.success).toBe(true);
    expect(result.scenario.isDifferentStations).toBe(true);
    expect(result.scenario.isDifferentTimes).toBe(false);
    expect(result.delta.valueDelta).toBeCloseTo(0.020, 3);
  });

  test('Scenario 2: Same station, 6.5 hours apart', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.yafoLater);

    expect(result.success).toBe(true);
    expect(result.scenario.sameStation).toBe(true);
    expect(result.scenario.isDifferentTimes).toBe(true);
    expect(result.timeDelta.hours).toBe(6);
  });

  test('Scenario 3: Same station, 1 day apart', () => {
    const result = calculateDelta(mockDataPoints.yafoPrevious, mockDataPoints.yafoLater);

    expect(result.success).toBe(true);
    expect(result.scenario.sameStation).toBe(true);
    expect(result.timeDelta.days).toBe(1);
  });

  test('Scenario 4: High variation between stations', () => {
    const highPoint = {
      Tab_DateTime: '2024-11-20T12:00:00Z',
      Tab_Value_mDepthC1: 0.500,
      Station: 'HighStation'
    };
    const lowPoint = {
      Tab_DateTime: '2024-11-20T12:00:00Z',
      Tab_Value_mDepthC1: 0.100,
      Station: 'LowStation'
    };

    const result = calculateDelta(highPoint, lowPoint);

    expect(result.delta.valueDelta).toBe(0.400);
    expect(result.delta.percentageDifference).toBeCloseTo(80, 1);
  });
});

describe('Delta Calculator - JSON Summary', () => {
  test('should generate proper JSON structure', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.ashdod);
    const summary = generateDeltaSummary(result);

    // Verify structure
    expect(summary).toHaveProperty('success');
    expect(summary).toHaveProperty('point1');
    expect(summary).toHaveProperty('point2');
    expect(summary).toHaveProperty('delta');
    expect(summary).toHaveProperty('difference_percent');
    expect(summary).toHaveProperty('higher_point');
    expect(summary).toHaveProperty('same_station');
    expect(summary).toHaveProperty('same_time');
  });

  test('should handle ISO timestamp conversion', () => {
    const result = calculateDelta(mockDataPoints.yafo, mockDataPoints.ashdod);
    const summary = generateDeltaSummary(result);

    expect(summary.point1.timestamp).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    expect(summary.point2.timestamp).toMatch(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
  });
});
