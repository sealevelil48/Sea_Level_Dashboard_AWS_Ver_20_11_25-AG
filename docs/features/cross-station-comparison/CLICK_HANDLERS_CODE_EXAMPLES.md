# Click Handlers - Code Examples and Snippets

## Complete Implementation Snippets

### 1. State Declaration

```javascript
// Location: Dashboard.js, Line 76-79
// Point selection state for click handlers
const [selectedPoints, setSelectedPoints] = useState([]);
// Structure: [{ x, y, station, timestamp, pointIndex, traceIndex }, ...]
// Maximum 2 points can be selected
```

### 2. Click Handler Function

```javascript
// Location: Dashboard.js, Line 1349-1389
// Handle Plotly click events for point selection
const handlePlotClick = useCallback((event) => {
  if (!event.points || event.points.length === 0) return;

  const clickedPoint = event.points[0];

  // Extract point data
  const pointData = {
    x: clickedPoint.x,
    y: clickedPoint.y,
    station: clickedPoint.data.name || 'Unknown',
    timestamp: clickedPoint.x,
    pointIndex: clickedPoint.pointIndex,
    traceIndex: clickedPoint.curveNumber,
    fullData: clickedPoint.fullData
  };

  // Check if point is already selected
  const isAlreadySelected = selectedPoints.some(
    p => p.pointIndex === pointData.pointIndex &&
         p.traceIndex === pointData.traceIndex
  );

  setSelectedPoints(prev => {
    if (isAlreadySelected) {
      // Deselect the point
      return prev.filter(
        p => !(p.pointIndex === pointData.pointIndex &&
               p.traceIndex === pointData.traceIndex)
      );
    } else {
      // Add new point (max 2 points)
      if (prev.length >= 2) {
        // Replace oldest point (first in array)
        return [...prev.slice(1), pointData];
      } else {
        return [...prev, pointData];
      }
    }
  });
}, [selectedPoints]);

// Clear all selected points
const handleClearSelection = useCallback(() => {
  setSelectedPoints([]);
}, []);
```

### 3. Visual Feedback Trace

```javascript
// Location: Dashboard.js, Line 1024-1046
// Inside createPlot useMemo, add to traces array:

// ADD SELECTED POINTS TRACE FOR VISUAL FEEDBACK
if (selectedPoints.length > 0) {
  traces.push({
    x: selectedPoints.map(p => p.x),
    y: selectedPoints.map(p => p.y),
    type: 'scattergl',
    mode: 'markers',
    name: 'Selected Points',
    marker: {
      color: '#FFD700',  // Gold color
      size: 16,
      symbol: 'star',
      line: { color: 'white', width: 2 }
    },
    hovertemplate: selectedPoints.map((p, idx) =>
      `<b>Selected Point ${idx + 1}</b><br>` +
      `Station: ${p.station}<br>` +
      `Time: ${p.timestamp}<br>` +
      `Level: ${typeof p.y === 'number' ? p.y.toFixed(3) : p.y}m<extra></extra>`
    ),
    showlegend: true
  });
}
```

### 4. Plot Component with onClick

```javascript
// Location: Dashboard.js, Line 1796-1826
<Suspense fallback={<div className="text-center p-5"><Spinner animation="border" variant="primary" /><p className="mt-2">Loading chart...</p></div>}>
  <Plot
    ref={plotRef}
    data={createPlot.data}
    layout={{
      ...createPlot.layout,
      height: isGraphFullscreen ? (window.innerHeight - 60) : undefined
    }}
    config={{
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToAdd: [],
      modeBarButtonsToRemove: isGraphFullscreen ? [] : ['select2d', 'lasso2d'],
      scrollZoom: true,
      doubleClick: 'reset',
      showTips: true,
      toImageButtonOptions: {
        format: 'png',
        filename: 'sea_level_graph',
        height: 1080,
        width: 1920
      }
    }}
    style={{
      width: '100%',
      height: '100%'
    }}
    useResizeHandler={true}
    onClick={handlePlotClick}  // ← Click handler
  />
</Suspense>
```

### 5. Point Selection Info Panel

