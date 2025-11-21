/**
 * DASHBOARD LINE DRAWING INTEGRATION PATCH
 *
 * This file contains the exact code changes needed to integrate line drawing
 * between selected points into Dashboard.js
 *
 * INTEGRATION INSTRUCTIONS:
 * 1. Add import statement at the top of Dashboard.js
 * 2. Add the shape generation code to the layout useMemo
 * 3. Test the implementation
 */

// ============================================================================
// STEP 1: ADD IMPORT STATEMENT
// ============================================================================
// Add this import near the top of Dashboard.js (after line 14):

/*
import {
  generateConnectionShapes,
  createMidpointAnnotation,
  calculateTimeDifference,
  calculateLevelDifference,
  LINE_STYLES
} from '../utils/lineDrawingUtils';
*/

// ============================================================================
// STEP 2: UPDATE LAYOUT USEMEMO
// ============================================================================
// In the layout useMemo (around line 1175-1243), make these changes:

/*
const layout = useMemo(() => {
  const currentLayout = plotRef.current?.el?.layout;

  // ==================== ADD THIS SECTION ====================
  // Generate connection line shapes from selected points
  const connectionShapes = generateConnectionShapes(
    selectedPoints,
    LINE_STYLES.measurement  // Teal dashdot line
  );

  // Optional: Add annotation showing metrics between points
  const connectionAnnotations = [];
  if (selectedPoints.length === 2) {
    const [point1, point2] = selectedPoints;

    // Calculate differences
    const timeDiff = calculateTimeDifference(point1, point2);
    const levelDiff = calculateLevelDifference(point1, point2);

    // Create annotation at midpoint
    connectionAnnotations.push(
      createMidpointAnnotation(
        point1,
        point2,
        `${levelDiff.formatted}<br>${timeDiff}`,
        {
          font: {
            size: isGraphFullscreen ? 14 : (isMobile ? 10 : 12),
            color: '#FFD700',
            family: 'Arial, sans-serif'
          },
          bgcolor: 'rgba(0, 0, 0, 0.8)',
          bordercolor: '#FFD700',
          borderwidth: 1,
          borderpad: 4
        }
      )
    );
  }
  // ==================== END NEW SECTION ====================

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

    // ==================== ADD THESE LINES ====================
    shapes: connectionShapes,
    annotations: connectionAnnotations,
    // ==================== END NEW LINES ====================

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
  selectedPoints  // This should already be here from line 1243
]);
*/

// ============================================================================
// ALTERNATIVE: MINIMAL INTEGRATION (Line Only, No Annotation)
// ============================================================================
// If you want just the line without the annotation, use this simpler version:

/*
const layout = useMemo(() => {
  const currentLayout = plotRef.current?.el?.layout;

  // Generate connection line (simple version)
  const connectionShapes = generateConnectionShapes(
    selectedPoints,
    LINE_STYLES.measurement
  );

  return {
    // ... all existing layout properties ...
    shapes: connectionShapes,
    // ... rest of layout ...
  };
}, [/* ... existing dependencies ...*/, selectedPoints]);
*/

// ============================================================================
// EXAMPLE: CUSTOM STYLING
// ============================================================================
// Different styling options you can use:

const STYLING_EXAMPLES = {
  // Gold dotted line (default)
  goldDotted: {
    color: '#FFD700',
    width: 2,
    dash: 'dot',
    opacity: 0.8,
    layer: 'above'
  },

  // Bold red line for emphasis
  boldRed: {
    color: '#FF6B6B',
    width: 3,
    dash: 'solid',
    opacity: 0.9,
    layer: 'above'
  },

  // Subtle gray line
  subtle: {
    color: '#666666',
    width: 1,
    dash: 'dash',
    opacity: 0.5,
    layer: 'below'
  },

  // Teal measurement line (recommended)
  measurement: {
    color: '#4ECDC4',
    width: 2,
    dash: 'dashdot',
    opacity: 0.85,
    layer: 'above'
  },

  // Dynamic color based on rise/fall
  dynamic: (selectedPoints) => {
    if (selectedPoints.length !== 2) return LINE_STYLES.default;

    const isRising = selectedPoints[1].y > selectedPoints[0].y;
    return {
      color: isRising ? '#FF6B6B' : '#4ECDC4',  // Red for rise, teal for fall
      width: 2,
      dash: 'dashdot',
      opacity: 0.85,
      layer: 'above'
    };
  }
};

// Usage example with dynamic color:
/*
const connectionShapes = generateConnectionShapes(
  selectedPoints,
  STYLING_EXAMPLES.dynamic(selectedPoints)
);
*/

// ============================================================================
// VERIFICATION CHECKLIST
// ============================================================================
/*
After integration, verify:

1. ✓ Import statement added correctly
2. ✓ connectionShapes variable created in useMemo
3. ✓ shapes: connectionShapes added to layout return object
4. ✓ selectedPoints included in useMemo dependency array
5. ✓ No console errors on page load
6. ✓ Line appears when 2 points are selected
7. ✓ Line disappears when points are deselected
8. ✓ Line persists during zoom/pan operations
9. ✓ Annotation shows correct metrics (if enabled)
10. ✓ Works in mobile view and fullscreen mode

Test cases:
- Select 2 points → line appears
- Deselect points → line disappears
- Zoom in → line scales correctly
- Pan graph → line moves with points
- Fullscreen mode → line and annotation visible
- Mobile view → line is visible and properly styled
*/

// ============================================================================
// TROUBLESHOOTING
// ============================================================================
/*
Issue: Line doesn't appear
- Check selectedPoints state has exactly 2 points
- Verify points have valid x and y values
- Check browser console for errors
- Ensure shapes is added to layout object

Issue: Line position is wrong
- Verify x values are Date objects
- Check y values are numbers
- Ensure points have correct structure: { x, y, station, timestamp }

Issue: Line disappears on interaction
- Should NOT happen with native Plotly shapes
- If it does, check uirevision: 'constant' in layout
- Verify selectedPoints is in useMemo dependencies

Issue: Performance problems
- Lines are very lightweight
- If issues occur, check other heavy operations
- Consider using layer: 'below' for better performance
*/

export default {
  STYLING_EXAMPLES,
  integrationNotes: 'See comments above for integration instructions'
};
