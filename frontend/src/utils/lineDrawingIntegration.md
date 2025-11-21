# Line Drawing Integration Guide

## Overview
This guide explains how to integrate the line drawing functionality between selected points on the Plotly graph.

## Dependencies
- **Agent 5**: Point Selection (selectedPoints state management)
- **Agent 7**: Distance Calculation utilities
- **Plotly**: react-plotly.js for graph rendering

## File Structure
```
frontend/src/
  utils/
    lineDrawingUtils.js        # Core line drawing utilities
    lineDrawingIntegration.md  # This integration guide
  components/
    Dashboard.js               # Main integration point
```

## Integration Steps

### Step 1: Import the Utilities

Add to the top of `Dashboard.js`:

```javascript
import {
  generateConnectionShapes,
  createMidpointAnnotation,
  calculateTimeDifference,
  calculateLevelDifference,
  LINE_STYLES
} from '../utils/lineDrawingUtils';
```

### Step 2: Update the Layout useMemo

Modify the existing layout useMemo (around line 1175) to include shapes:

```javascript
const layout = useMemo(() => {
  // ... existing layout code ...

  // Generate connection line shapes from selected points
  const connectionShapes = generateConnectionShapes(
    selectedPoints,
    LINE_STYLES.measurement  // Use preset style or custom options
  );

  // Optional: Add annotation showing metrics between points
  const connectionAnnotations = [];
  if (selectedPoints.length === 2) {
    const timeDiff = calculateTimeDifference(selectedPoints[0], selectedPoints[1]);
    const levelDiff = calculateLevelDifference(selectedPoints[0], selectedPoints[1]);

    connectionAnnotations.push(
      createMidpointAnnotation(
        selectedPoints[0],
        selectedPoints[1],
        `${levelDiff.formatted}<br>${timeDiff}`,
        {
          font: { size: isMobile ? 10 : 12, color: '#FFD700' },
          bgcolor: 'rgba(0, 0, 0, 0.8)',
          bordercolor: '#FFD700'
        }
      )
    );
  }

  return {
    // ... existing layout properties ...
    shapes: connectionShapes,           // ADD THIS LINE
    annotations: connectionAnnotations, // ADD THIS LINE (if using annotations)
  };
}, [selectedPoints, /* ... other existing dependencies ... */]);
```

### Step 3: Verify Dependencies in useMemo

Make sure `selectedPoints` is included in the dependency array of the layout useMemo:

```javascript
}, [
  graphData,
  filters.dataType,
  selectedStations,
  filters.showAnomalies,
  filters.trendline,
  filters.analysisType,
  predictions,
  calculateTrendline,
  calculateAnalysis,
  isMobile,
  isGraphFullscreen,
  selectedPoints  // Should already be here from line 1243
]);
```

## Styling Options

### Use Preset Styles

```javascript
// Default style (gold dotted line)
generateConnectionShapes(selectedPoints, LINE_STYLES.default)

// Subtle style (gray dashed line)
generateConnectionShapes(selectedPoints, LINE_STYLES.subtle)

// Bold style (red solid line)
generateConnectionShapes(selectedPoints, LINE_STYLES.bold)

// Measurement style (teal dashdot line) - recommended
generateConnectionShapes(selectedPoints, LINE_STYLES.measurement)

// Comparison style (mint longdash line)
generateConnectionShapes(selectedPoints, LINE_STYLES.comparison)
```

### Custom Styling

```javascript
generateConnectionShapes(selectedPoints, {
  color: '#FF00FF',    // Magenta
  width: 3,            // Thicker line
  dash: 'solid',       // Solid line
  opacity: 0.9,        // More opaque
  layer: 'above'       // Draw above traces
})
```

## Available Line Dash Styles

- `'solid'` - Solid line
- `'dot'` - Dotted line
- `'dash'` - Dashed line
- `'longdash'` - Long dashed line
- `'dashdot'` - Dash-dot pattern
- `'longdashdot'` - Long dash-dot pattern

## Complete Integration Example

Here's a complete example of the layout configuration with line drawing:

```javascript
const layout = useMemo(() => {
  const currentLayout = plotRef.current?.el?.layout;

  // Generate connection shapes
  const connectionShapes = generateConnectionShapes(
    selectedPoints,
    LINE_STYLES.measurement
  );

  // Generate annotations for metrics
  const connectionAnnotations = [];
  if (selectedPoints.length === 2) {
    const [point1, point2] = selectedPoints;

    // Calculate differences
    const timeDiff = calculateTimeDifference(point1, point2);
    const levelDiff = calculateLevelDifference(point1, point2);

    // Create annotation
    connectionAnnotations.push(
      createMidpointAnnotation(
        point1,
        point2,
        `ΔLevel: ${levelDiff.formatted}<br>ΔTime: ${timeDiff}`,
        {
          font: {
            size: isGraphFullscreen ? 14 : (isMobile ? 10 : 12),
            color: '#FFD700'
          },
          bgcolor: 'rgba(0, 0, 0, 0.8)',
          bordercolor: '#FFD700',
          borderwidth: 1
        }
      )
    );
  }

  return {
    title: {
      text: filters.dataType === 'tides' ? 'Tide Levels' : 'Sea Level Over Time',
      font: {
        color: 'white',
        size: isGraphFullscreen ? 20 : (isMobile ? 14 : 16)
      }
    },
    plot_bgcolor: '#142950',
    paper_bgcolor: '#142950',
    font: { color: 'white' },

    xaxis: {
      title: 'Date/Time',
      color: 'white',
      gridcolor: '#1e3c72',
      range: currentLayout?.xaxis?.range,
      tickfont: {
        size: isGraphFullscreen ? 12 : (isMobile ? 9 : 10)
      }
    },

    yaxis: {
      title: filters.dataType === 'tides' ? 'Tide Level (m)' : 'Sea Level (m)',
      color: 'white',
      gridcolor: '#1e3c72',
      range: currentLayout?.yaxis?.range,
      tickfont: {
        size: isGraphFullscreen ? 12 : (isMobile ? 9 : 10)
      }
    },

    // Add shapes and annotations
    shapes: connectionShapes,
    annotations: connectionAnnotations,

    // Other layout properties...
    margin: isGraphFullscreen
      ? { l: 60, r: 40, t: 60, b: 60 }
      : { t: 50, r: 20, b: 50, l: 60 },

    height: 400,
    showlegend: true,
    legend: {
      orientation: isGraphFullscreen ? 'h' : 'v',
      y: isGraphFullscreen ? -0.15 : 1,
      x: isGraphFullscreen ? 0.5 : 0,
      xanchor: isGraphFullscreen ? 'center' : 'left',
      font: {
        color: 'white',
        size: isGraphFullscreen ? 11 : (isMobile ? 9 : 10)
      },
      bgcolor: 'rgba(20, 41, 80, 0.8)',
      bordercolor: '#2a4a8c',
      borderwidth: 1
    },

    dragmode: isMobile ? 'pan' : 'zoom',
    hovermode: 'closest',

    modebar: {
      orientation: 'h',
      bgcolor: 'rgba(20, 41, 80, 0.95)',
      color: 'white',
      activecolor: '#3b82f6'
    },
    uirevision: 'constant'
  };
}, [
  graphData,
  filters.dataType,
  selectedStations,
  filters.showAnomalies,
  filters.trendline,
  filters.analysisType,
  predictions,
  calculateTrendline,
  calculateAnalysis,
  isMobile,
  isGraphFullscreen,
  selectedPoints  // Important: include this dependency
]);
```

## How It Works

### 1. Point Selection (Agent 5)
- User clicks on points in the graph
- `handlePlotClick` updates `selectedPoints` state
- Maximum 2 points can be selected

### 2. Line Drawing (This Agent)
- When `selectedPoints.length === 2`, a line is drawn
- `generateConnectionShapes()` creates a Plotly shape object
- Shape is added to `layout.shapes` array

### 3. Graph Update
- Plotly detects layout change via useMemo dependencies
- Graph re-renders with the connection line
- Line persists during zoom/pan operations