```javascript
// Location: Dashboard.js, Line 1829-1866
{/* Point Selection Info and Controls */}
{selectedPoints.length > 0 && (
  <div className="mt-2 p-2" style={{
    backgroundColor: 'rgba(20, 41, 80, 0.8)',
    borderRadius: '6px',
    border: '1px solid #2a4a8c'
  }}>
    <div className="d-flex justify-content-between align-items-center mb-2">
      <small className="text-white fw-bold">Selected Points ({selectedPoints.length}/2)</small>
      <Button
        variant="outline-danger"
        size="sm"
        onClick={handleClearSelection}
        style={{ fontSize: '0.65rem', padding: '2px 8px' }}
      >
        Clear Selection
      </Button>
    </div>
    {selectedPoints.map((point, idx) => (
      <div key={idx} className="mb-1" style={{ fontSize: '0.75rem', color: '#FFD700' }}>
        <strong>Point {idx + 1}:</strong> {point.station} |
        Time: {new Date(point.timestamp).toLocaleString()} |
        Level: {typeof point.y === 'number' ? point.y.toFixed(3) : point.y}m
      </div>
    ))}
    {selectedPoints.length === 2 && (
      <div className="mt-2 pt-2" style={{
        borderTop: '1px solid #2a4a8c',
        fontSize: '0.75rem',
        color: '#4dabf5'
      }}>
        <strong>Difference:</strong> {' '}
        Level: {Math.abs(selectedPoints[1].y - selectedPoints[0].y).toFixed(3)}m |
        Time: {Math.abs(new Date(selectedPoints[1].timestamp) - new Date(selectedPoints[0].timestamp)) / (1000 * 60 * 60)} hours
      </div>
    )}
  </div>
)}
```

### 6. Updated useMemo Dependencies

```javascript
// Location: Dashboard.js, Line 1243
}, [graphData, filters.dataType, selectedStations, filters.showAnomalies,
    filters.trendline, filters.analysisType, predictions,
    calculateTrendline, calculateAnalysis, isMobile, isGraphFullscreen,
    selectedPoints]);  // ← Added selectedPoints
```

## Usage Examples

### Example 1: Basic Point Selection

```javascript
// User clicks on a point
const event = {
  points: [{
    x: '2025-01-15T12:00:00',
    y: 1.234,
    data: { name: 'Haifa' },
    pointIndex: 0,
    curveNumber: 0
  }]
};

handlePlotClick(event);

// Result:
// selectedPoints = [
//   {
//     x: '2025-01-15T12:00:00',
//     y: 1.234,
//     station: 'Haifa',
//     timestamp: '2025-01-15T12:00:00',
//     pointIndex: 0,
//     traceIndex: 0
//   }
// ]
```

### Example 2: Selecting Two Points

```javascript
// First click
handlePlotClick(event1);
// selectedPoints.length = 1

// Second click
handlePlotClick(event2);
// selectedPoints.length = 2

// Info panel shows both points and difference
```

### Example 3: FIFO Replacement

```javascript
// State: [Point A, Point B]
// User clicks Point C

handlePlotClick(eventC);

// Result: [Point B, Point C]
// Point A is removed (oldest)
```

### Example 4: Toggle Selection

```javascript
// State: [Point A]
// User clicks Point A again

handlePlotClick(eventA);

// Result: []
// Point A is deselected
```

### Example 5: Clear All

```javascript
// State: [Point A, Point B]

handleClearSelection();

// Result: []
// All points cleared
```

## Styling Constants

```javascript
// Color scheme
const COLORS = {
  selectedPointColor: '#FFD700',      // Gold
  selectedPointOutline: 'white',      // White
  infoPanelBackground: 'rgba(20, 41, 80, 0.8)',  // Semi-transparent blue
  infoPanelBorder: '#2a4a8c',         // Medium blue
  pointTextColor: '#FFD700',          // Gold
  differenceTextColor: '#4dabf5'      // Light blue
};

// Sizes
const SIZES = {
  markerSize: 16,
  markerOutlineWidth: 2,
  borderRadius: '6px',
  fontSize: '0.75rem',
  buttonFontSize: '0.65rem',
  buttonPadding: '2px 8px'
};

// Symbols
const SYMBOLS = {
  markerSymbol: 'star',
  maxPoints: 2
};
```

## Helper Functions

```javascript
// Format timestamp for display
const formatTimestamp = (timestamp) => {
  return new Date(timestamp).toLocaleString();
};

// Calculate level difference
const calculateLevelDifference = (point1, point2) => {
  return Math.abs(point2.y - point1.y).toFixed(3);
};

// Calculate time difference in hours
const calculateTimeDifference = (point1, point2) => {
  const diff = Math.abs(
    new Date(point2.timestamp) - new Date(point1.timestamp)
  );
  return (diff / (1000 * 60 * 60)).toFixed(2);
};

// Check if point is selected
const isPointSelected = (point, selectedPoints) => {
  return selectedPoints.some(
    p => p.pointIndex === point.pointIndex &&
         p.traceIndex === point.traceIndex
  );
};
```

