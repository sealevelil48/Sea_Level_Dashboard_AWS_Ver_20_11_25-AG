# Delta Calculator - Usage Examples

Complete working examples demonstrating all features and scenarios of the delta calculation module.

---

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Validation Examples](#validation-examples)
3. [Different Scenarios](#different-scenarios)
4. [Formatting Examples](#formatting-examples)
5. [React Integration](#react-integration)
6. [Error Handling](#error-handling)
7. [Advanced Examples](#advanced-examples)

---

## Basic Usage

### Example 1: Simple Two-Station Comparison

```javascript
import { calculateDelta } from '../utils/deltaCalculator';

// Data points from different stations, same time
const yafo = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.235,
  Station: 'Yafo'
};

const ashdod = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.215,
  Station: 'Ashdod'
};

// Calculate delta
const result = calculateDelta(yafo, ashdod);

// Access results
console.log(`Delta: ${result.delta.valueDelta}m`);
// Output: Delta: 0.02m

console.log(`${yafo.Station} is ${result.delta.isPoint1Higher ? 'higher' : 'lower'}`);
// Output: Yafo is higher

console.log(`Percentage change: ${result.delta.percentageDifference}%`);
// Output: Percentage change: 8.51%
```

---

## Validation Examples

### Example 2: Validate Before Calculation

```javascript
import { validateDataPoint, calculateDelta } from '../utils/deltaCalculator';

const point1 = { /* data */ };
const point2 = { /* data */ };

// Always validate first for better error handling
const validation1 = validateDataPoint(point1);
const validation2 = validateDataPoint(point2);

if (!validation1.isValid) {
  console.error(`Point 1 error: ${validation1.error}`);
  return;
}

if (!validation2.isValid) {
  console.error(`Point 2 error: ${validation2.error}`);
  return;
}

// Safe to calculate
const result = calculateDelta(point1, point2);
```

### Example 3: Handle Various Field Names

```javascript
// IMS Standard Format
const imsPoint = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.235,
  Station: 'Yafo'
};

// Alternative Format 1
const alt1 = {
  timestamp: '2024-11-20T12:00:00Z',
  level: 0.235,
  station: 'Yafo'
};

// Alternative Format 2
const alt2 = {
  date: '2024-11-20T12:00:00Z',
  value: 0.235,
  name: 'Yafo'
};

// All formats work!
const result1 = calculateDelta(imsPoint, alt1);
const result2 = calculateDelta(alt1, alt2);

console.log(result1.success); // true
console.log(result2.success); // true
```

---

## Different Scenarios

### Example 4: Different Stations, Same Time

**Scenario:** Compare sea levels at two coastal cities at the same moment

```javascript
import { calculateDelta, formatDeltaOutput } from '../utils/deltaCalculator';

const gibraltarPoint = {
  Tab_DateTime: '2024-11-20T14:30:00Z',
  Tab_Value_mDepthC1: 0.450,
  Station: 'Gibraltar'
};

const casablancaPoint = {
  Tab_DateTime: '2024-11-20T14:30:00Z',
  Tab_Value_mDepthC1: 0.380,
  Station: 'Casablanca'
};

const result = calculateDelta(gibraltarPoint, casablancaPoint);

console.log(formatDeltaOutput(result));

/* Output:
Stations: Gibraltar → Casablanca
Both measured at: 2024-11-20 14:30

Values:
  Gibraltar: 0.450m
  Casablanca: 0.380m

Delta: Δ0.070m (Gibraltar is higher)
Percentage Change: 15.56%
*/
```

### Example 5: Same Station, Different Times (6 Hours Apart)

**Scenario:** Track how sea level changes over a workday

```javascript
const morningReading = {
  Tab_DateTime: '2024-11-20T08:00:00Z',
  Tab_Value_mDepthC1: 0.185,
  Station: 'Ashdod'
};

const afternoonReading = {
  Tab_DateTime: '2024-11-20T14:00:00Z',
  Tab_Value_mDepthC1: 0.220,
  Station: 'Ashdod'
};

const result = calculateDelta(morningReading, afternoonReading);

// Check results
if (result.success) {
  console.log(`Change over 6 hours: Δ${result.delta.valueDelta.toFixed(3)}m`);
  // Output: Change over 6 hours: Δ0.035m

  console.log(`Time difference: ${result.timeDelta.formattedString}`);
  // Output: Time difference: 6h

  console.log(`Same station: ${result.scenario.sameStation}`);
  // Output: Same station: true

  console.log(`Different times: ${result.scenario.isDifferentTimes}`);
  // Output: Different times: true
}
```

### Example 6: Same Station, Different Days (24 Hours)

**Scenario:** Compare sea levels one day apart to detect trends

```javascript
const yesterdayNoon = {
  Tab_DateTime: '2024-11-19T12:00:00Z',
  Tab_Value_mDepthC1: 0.215,
  Station: 'Yafo'
};

const todayNoon = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.235,
  Station: 'Yafo'
};

const result = calculateDelta(yesterdayNoon, todayNoon);

// Analyze the change
const change24h = result.delta.valueDelta;
const trend = result.delta.isPoint1Higher ? 'Rising' : 'Falling';

console.log(`24-hour trend: ${trend} by Δ${change24h.toFixed(3)}m`);
// Output: 24-hour trend: Rising by Δ0.020m

console.log(`Daily rate: ${(change24h * 100).toFixed(2)}cm/day`);
// Output: Daily rate: 2.00cm/day
```

### Example 7: Same Station, 1 Week Apart

**Scenario:** Long-term sea level trend analysis

```javascript
const oneWeekAgo = {
  Tab_DateTime: '2024-11-13T12:00:00Z',
  Tab_Value_mDepthC1: 0.180,
  Station: 'Yafo'
};

const today = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.235,
  Station: 'Yafo'
};

const result = calculateDelta(oneWeekAgo, today);

if (result.success) {
  const weeklyChange = result.delta.valueDelta;
  const dailyRate = weeklyChange / result.timeDelta.days;

  console.log(`Weekly change: Δ${weeklyChange.toFixed(3)}m`);
  // Output: Weekly change: Δ0.055m

  console.log(`Daily rate: ${(dailyRate * 100).toFixed(2)}cm/day`);
  // Output: Daily rate: 7.86cm/day

  console.log(`Time span: ${result.timeDelta.formattedString}`);
  // Output: Time span: 7d
}
```

---

## Formatting Examples

### Example 8: Generate Formatted Output

```javascript
import { calculateDelta, formatDeltaOutput } from '../utils/deltaCalculator';

const point1 = {
  Tab_DateTime: '2024-11-20T08:30:00Z',
  Tab_Value_mDepthC1: 0.200,
  Station: 'Station A'
};

const point2 = {
  Tab_DateTime: '2024-11-20T20:45:00Z',
  Tab_Value_mDepthC1: 0.245,
  Station: 'Station A'
};

const result = calculateDelta(point1, point2);
const output = formatDeltaOutput(result);

console.log(output);

/* Full Output:
Station: Station A
Time Range: 2024-11-20 08:30 to 2024-11-20 20:45

Values:
  Station A: 0.200m
  Station A: 0.245m

Delta: Δ0.045m (evening point is higher)
Percentage Change: 22.50%
Time Difference: 12h 15m
*/
```

### Example 9: Generate Compact String

```javascript
import { calculateDelta, generateCompactDeltaString } from '../utils/deltaCalculator';

const result = calculateDelta(point1, point2);

// Default - includes stations and time
const compact = generateCompactDeltaString(result);
console.log(compact);
// Output: Yafo vs Ashdod: 0.235m → 0.215m (Δ0.020m) ↑

// Without stations
const compactNoStations = generateCompactDeltaString(result, { includeStations: false });
console.log(compactNoStations);
// Output: 0.235m → 0.215m (Δ0.020m) ↑

// Without time info
const compactNoTime = generateCompactDeltaString(result, { includeTime: false });
console.log(compactNoTime);
// Output: Yafo vs Ashdod: 0.235m → 0.215m (Δ0.020m) ↑
```

### Example 10: Generate JSON Summary

```javascript
import { calculateDelta, generateDeltaSummary } from '../utils/deltaCalculator';

const result = calculateDelta(point1, point2);
const summary = generateDeltaSummary(result);

// Perfect for sending to API or storing in database
console.log(JSON.stringify(summary, null, 2));

/* Output:
{
  "success": true,
  "point1": {
    "station": "Yafo",
    "value": 0.235,
    "timestamp": "2024-11-20T12:00:00.000Z"
  },
  "point2": {
    "station": "Ashdod",
    "value": 0.215,
    "timestamp": "2024-11-20T12:00:00.000Z"
  },
  "delta": 0.02,
  "difference_percent": 8.51,
  "higher_point": "Yafo",
  "time_difference_minutes": 0,
  "same_station": false,
  "same_time": true
}
*/
```

---

## React Integration

### Example 11: Using in a React Component

```javascript
import React, { useState } from 'react';
import { calculateDelta } from '../utils/deltaCalculator';
import DeltaComparison from './DeltaComparison';

const DataComparisonPanel = ({ data }) => {
  const [selectedPoints, setSelectedPoints] = useState([]);

  const handlePointClick = (point) => {
    if (selectedPoints.length < 2) {
      setSelectedPoints([...selectedPoints, point]);
    } else {
      // Reset and select new point
      setSelectedPoints([point]);
    }
  };

  const handleClear = () => {
    setSelectedPoints([]);
  };

  return (
    <div className="comparison-panel">
      <div className="data-table">
        {data.map((point, idx) => (
          <div
            key={idx}
            className="data-row"
            onClick={() => handlePointClick(point)}
            style={{
              backgroundColor: selectedPoints.includes(point) ? '#4CAF50' : 'transparent'
            }}
          >
            <span>{point.Station} - {point.Tab_DateTime}</span>
            <span>{point.Tab_Value_mDepthC1.toFixed(3)}m</span>
          </div>
        ))}
      </div>

      {selectedPoints.length === 2 && (
        <DeltaComparison
          point1={selectedPoints[0]}
          point2={selectedPoints[1]}
          onClear={handleClear}
        />
      )}
    </div>
  );
};

export default DataComparisonPanel;
```

### Example 12: Using with GraphView Point Clicking

```javascript
// In GraphView.js or similar component

import { calculateDelta } from '../utils/deltaCalculator';

const [selectedPoints, setSelectedPoints] = useState([]);

const handlePlotClick = (data) => {
  const clickedPoint = {
    Tab_DateTime: data.points[0].x,
    Tab_Value_mDepthC1: data.points[0].y,
    Station: filters.station
  };

  if (selectedPoints.length < 2) {
    setSelectedPoints([...selectedPoints, clickedPoint]);
  }

  if (selectedPoints.length === 2) {
    const delta = calculateDelta(selectedPoints[0], clickedPoint);

    if (delta.success) {
      // Show delta in a modal or notification
      showNotification({
        title: 'Delta Calculated',
        message: `Δ${delta.delta.valueDelta.toFixed(3)}m (${delta.delta.percentageDifference}%)`
      });
    }
  }
};

return (
  <Plot
    data={graphData}
    layout={layout}
    config={config}
    onClick={handlePlotClick}
  />
);
```

---

## Error Handling

### Example 13: Comprehensive Error Handling

```javascript
import { calculateDelta, validateDataPoint } from '../utils/deltaCalculator';

function safeCalculateDelta(point1, point2) {
  try {
    // Step 1: Validate points
    const validation1 = validateDataPoint(point1);
    if (!validation1.isValid) {
      return {
        success: false,
        error: `Point 1: ${validation1.error}`,
        data: null
      };
    }

    const validation2 = validateDataPoint(point2);
    if (!validation2.isValid) {
      return {
        success: false,
        error: `Point 2: ${validation2.error}`,
        data: null
      };
    }

    // Step 2: Calculate delta
    const result = calculateDelta(point1, point2);

    if (!result.success) {
      return {
        success: false,
        error: result.error,
        data: null
      };
    }

    // Step 3: Return success with data
    return {
      success: true,
      error: null,
      data: result
    };

  } catch (error) {
    return {
      success: false,
      error: `Unexpected error: ${error.message}`,
      data: null
    };
  }
}

// Usage
const result = safeCalculateDelta(point1, point2);

if (result.success) {
  console.log(`Delta: ${result.data.delta.valueDelta}m`);
} else {
  console.error(result.error);
  // Handle error - show user message, log, etc.
}
```

### Example 14: Handle Various Data Formats

```javascript
import { validateDataPoint, calculateDelta } from '../utils/deltaCalculator';

function calculateDeltaFlexible(point1, point2) {
  // Try to validate with current format
  let val1 = validateDataPoint(point1);
  let val2 = validateDataPoint(point2);

  if (!val1.isValid) {
    // Try to fix common issues
    if (point1 && point1.Tab_Value_mDepthC1 === undefined) {
      point1 = {
        ...point1,
        Tab_Value_mDepthC1: point1.level || point1.value || point1.seaLevel
      };
    }
    if (!point1.Tab_DateTime && point1.timestamp) {
      point1 = { ...point1, Tab_DateTime: point1.timestamp };
    }
    val1 = validateDataPoint(point1);
  }

  if (!val2.isValid) {
    if (point2 && point2.Tab_Value_mDepthC1 === undefined) {
      point2 = {
        ...point2,
        Tab_Value_mDepthC1: point2.level || point2.value || point2.seaLevel
      };
    }
    if (!point2.Tab_DateTime && point2.timestamp) {
      point2 = { ...point2, Tab_DateTime: point2.timestamp };
    }
    val2 = validateDataPoint(point2);
  }

  // Now calculate if both valid
  if (val1.isValid && val2.isValid) {
    return calculateDelta(point1, point2);
  }

  return {
    success: false,
    error: `Validation failed: Point1=${!val1.isValid}, Point2=${!val2.isValid}`
  };
}
```

---

## Advanced Examples

### Example 15: Batch Delta Calculations

```javascript
import { calculateDelta } from '../utils/deltaCalculator';

// Calculate deltas between reference point and multiple other points
function calculateMultipleDeltasFromReference(referencePoint, otherPoints) {
  return otherPoints.map((point, index) => {
    const result = calculateDelta(referencePoint, point);

    if (!result.success) {
      return { index, error: result.error };
    }

    return {
      index,
      station: point.Station,
      delta: result.delta.valueDelta,
      percentage: result.delta.percentageDifference,
      isHigher: result.delta.isPoint1Higher,
      timestamp: result.point2.formattedTime
    };
  });
}

// Usage
const reference = { /* Yafo noon */ };
const otherStations = [ /* Ashdod, Tel Aviv, Eilat */ ];

const results = calculateMultipleDeltasFromReference(reference, otherStations);

results.forEach(r => {
  if (r.error) {
    console.error(`Station ${r.index}: ${r.error}`);
  } else {
    console.log(`${r.station}: Δ${r.delta.toFixed(3)}m (${r.percentage}%)`);
  }
});
```

### Example 16: Track Trends Over Multiple Time Points

```javascript
import { calculateDelta } from '../utils/deltaCalculator';

function analyzeSeaLevelTrend(dataPoints) {
  if (dataPoints.length < 2) {
    return null;
  }

  const deltas = [];

  // Calculate deltas between consecutive points
  for (let i = 0; i < dataPoints.length - 1; i++) {
    const result = calculateDelta(dataPoints[i], dataPoints[i + 1]);

    if (result.success) {
      deltas.push({
        timeFrom: result.point1.formattedTime,
        timeTo: result.point2.formattedTime,
        delta: result.delta.valueDelta,
        duration: result.timeDelta?.formattedString || 'N/A',
        ratePerHour: result.timeDelta
          ? (result.delta.valueDelta / (result.timeDelta.hours + result.timeDelta.minutes / 60)).toFixed(4)
          : 'N/A'
      });
    }
  }

  // Calculate statistics
  const allDeltas = deltas.map(d => d.delta);
  const avgDelta = allDeltas.reduce((a, b) => a + b, 0) / allDeltas.length;
  const maxDelta = Math.max(...allDeltas);
  const minDelta = Math.min(...allDeltas);

  return {
    pointsAnalyzed: dataPoints.length,
    deltasCalculated: deltas.length,
    individualDeltas: deltas,
    statistics: {
      averageDelta: avgDelta.toFixed(3),
      maxDelta: maxDelta.toFixed(3),
      minDelta: minDelta.toFixed(3),
      trend: avgDelta > 0 ? 'Rising' : avgDelta < 0 ? 'Falling' : 'Stable'
    }
  };
}

// Usage
const result = analyzeSeaLevelTrend(hourlyDataPoints);
console.log(`Trend: ${result.statistics.trend}`);
console.log(`Average change: Δ${result.statistics.averageDelta}m per interval`);
```

### Example 17: Find Maximum/Minimum Variations

```javascript
import { calculateDelta } from '../utils/deltaCalculator';

function findExtremeVariations(dataPoints) {
  const variations = [];

  // Compare all pairs
  for (let i = 0; i < dataPoints.length; i++) {
    for (let j = i + 1; j < dataPoints.length; j++) {
      const result = calculateDelta(dataPoints[i], dataPoints[j]);

      if (result.success) {
        variations.push({
          point1: result.point1.station,
          point2: result.point2.station,
          delta: result.delta.valueDelta,
          percentage: result.delta.percentageDifference,
          time1: result.point1.formattedTime,
          time2: result.point2.formattedTime
        });
      }
    }
  }

  // Sort to find extremes
  variations.sort((a, b) => b.delta - a.delta);

  return {
    maximum: variations[0],
    minimum: variations[variations.length - 1],
    median: variations[Math.floor(variations.length / 2)],
    allVariations: variations
  };
}

// Usage
const extremes = findExtremeVariations(allDataPoints);
console.log(`Maximum variation: ${extremes.maximum.delta}m between ${extremes.maximum.point1} and ${extremes.maximum.point2}`);
```

---

## Production Checklist

Before integrating delta calculator into production:

- [ ] All test cases pass: `npm test deltaCalculator.test.js`
- [ ] Validate data format matches expected structure
- [ ] Handle null/undefined points gracefully
- [ ] Implement error boundaries in React components
- [ ] Add loading states for async calculations
- [ ] Log errors for monitoring/debugging
- [ ] Test with real historical data
- [ ] Verify number precision (3 decimal places)
- [ ] Test on mobile devices
- [ ] Performance test with large datasets

---

## Tips & Best Practices

1. **Always validate first**: Use `validateDataPoint()` before calculations
2. **Use try-catch**: Wrap calculations in error handlers
3. **Format before display**: Use `formatDeltaOutput()` for user-facing text
4. **Cache results**: For identical point pairs, cache the result
5. **Handle timezone**: Ensure timestamps are in UTC
6. **Document custom formats**: If using non-standard field names, document them
7. **Test edge cases**: Empty arrays, null values, extreme numbers
8. **Monitor performance**: Log calculation times for large datasets
9. **Use TypeScript**: Consider adding type definitions in the future
10. **Keep it simple**: Don't over-engineer; delta is just a difference

