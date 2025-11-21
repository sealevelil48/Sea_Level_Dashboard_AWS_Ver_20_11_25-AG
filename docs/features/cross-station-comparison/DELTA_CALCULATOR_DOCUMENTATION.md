# Delta Calculator Documentation

## Overview

The Delta Calculator is a utility module for computing and formatting the difference between two selected data points in the Sea Level Dashboard. It handles multiple scenarios and provides comprehensive validation.

**File Location:** `frontend/src/utils/deltaCalculator.js`

**Test Location:** `frontend/src/__tests__/deltaCalculator.test.js`

---

## Core Functions

### 1. `calculateDelta(point1, point2)`

Main function that calculates the difference between two data points.

#### Parameters
- `point1` (Object): First data point with sea level value and timestamp
- `point2` (Object): Second data point with sea level value and timestamp

#### Return Value
Returns an object with the following structure:

```javascript
{
  success: boolean,           // true if calculation succeeded
  error?: string,            // error message if success is false
  point1: {
    value: number,           // Sea level in meters (3 decimal places)
    station: string,         // Station name
    timestamp: Date,         // Parsed date object
    formattedTime: string    // Human-readable time string
  },
  point2: { ... },          // Same as point1
  delta: {
    valueDelta: number,      // Absolute difference in meters
    isPoint1Higher: boolean, // True if point1 value > point2 value
    isPoint2Higher: boolean, // True if point2 value > point1 value
    isEqual: boolean,        // True if values are equal
    highestValue: number,    // Maximum of the two values
    lowestValue: number,     // Minimum of the two values
    percentageDifference: number // Percentage change relative to point1
  },
  scenario: {
    sameStation: boolean,    // True if both from same station
    sameTime: boolean,       // True if both from same timestamp (±1s)
    isDifferentStations: boolean,
    isDifferentTimes: boolean
  },
  timeDelta?: {              // Only if times differ
    days: number,
    hours: number,
    minutes: number,
    seconds: number,
    formattedString: string  // e.g., "1d 6h 30m"
  }
}
```

#### Example Usage

```javascript
import { calculateDelta } from '../utils/deltaCalculator';

// Define two data points
const point1 = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.235,
  Station: 'Yafo'
};

const point2 = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.215,
  Station: 'Ashdod'
};

// Calculate delta
const result = calculateDelta(point1, point2);

if (result.success) {
  console.log(`Difference: Δ${result.delta.valueDelta.toFixed(3)}m`);
  // Output: Difference: Δ0.020m
}
```

---

### 2. `validateDataPoint(point)`

Validates that a data point has all required fields and correct types.

#### Parameters
- `point` (Object): Data point to validate

#### Return Value
```javascript
{
  isValid: boolean,   // true if point is valid
  error?: string      // error message if validation failed
}
```

#### Example Usage

```javascript
import { validateDataPoint } from '../utils/deltaCalculator';

const point = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.235,
  Station: 'Yafo'
};

const validation = validateDataPoint(point);

if (!validation.isValid) {
  console.error(`Validation failed: ${validation.error}`);
}
```

---

### 3. `formatDeltaOutput(deltaResult)`

Formats the delta calculation result into a detailed, human-readable string.

#### Parameters
- `deltaResult` (Object): Result from `calculateDelta()`

#### Return Value
Multi-line formatted string with:
- Station information
- Timestamp or time range
- Sea level values
- Delta with interpretation
- Percentage change
- Time difference (if applicable)

#### Example Output

```
Stations: Yafo → Ashdod
Both measured at: 2024-11-20 12:00

Values:
  Yafo: 0.235m
  Ashdod: 0.215m

Delta: Δ0.020m (Yafo is higher)
Percentage Change: 8.51%
```

#### Example Usage

```javascript
import { calculateDelta, formatDeltaOutput } from '../utils/deltaCalculator';

const result = calculateDelta(point1, point2);
const output = formatDeltaOutput(result);

console.log(output);
```

---

### 4. `generateCompactDeltaString(deltaResult, options)`

Generates a concise one-line delta string for quick display in UI.

#### Parameters
- `deltaResult` (Object): Result from `calculateDelta()`
- `options` (Object, optional):
  - `includeStations` (boolean): Include station names (default: true)
  - `includeTime` (boolean): Include time info (default: true)

#### Return Value
Single-line string like: `"Yafo vs Ashdod: 0.235m → 0.215m (Δ0.020m) ↓"`

#### Example Usage

```javascript
const compact = generateCompactDeltaString(result);
// Output: "Yafo vs Ashdod: 0.235m → 0.215m (Δ0.020m) ↑"
```

---

### 5. `generateDeltaSummary(deltaResult)`