## Testing Examples

### Unit Test for Click Handler

```javascript
describe('handlePlotClick', () => {
  it('should add point to selection', () => {
    const mockEvent = {
      points: [{
        x: '2025-01-15T12:00:00',
        y: 1.234,
        data: { name: 'Haifa' },
        pointIndex: 0,
        curveNumber: 0
      }]
    };

    // Initial state: []
    handlePlotClick(mockEvent);

    // Expected state: [{ x, y, station, ... }]
    expect(selectedPoints).toHaveLength(1);
    expect(selectedPoints[0].station).toBe('Haifa');
  });
});
```

### Integration Test

```javascript
describe('Point Selection Integration', () => {
  it('should display gold stars when points are selected', async () => {
    render(<Dashboard />);

    // Click on plot
    const plot = screen.getByTestId('plot');
    fireEvent.click(plot);

    // Check for visual feedback
    await waitFor(() => {
      expect(screen.getByText(/Selected Points/)).toBeInTheDocument();
    });

    // Verify plot data includes selected points trace
    const plotComponent = screen.getByTestId('plot');
    expect(plotComponent.props.data).toContainEqual(
      expect.objectContaining({
        name: 'Selected Points',
        marker: expect.objectContaining({ color: '#FFD700' })
      })
    );
  });
});
```

## Common Patterns

### Pattern 1: Safe Point Access

```javascript
// Always check if event and points exist
if (!event.points || event.points.length === 0) return;

// Use optional chaining and defaults
const station = clickedPoint.data?.name || 'Unknown';
const value = typeof point.y === 'number' ? point.y.toFixed(3) : point.y;
```

### Pattern 2: Immutable State Updates

```javascript
// Don't mutate state directly
// ❌ selectedPoints.push(newPoint);

// Use immutable operations
// ✅ setSelectedPoints(prev => [...prev, newPoint]);
// ✅ setSelectedPoints(prev => prev.filter(...));
// ✅ setSelectedPoints(prev => prev.slice(1).concat(newPoint));
```

### Pattern 3: Conditional Rendering

```javascript
// Only render when needed
{selectedPoints.length > 0 && (
  <InfoPanel points={selectedPoints} />
)}

// Conditional styling
style={{
  display: selectedPoints.length > 0 ? 'block' : 'none'
}}
```

### Pattern 4: Array Operations

```javascript
// Add to end
setSelectedPoints(prev => [...prev, newPoint]);

// Remove specific item
setSelectedPoints(prev => prev.filter(p => p.pointIndex !== index));

// Replace oldest (FIFO)
setSelectedPoints(prev => [...prev.slice(1), newPoint]);

// Clear all
setSelectedPoints([]);
```

## Debugging Tips

### Log Event Data

```javascript
const handlePlotClick = useCallback((event) => {
  console.log('Click event:', event);
  console.log('Points:', event.points);
  console.log('First point:', event.points[0]);
  // ... rest of handler
}, [selectedPoints]);
```

### Log State Changes

```javascript
useEffect(() => {
  console.log('Selected points changed:', selectedPoints);
}, [selectedPoints]);
```

### Verify Trace Addition

```javascript
const createPlot = useMemo(() => {
  // ...
  console.log('Total traces:', traces.length);
  console.log('Selected points trace:', traces.find(t => t.name === 'Selected Points'));
  // ...
}, [...dependencies]);
```

## Performance Profiling

```javascript
// Measure click handler performance
const handlePlotClick = useCallback((event) => {
  const start = performance.now();

  // ... handler logic ...

  const end = performance.now();
  console.log(`Click handler took ${end - start}ms`);
}, [selectedPoints]);

// Measure render performance
useEffect(() => {
  const start = performance.now();
  // Component rendered
  const end = performance.now();
  console.log(`Render took ${end - start}ms`);
});
```

## Accessibility Enhancements (Future)

```javascript
// Add ARIA labels
<Button
  onClick={handleClearSelection}
  aria-label="Clear all selected points"
>
  Clear Selection
</Button>

// Add keyboard support
const handleKeyDown = (event) => {
  if (event.key === 'Escape') {
    handleClearSelection();
  }
};

// Add screen reader announcements
<div role="status" aria-live="polite">
  {selectedPoints.length > 0 && (
    `${selectedPoints.length} point${selectedPoints.length > 1 ? 's' : ''} selected`
  )}
</div>
```

---

**Last Updated:** January 15, 2025
**Version:** 1.0.0
**Maintained By:** Development Team
