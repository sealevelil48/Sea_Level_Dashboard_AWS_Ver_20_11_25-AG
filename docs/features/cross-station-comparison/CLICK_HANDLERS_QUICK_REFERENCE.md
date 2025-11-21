# Click Handlers Quick Reference Guide

## For Developers

### State Management

```javascript
// State structure
const [selectedPoints, setSelectedPoints] = useState([]);

// Point object structure
{
  x: '2025-01-15T12:00:00',        // Timestamp (string)
  y: 1.234,                         // Sea level (number)
  station: 'Haifa',                 // Station name (string)
  timestamp: '2025-01-15T12:00:00', // Same as x (string)
  pointIndex: 0,                    // Index in trace (number)
  traceIndex: 0,                    // Trace index (number)
  fullData: {...}                   // Full Plotly data object
}
```

### Event Handler

```javascript
// Add to Plot component
<Plot
  onClick={handlePlotClick}
  {...otherProps}
/>

// Handler implementation
const handlePlotClick = useCallback((event) => {
  // Validates and processes click events
  // Manages selection state (max 2 points)
  // Implements toggle behavior
}, [selectedPoints]);
```

### Visual Feedback

```javascript
// Add to traces array in createPlot
if (selectedPoints.length > 0) {
  traces.push({
    x: selectedPoints.map(p => p.x),
    y: selectedPoints.map(p => p.y),
    type: 'scattergl',
    mode: 'markers',
    name: 'Selected Points',
    marker: {
      color: '#FFD700',
      size: 16,
      symbol: 'star',
      line: { color: 'white', width: 2 }
    }
  });
}
```

### UI Panel

```javascript
// Conditional rendering
{selectedPoints.length > 0 && (
  <div>
    {/* Point info */}
    {selectedPoints.map((point, idx) => (...))}

    {/* Difference calculation (2 points) */}
    {selectedPoints.length === 2 && (
      <div>
        Level: {Math.abs(selectedPoints[1].y - selectedPoints[0].y).toFixed(3)}m
        Time: {Math.abs(new Date(selectedPoints[1].timestamp) -
                       new Date(selectedPoints[0].timestamp)) / (1000 * 60 * 60)} hours
      </div>
    )}

    {/* Clear button */}
    <Button onClick={handleClearSelection}>Clear Selection</Button>
  </div>
)}
```

## For Users

### How to Use

1. **Select First Point:**
   - Click on any point on the graph
   - A gold star will appear
   - Point details will be shown below the graph

2. **Select Second Point:**
   - Click on another point
   - Another gold star will appear
   - Difference calculation will be shown

3. **Deselect Point:**
   - Click on a selected point again
   - The gold star will disappear

4. **Clear All:**
   - Click the "Clear Selection" button
   - All selections will be removed

5. **Replace Point:**
   - When 2 points are selected, clicking a third point
   - Will replace the oldest selection

### What You Can See

- **Point Details:**
  - Station name
  - Timestamp (date and time)
  - Sea level value (in meters)

- **Comparison (2 points):**
  - Level difference (in meters)
  - Time difference (in hours)

### Tips

- Works on both desktop (click) and mobile (tap)
- Can select points from different stations
- Selection persists when changing views
- Zoom/pan still works normally
- Maximum 2 points can be selected

## Troubleshooting

### Point Won't Select
- **Issue:** Clicking doesn't select point
- **Solution:** Make sure you're clicking directly on a data point (line or marker)

### Selection Disappears
- **Issue:** Selected points disappear when changing filters
- **Solution:** This is by design - filter changes reload data and clear selection

### Can't See Gold Stars
- **Issue:** Selected points not visible
- **Solution:** Check legend - "Selected Points" trace should be visible

### Clear Button Missing
- **Issue:** Can't find Clear Selection button
- **Solution:** Button only appears when at least one point is selected

### Mobile Issues
- **Issue:** Touch not working
- **Solution:** Use single tap on data points, avoid dragging

## API Reference

### handlePlotClick(event)

**Parameters:**
- `event` (Object): Plotly click event object
  - `event.points` (Array): Array of clicked points
  - `event.points[0].x` (String): X-axis value
  - `event.points[0].y` (Number): Y-axis value
  - `event.points[0].data.name` (String): Trace name
  - `event.points[0].pointIndex` (Number): Point index
  - `event.points[0].curveNumber` (Number): Trace index

**Returns:** void

**Behavior:**
- Validates event data
- Adds/removes point from selection
- Enforces 2-point maximum
- Updates UI automatically

### handleClearSelection()

**Parameters:** None

**Returns:** void

**Behavior:**
- Clears all selected points
- Hides selection info panel
- Removes gold stars from graph

### selectedPoints

**Type:** Array<Object>

**Structure:**
```javascript
[
  {
    x: String,           // Timestamp
    y: Number,           // Sea level value
    station: String,     // Station name
    timestamp: String,   // ISO timestamp
    pointIndex: Number,  // Index in trace
    traceIndex: Number,  // Trace index
    fullData: Object     // Full Plotly data
  }
]
```

**Max Length:** 2

**Usage:**
```javascript
// Check if points are selected
if (selectedPoints.length > 0) {
  // Do something
}

// Get first selected point
const firstPoint = selectedPoints[0];

// Calculate difference
if (selectedPoints.length === 2) {
  const diff = Math.abs(selectedPoints[1].y - selectedPoints[0].y);
}
```

## Constants

```javascript
// Maximum number of selectable points
const MAX_SELECTED_POINTS = 2;

// Visual styling
const SELECTED_POINT_COLOR = '#FFD700';  // Gold
const SELECTED_POINT_SIZE = 16;
const SELECTED_POINT_SYMBOL = 'star';
const SELECTED_POINT_OUTLINE = 'white';
const SELECTED_POINT_OUTLINE_WIDTH = 2;
```

## Files Modified

- `frontend/src/components/Dashboard.js` (main implementation)
- `frontend/src/components/__tests__/Dashboard.ClickHandlers.test.js` (tests)

## Related Components

- Plot (react-plotly.js)
- Dashboard (main component)
- ErrorBoundary (error handling)
- Button (Bootstrap)

## Performance Notes

- Uses `useCallback` for memoization
- WebGL rendering (`scattergl`) for efficiency
- Limited to 2 points to prevent memory issues
- No unnecessary re-renders
- Lightweight state structure

## Browser Support

- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support
- Mobile Safari: Full support
- Chrome Mobile: Full support

## Keyboard Shortcuts

Currently not implemented. Potential additions:
- `Esc` - Clear selection
- `Backspace` - Remove last selection
- `Arrow keys` - Navigate between points

---

**Last Updated:** January 15, 2025
**Version:** 1.0.0
**Maintained by:** Development Team
