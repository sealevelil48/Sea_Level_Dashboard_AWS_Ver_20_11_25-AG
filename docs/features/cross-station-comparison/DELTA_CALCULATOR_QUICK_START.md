# Delta Calculator - Quick Start Guide

Fast reference for using the delta calculation module in the Sea Level Dashboard.

---

## Installation

The delta calculator is already included in the project:

- **Utility**: `frontend/src/utils/deltaCalculator.js`
- **React Component**: `frontend/src/components/DeltaComparison.js`
- **Tests**: `frontend/src/__tests__/deltaCalculator.test.js`

---

## 30-Second Start

```javascript
import { calculateDelta } from '../utils/deltaCalculator';

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

const result = calculateDelta(point1, point2);

if (result.success) {
  console.log(`Δ${result.delta.valueDelta.toFixed(3)}m`);
}
```

---

## Core Functions

| Function | Purpose | Returns |
|----------|---------|---------|
| `calculateDelta(p1, p2)` | Calculate difference between points | Result object with delta |
| `validateDataPoint(point)` | Check if point is valid | `{isValid, error?}` |
| `formatDeltaOutput(result)` | Human-readable multi-line | String |
| `generateCompactDeltaString(result)` | One-line summary | String |
| `generateDeltaSummary(result)` | JSON-friendly structure | Object |

---

## Data Point Format

Minimal required format:

```javascript
{
  Tab_DateTime: "ISO date string",
  Tab_Value_mDepthC1: number,
  Station: "Station name"
}
```

Alternative field names are supported:
- Value: `Tab_Value_mDepthC1`, `level`, `value`
- Time: `Tab_DateTime`, `timestamp`, `date`
- Station: `Station`, `station`, `name`

---

## Quick Examples

### Example 1: Compare Two Stations

```javascript
const result = calculateDelta(yafo, ashdod);
console.log(`${result.delta.valueDelta.toFixed(3)}m difference`);
```

### Example 2: Check If Higher/Lower

```javascript
if (result.delta.isPoint1Higher) {
  console.log('Point 1 is higher');
} else if (result.delta.isPoint2Higher) {
  console.log('Point 2 is higher');
} else {
  console.log('Equal levels');
}
```

### Example 3: Time-Based Comparison

```javascript
if (result.scenario.isDifferentTimes) {
  console.log(`Time difference: ${result.timeDelta.formattedString}`);
}
```

### Example 4: Percentage Change

```javascript
const percent = result.delta.percentageDifference;
console.log(`${percent}% change`);
```

### Example 5: React Component

```javascript
import DeltaComparison from '../components/DeltaComparison';

<DeltaComparison
  point1={selectedPoint1}
  point2={selectedPoint2}
  onClear={handleClear}
/>
```

---

## Result Object Structure

```javascript
{
  success: true,
  point1: {
    value: 0.235,
    station: "Yafo",
    timestamp: Date,
    formattedTime: "2024-11-20 12:00"
  },
  point2: { /* similar */ },
  delta: {
    valueDelta: 0.020,        // Absolute difference
    isPoint1Higher: true,
    isPoint2Higher: false,
    isEqual: false,
    highestValue: 0.235,
    lowestValue: 0.215,
    percentageDifference: 8.51
  },
  scenario: {
    sameStation: false,
    sameTime: true,
    isDifferentStations: true,
    isDifferentTimes: false
  },
  timeDelta: {                // Only if different times
    days: 0,
    hours: 0,
    minutes: 0,
    seconds: 0,
    formattedString: "6h 30m"
  }
}
```

---

## Common Scenarios

### Different Stations, Same Time
```javascript
const result = calculateDelta(yafo, ashdod);
// result.scenario.sameStation === false
// result.scenario.sameTime === true
```

### Same Station, Different Times
```javascript
const result = calculateDelta(morning, evening);
// result.scenario.sameStation === true
// result.scenario.isDifferentTimes === true
// result.timeDelta available
```

### Same Station, Same Time
```javascript
const result = calculateDelta(point, point);
// result.delta.valueDelta === 0
// result.delta.isEqual === true
```

---

## Output Formatting

