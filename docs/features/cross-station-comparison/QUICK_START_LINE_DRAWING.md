# Quick Start: Line Drawing Integration

## 3-Minute Integration Guide

### Step 1: Add Import (Dashboard.js, line ~14)

```javascript
import {
  generateConnectionShapes,
  LINE_STYLES
} from '../utils/lineDrawingUtils';
```

### Step 2: Add to Layout useMemo (Dashboard.js, line ~1175)

```javascript
const layout = useMemo(() => {
  const currentLayout = plotRef.current?.el?.layout;

  // ADD THIS: Generate connection line shapes
  const connectionShapes = generateConnectionShapes(
    selectedPoints,
    LINE_STYLES.measurement  // Teal dashdot line
  );

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
      tickfont: { size: isGraphFullscreen ? 12 : (isMobile ? 9 : 10) }
    },
    yaxis: {
      title: filters.dataType === 'tides' ? 'Tide Level (m)' : 'Sea Level (m)',
      color: 'white',
      gridcolor: '#1e3c72',
      range: currentLayout?.yaxis?.range,
      tickfont: { size: isGraphFullscreen ? 12 : (isMobile ? 9 : 10) }
    },

    shapes: connectionShapes,  // ADD THIS LINE

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
  selectedPoints  // Verify this is in the dependency array
]);
```

### Step 3: Test

1. Start the application
2. Navigate to the graph view
3. Click on a data point (it will show as a star marker)
4. Click on another data point
5. A line should appear connecting the two points

Done! The line will automatically:
- Appear when 2 points are selected
- Disappear when points are deselected
- Stay connected during zoom/pan
- Work in mobile and fullscreen modes

## Optional: Add Metric Annotations

For displaying time and level differences at the midpoint:

```javascript
import {
  generateConnectionShapes,
  createMidpointAnnotation,
  calculateTimeDifference,
  calculateLevelDifference,
  LINE_STYLES
} from '../utils/lineDrawingUtils';

// In layout useMemo:
const connectionShapes = generateConnectionShapes(
  selectedPoints,
  LINE_STYLES.measurement
);

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
  // ... layout properties ...
  shapes: connectionShapes,
  annotations: connectionAnnotations,  // ADD THIS
  // ... rest of layout ...
};
```

## Styling Options

Change the line style by using different presets:

```javascript
// Teal dashdot (recommended)
LINE_STYLES.measurement

// Red solid (bold)
LINE_STYLES.bold

// Gray dashed (subtle)
LINE_STYLES.subtle

// Gold dotted (default)
LINE_STYLES.default

// Or custom:
{
  color: '#FF00FF',
  width: 3,
  dash: 'solid',
  opacity: 0.9
}
```

## Test the Demo

Open the standalone demo in a browser:
```
frontend/public/line-drawing-demo.html
```

## Troubleshooting

**Line doesn't appear:**
- Check that exactly 2 points are selected
- Verify `selectedPoints` has valid x and y values
- Check browser console for errors

**Line disappears on zoom:**
- Verify `shapes: connectionShapes` is in layout object
- Check `uirevision: 'constant'` is set

## Files Reference

| File | Purpose |
|------|---------|
| `frontend/src/utils/lineDrawingUtils.js` | Core utilities |
| `frontend/src/utils/lineDrawingIntegration.md` | Full documentation |
| `frontend/src/utils/dashboardLineIntegrationPatch.js` | Integration code |
| `frontend/src/utils/__tests__/lineDrawingUtils.test.js` | Unit tests |
| `frontend/public/line-drawing-demo.html` | Interactive demo |
| `AGENT_9_LINE_DRAWING_REPORT.md` | Comprehensive report |
| `QUICK_START_LINE_DRAWING.md` | This file |

## Run Tests

```bash
cd frontend
npm test -- lineDrawingUtils.test.js
```

## That's It!

With just 3 steps and less than 10 lines of code, you have fully functional line drawing between selected points that works with zoom, pan, and all dashboard features.

For more advanced features, customization, and detailed documentation, see:
- `AGENT_9_LINE_DRAWING_REPORT.md` - Complete report
- `frontend/src/utils/lineDrawingIntegration.md` - Full integration guide