### 4. Line Removal
- When user deselects points, `selectedPoints` changes
- useMemo recalculates, `generateConnectionShapes()` returns `[]`
- Line disappears from graph

## Zoom/Pan Compatibility

The line drawing implementation uses Plotly's native shapes API, which automatically:
- **Scales** with zoom operations
- **Translates** with pan operations
- **Maintains** correct positioning relative to data points
- **Updates** during relayout events

No additional code is needed for zoom/pan compatibility!

## Testing

### Manual Testing Steps

1. **Load the dashboard**
   - Navigate to the graph view
   - Ensure data is displayed

2. **Select first point**
   - Click on any data point on the graph
   - Verify it appears as a gold star marker

3. **Select second point**
   - Click on another data point
   - Verify connection line appears between the two points
   - Check that line is styled correctly (dotted, gold/teal color)

4. **Test zoom**
   - Zoom in on the graph
   - Verify line stays connected to points
   - Zoom out, verify line remains correct

5. **Test pan**
   - Pan the graph in different directions
   - Verify line moves with the points

6. **Test deselection**
   - Click "Clear Selection" or click on a selected point again
   - Verify line disappears when points are deselected

7. **Test annotations** (if enabled)
   - With 2 points selected, verify annotation appears at midpoint
   - Check that metrics (ΔLevel, ΔTime) are calculated correctly

### Edge Cases to Test

- Selecting the same point twice
- Selecting points very close together
- Selecting points very far apart
- Fullscreen mode
- Mobile view
- Different data sources (tides vs sea level)

## Customization Options

### Change Line Color Based on Level Difference

```javascript
const connectionShapes = selectedPoints.length === 2
  ? generateConnectionShapes(selectedPoints, {
      ...LINE_STYLES.measurement,
      color: selectedPoints[1].y > selectedPoints[0].y
        ? '#FF6B6B'  // Red for rise
        : '#4ECDC4'  // Teal for drop
    })
  : [];
```

### Add Multiple Lines

```javascript
// For connecting multiple point pairs
const allShapes = [
  ...generateConnectionShapes([point1, point2], LINE_STYLES.bold),
  ...generateConnectionShapes([point3, point4], LINE_STYLES.subtle),
];
```

### Conditional Styling

```javascript
const getLineStyle = () => {
  if (isMobile) {
    return { ...LINE_STYLES.measurement, width: 1 };
  } else if (isGraphFullscreen) {
    return { ...LINE_STYLES.measurement, width: 3 };
  }
  return LINE_STYLES.measurement;
};

const connectionShapes = generateConnectionShapes(selectedPoints, getLineStyle());
```

## Troubleshooting

### Line doesn't appear
- Check that exactly 2 points are selected
- Verify `selectedPoints` has valid `x` and `y` values
- Check browser console for warnings
- Ensure `shapes` is added to layout object

### Line disappears on zoom
- This shouldn't happen with native Plotly shapes
- If it does, check that `uirevision: 'constant'` is in layout

### Line position is incorrect
- Verify that `x` values are Date objects or valid timestamps
- Check that `y` values are numbers
- Ensure coordinate system matches the data

### Performance issues
- Lines are very lightweight
- If issues occur, check if other heavy operations are running
- Consider using `layer: 'below'` for better performance

## API Reference

See `lineDrawingUtils.js` for complete function documentation.

### Main Functions

- `generateConnectionShapes(selectedPoints, options)` - Main function to create line shapes
- `createLineBetweenPoints(point1, point2, options)` - Creates single line shape
- `createMidpointAnnotation(point1, point2, text, options)` - Creates annotation at midpoint
- `calculateTimeDifference(point1, point2)` - Calculates time between points
- `calculateLevelDifference(point1, point2)` - Calculates level difference between points

### Constants

- `LINE_STYLES` - Preset styling configurations

## Related Documentation

- [Plotly Shapes Documentation](https://plotly.com/javascript/shapes/)
- [Plotly Annotations Documentation](https://plotly.com/javascript/text-and-annotations/)
- Agent 5: Point Selection Implementation
- Agent 7: Distance Calculation Implementation