Generates a JSON-friendly summary object suitable for API responses.

#### Parameters
- `deltaResult` (Object): Result from `calculateDelta()`

#### Return Value
```javascript
{
  success: boolean,
  point1: {
    station: string,
    value: number,
    timestamp: string  // ISO format
  },
  point2: { ... },
  delta: number,
  difference_percent: number,
  higher_point: string,
  time_difference_minutes: number,
  same_station: boolean,
  same_time: boolean,
  error?: string  // If success is false
}
```

#### Example Usage

```javascript
const summary = generateDeltaSummary(result);
// Can be sent to API or stored in state
```

---

## Data Point Format

The calculator is flexible and supports multiple field naming conventions:

### Sea Level Value (one of):
- `Tab_Value_mDepthC1` (IMS standard)
- `level`
- `value`

### Timestamp (one of):
- `Tab_DateTime` (IMS standard)
- `timestamp`
- `date`

### Station Name (one of):
- `Station` (IMS standard)
- `station`
- `name`

**Recommended format:**
```javascript
{
  Tab_DateTime: "2024-11-20T12:00:00Z",
  Tab_Value_mDepthC1: 0.235,
  Station: "Yafo"
}
```

---

## Scenarios & Examples

### Scenario 1: Different Stations, Same Time

```javascript
const yafoPoint = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.235,
  Station: 'Yafo'
};

const ashdodPoint = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.215,
  Station: 'Ashdod'
};

const result = calculateDelta(yafoPoint, ashdodPoint);

// Output:
// {
//   success: true,
//   delta: {
//     valueDelta: 0.020,
//     isPoint1Higher: true,
//     percentageDifference: 8.51
//   },
//   scenario: {
//     sameStation: false,
//     sameTime: true,
//     isDifferentStations: true,
//     isDifferentTimes: false
//   }
// }
```

**Formatted Output:**
```
Stations: Yafo → Ashdod
Both measured at: 2024-11-20 12:00

Values:
  Yafo: 0.235m
  Ashdod: 0.215m

Delta: Δ0.020m (Yafo is higher)
Percentage Change: 8.51%
```

---

### Scenario 2: Same Station, Different Times (6.5 hours)

```javascript
const morningPoint = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.235,
  Station: 'Yafo'
};

const eveningPoint = {
  Tab_DateTime: '2024-11-20T18:30:00Z',
  Tab_Value_mDepthC1: 0.240,
  Station: 'Yafo'
};

const result = calculateDelta(morningPoint, eveningPoint);

// Output includes timeDelta:
// {
//   timeDelta: {
//     days: 0,
//     hours: 6,
//     minutes: 30,
//     seconds: 23400,
//     formattedString: "6h 30m"
//   }
// }
```

**Formatted Output:**
```
Station: Yafo
Time Range: 2024-11-20 12:00 to 2024-11-20 18:30

Values:
  Yafo: 0.235m
  Yafo: 0.240m

Delta: Δ0.005m (evening point is higher)
Percentage Change: 2.13%
Time Difference: 6h 30m
```

---

### Scenario 3: Same Station, 1 Day Apart

```javascript
const previousPoint = {
  Tab_DateTime: '2024-11-19T12:00:00Z',
  Tab_Value_mDepthC1: 0.200,
  Station: 'Yafo'
};

const currentPoint = {
  Tab_DateTime: '2024-11-20T12:00:00Z',
  Tab_Value_mDepthC1: 0.235,
  Station: 'Yafo'
};

const result = calculateDelta(previousPoint, currentPoint);

// Output:
// {
//   timeDelta: {
//     days: 1,
//     hours: 24,
//     minutes: 1440,
//     seconds: 86400,
//     formattedString: "1d"
//   },
//   delta: {
//     valueDelta: 0.035,
//     percentageDifference: 17.50
//   }
// }
```

---

### Scenario 4: Edge Cases

#### Equal Values
```javascript
const point1 = { Tab_DateTime: '2024-11-20T12:00:00Z', Tab_Value_mDepthC1: 0.235, Station: 'A' };
const point2 = { Tab_DateTime: '2024-11-20T12:00:00Z', Tab_Value_mDepthC1: 0.235, Station: 'B' };

const result = calculateDelta(point1, point2);
// result.delta.valueDelta === 0
// result.delta.isEqual === true
```

#### Negative Values
```javascript
const point1 = { Tab_DateTime: '2024-11-20T12:00:00Z', Tab_Value_mDepthC1: -0.050, Station: 'A' };
const point2 = { Tab_DateTime: '2024-11-20T12:00:00Z', Tab_Value_mDepthC1: -0.100, Station: 'B' };

const result = calculateDelta(point1, point2);
// result.delta.valueDelta === 0.050
// result.delta.isPoint1Higher === true (because -0.050 > -0.100)
```