### Full Formatted Output
```javascript
const output = formatDeltaOutput(result);
console.log(output);
// Multi-line detailed string
```

### Compact String
```javascript
const compact = generateCompactDeltaString(result);
// "Yafo vs Ashdod: 0.235m → 0.215m (Δ0.020m) ↑"
```

### JSON Summary
```javascript
const summary = generateDeltaSummary(result);
// {success, point1, point2, delta, ...}
```

---

## Error Handling

### Check Success
```javascript
const result = calculateDelta(p1, p2);

if (!result.success) {
  console.error(result.error);
}
```

### Validate Before Calculating
```javascript
import { validateDataPoint } from '../utils/deltaCalculator';

const val = validateDataPoint(point);
if (!val.isValid) {
  console.error(val.error);
}
```

---

## Validation Errors

| Error | Meaning | Fix |
|-------|---------|-----|
| "null or undefined" | Point is null | Check input before calling |
| "must be an object" | Point isn't an object | Convert to object |
| "missing sea level value" | No value field | Add `Tab_Value_mDepthC1` |
| "valid number" | Value is NaN | Ensure value is numeric |
| "missing timestamp" | No date field | Add `Tab_DateTime` |
| "Invalid timestamp format" | Bad date format | Use ISO format |

---

## Number Formatting

All values are formatted to **3 decimal places**:

```javascript
result.delta.valueDelta  // Already rounded to 3 places
result.point1.value      // Already rounded to 3 places

// If you need to format yourself:
value.toFixed(3)
```

---

## Testing

Run tests:
```bash
npm test deltaCalculator.test.js
```

Test coverage includes:
- Validation
- Different scenarios
- Edge cases (null, equal values, negatives)
- Formatting
- Alternative field names

---

## Performance

All functions are O(1) - constant time:
- Validation: Fast
- Calculation: Fast
- Formatting: Fast

Safe to use in React renders and tight loops.

---

## Integration Checklist

When adding to your code:

- [ ] Import the function: `import { calculateDelta } from '../utils/deltaCalculator';`
- [ ] Validate points using `validateDataPoint()`
- [ ] Handle the result object properly
- [ ] Check `result.success` before using data
- [ ] Format output with appropriate function
- [ ] Test with sample data
- [ ] Add error handling
- [ ] Consider caching for performance

---

## Common Patterns

### Pattern 1: Simple Calculation
```javascript
const delta = calculateDelta(p1, p2);
if (delta.success) {
  // Use delta.delta.valueDelta
}
```

### Pattern 2: With Validation
```javascript
const val1 = validateDataPoint(p1);
const val2 = validateDataPoint(p2);
if (val1.isValid && val2.isValid) {
  const delta = calculateDelta(p1, p2);
}
```

### Pattern 3: With Error Display
```javascript
const delta = calculateDelta(p1, p2);
if (!delta.success) {
  setErrorMessage(delta.error);
} else {
  setDeltaResult(delta);
}
```

### Pattern 4: React Hook
```javascript
const [result, setResult] = useState(null);

useEffect(() => {
  if (point1 && point2) {
    setResult(calculateDelta(point1, point2));
  }
}, [point1, point2]);
```

---

## Tips

1. Always check `result.success` first
2. Use `validateDataPoint()` for debugging
3. `timeDelta` is only present if times differ
4. Percentage is relative to point1
5. Values are always absolute (positive)
6. Numbers already formatted to 3 decimals
7. All timestamps are Date objects in results
8. Station names can be any string
9. Works with any time units (hours, days, years)
10. Safe for production use

---

## Next Steps

1. Read full documentation: `DELTA_CALCULATOR_DOCUMENTATION.md`
2. See examples: `DELTA_CALCULATOR_EXAMPLES.md`
3. Review tests: `frontend/src/__tests__/deltaCalculator.test.js`
4. Check React component: `frontend/src/components/DeltaComparison.js`
5. Run tests: `npm test`

---

## Support

For issues:
1. Check the validation error message
2. Verify data point format
3. Review examples for similar use case
4. Check test file for working examples
5. Look at React component implementation

---

**Version:** 1.0.0
**Last Updated:** 2024-11-20
**Status:** Production Ready