#### Invalid Input
```javascript
const result = calculateDelta(null, point2);
// result.success === false
// result.error === "Point 1: Data point is null or undefined"
```

---

## Validation Rules

A valid data point must have:

1. **Sea Level Value**
   - Field must exist with one of the standard names
   - Value must be a number
   - Value must not be NaN

2. **Timestamp**
   - Field must exist with one of the standard names
   - Must be parseable as a valid date

3. **Station Name** (optional but recommended)
   - Used for labeling in output

**Validation errors include:**
- "Data point is null or undefined"
- "Data point must be an object"
- "Data point missing sea level value"
- "Sea level value must be a valid number"
- "Data point missing timestamp"
- "Invalid timestamp format"

---

## Number Formatting

All sea level values are formatted to **3 decimal places** to match the dashboard's existing precision:

- Input: `0.2351234`
- Output: `0.235`

This is consistent with the current dashboard formatting in:
- `TableView.js` (lines 40-41)
- `GraphView.js` (line 136, 156, etc.)

---

## Integration with React Components

### Example: Using in a Comparison Modal

```javascript
import React, { useState } from 'react';
import { calculateDelta, formatDeltaOutput } from '../utils/deltaCalculator';

const DeltaComparisonModal = ({ selectedPoints }) => {
  const [deltaResult, setDeltaResult] = useState(null);

  const handleCalculate = () => {
    if (selectedPoints.length !== 2) return;

    const result = calculateDelta(selectedPoints[0], selectedPoints[1]);
    setDeltaResult(result);
  };

  if (!deltaResult) {
    return <button onClick={handleCalculate}>Calculate Delta</button>;
  }

  if (!deltaResult.success) {
    return <div className="error">{deltaResult.error}</div>;
  }

  return (
    <div className="delta-comparison">
      <pre>{formatDeltaOutput(deltaResult)}</pre>
    </div>
  );
};

export default DeltaComparisonModal;
```

### Example: Using in GraphView for Point Selection

```javascript
// In GraphView.js

const [selectedPoints, setSelectedPoints] = useState([]);

const handlePointClick = (point) => {
  if (selectedPoints.length < 2) {
    setSelectedPoints([...selectedPoints, point]);
  }

  if (selectedPoints.length === 2) {
    const delta = calculateDelta(selectedPoints[0], point);
    if (delta.success) {
      console.log('Delta:', delta.delta.valueDelta);
    }
  }
};
```

---

## Testing

Unit tests are comprehensive and cover:

### Validation Tests
- Valid data points
- Null/undefined points
- Missing fields
- Invalid data types
- Invalid timestamps

### Calculation Tests
- Different stations (same time)
- Same station (different times)
- Large time differences (days)
- Equal values
- Negative values
- Very small differences
- High variations

### Formatting Tests
- Multi-line formatted output
- Compact string generation
- JSON summary generation

### Edge Cases
- Error handling
- Alternative field names
- Percentage calculation
- Time difference formatting

### Run Tests
```bash
npm test deltaCalculator.test.js
```

---

## Performance Considerations

1. **Validation**: O(1) - constant time
2. **Calculation**: O(1) - constant time
3. **Formatting**: O(1) - constant time

The module has no dependencies on external libraries beyond the existing `dateUtils.js`.

---

## Future Enhancements

Potential additions for future versions:

1. **Trend analysis**: Calculate if delta is increasing/decreasing over time
2. **Batch calculations**: Calculate deltas for multiple point pairs
3. **Caching**: Memoize results for frequently compared points
4. **Localization**: Support multiple date/time formats
5. **Statistical analysis**: Standard deviation, confidence intervals
6. **Anomaly detection**: Flag unusual deltas
7. **Rate calculations**: m/hour, m/day trends

---

## Related Files

- **Main Calculator**: `frontend/src/utils/deltaCalculator.js`
- **Unit Tests**: `frontend/src/__tests__/deltaCalculator.test.js`
- **Date Utils**: `frontend/src/utils/dateUtils.js`
- **Data Optimizer**: `frontend/src/utils/dataOptimizer.js`
- **Table View**: `frontend/src/components/TableView.js`
- **Graph View**: `frontend/src/components/GraphView.js`

---

## Changelog

### Version 1.0.0 (2024-11-20)
- Initial release
- Core delta calculation function
- Validation system
- Multiple output formatting options
- Comprehensive test suite
- Complete documentation

---

## Support

For issues or questions:
1. Check the test file for usage examples
2. Review the scenario documentation above
3. Verify data point format compliance
4. Check validation results for specific errors
