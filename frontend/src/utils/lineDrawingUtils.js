/**
 * Line Drawing Utilities for Plotly Graphs
 *
 * This module provides utilities for drawing visual lines between selected points
 * on Plotly graphs using the layout.shapes API.
 *
 * Dependencies: Coordinate with Agent 5 (Point Selection) and Agent 7 (Distance Calculation)
 */

/**
 * Creates a Plotly shape object for a line between two points
 *
 * @param {Object} point1 - First selected point { x, y, station, timestamp }
 * @param {Object} point2 - Second selected point { x, y, station, timestamp }
 * @param {Object} options - Optional styling configuration
 * @returns {Object} Plotly shape object for the line
 */
export function createLineBetweenPoints(point1, point2, options = {}) {
  const {
    color = '#FFD700',      // Gold/yellow color
    width = 2,              // Line width
    dash = 'dot',           // Line style: 'solid', 'dot', 'dash', 'longdash', 'dashdot', 'longdashdot'
    opacity = 0.8,          // Line opacity
    layer = 'above'         // Draw above or below traces: 'above' or 'below'
  } = options;

  // Convert date strings to Date objects if necessary
  const x0 = point1.x instanceof Date ? point1.x : new Date(point1.x);
  const x1 = point2.x instanceof Date ? point2.x : new Date(point2.x);

  return {
    type: 'line',
    x0: x0,
    y0: point1.y,
    x1: x1,
    y1: point2.y,
    line: {
      color: color,
      width: width,
      dash: dash
    },
    opacity: opacity,
    layer: layer,
    // Add identifier for easy removal
    name: 'connection-line'
  };
}

/**
 * Creates multiple line shapes from an array of point pairs
 *
 * @param {Array} pointPairs - Array of [point1, point2] pairs
 * @param {Object} options - Optional styling configuration
 * @returns {Array} Array of Plotly shape objects
 */
export function createMultipleLines(pointPairs, options = {}) {
  return pointPairs.map(([point1, point2]) =>
    createLineBetweenPoints(point1, point2, options)
  );
}

/**
 * Generates a shape configuration for connecting selected points
 * This is the main function to use in Dashboard component
 *
 * @param {Array} selectedPoints - Array of selected point objects
 * @param {Object} options - Optional styling configuration
 * @returns {Array} Array of shape objects to add to layout.shapes
 */
export function generateConnectionShapes(selectedPoints, options = {}) {
  // Only draw line if exactly 2 points are selected
  if (!selectedPoints || selectedPoints.length !== 2) {
    return [];
  }

  const [point1, point2] = selectedPoints;

  // Validate points have required properties
  if (!isValidPoint(point1) || !isValidPoint(point2)) {
    console.warn('Invalid points provided to generateConnectionShapes:', { point1, point2 });
    return [];
  }

  return [createLineBetweenPoints(point1, point2, options)];
}

/**
 * Validates that a point object has required properties
 *
 * @param {Object} point - Point object to validate
 * @returns {boolean} True if point is valid
 */
function isValidPoint(point) {
  return point &&
         (point.x !== undefined && point.x !== null) &&
         (point.y !== undefined && point.y !== null);
}

/**
 * Removes all connection line shapes from existing shapes array
 *
 * @param {Array} existingShapes - Current shapes array from layout
 * @returns {Array} Filtered shapes array without connection lines
 */
export function removeConnectionLines(existingShapes = []) {
  return existingShapes.filter(shape => shape.name !== 'connection-line');
}

/**
 * Updates layout with connection line shapes
 * This function merges existing shapes with new connection lines
 *
 * @param {Object} currentLayout - Current Plotly layout object
 * @param {Array} selectedPoints - Array of selected point objects
 * @param {Object} options - Optional styling configuration
 * @returns {Object} Updated layout object with shapes
 */
export function updateLayoutWithConnectionLine(currentLayout, selectedPoints, options = {}) {
  // Get existing shapes (excluding old connection lines)
  const existingShapes = removeConnectionLines(currentLayout.shapes || []);

  // Generate new connection shapes
  const connectionShapes = generateConnectionShapes(selectedPoints, options);

  // Merge shapes
  const allShapes = [...existingShapes, ...connectionShapes];

  return {
    ...currentLayout,
    shapes: allShapes
  };
}

/**
 * Creates an annotation (text label) at the midpoint of the line
 * Useful for displaying distance or other metrics
 *
 * @param {Object} point1 - First selected point
 * @param {Object} point2 - Second selected point
 * @param {string} text - Text to display
 * @param {Object} options - Optional styling configuration
 * @returns {Object} Plotly annotation object
 */
export function createMidpointAnnotation(point1, point2, text, options = {}) {
  const {
    font = { size: 12, color: '#FFD700' },
    bgcolor = 'rgba(0, 0, 0, 0.7)',
    bordercolor = '#FFD700',
    borderwidth = 1,
    borderpad = 4,
    showarrow = false
  } = options;

  // Calculate midpoint
  const x0 = point1.x instanceof Date ? point1.x : new Date(point1.x);
  const x1 = point2.x instanceof Date ? point2.x : new Date(point2.x);

  const midX = new Date((x0.getTime() + x1.getTime()) / 2);
  const midY = (point1.y + point2.y) / 2;

  return {
    x: midX,
    y: midY,
    text: text,
    showarrow: showarrow,
    font: font,
    bgcolor: bgcolor,
    bordercolor: bordercolor,
    borderwidth: borderwidth,
    borderpad: borderpad,
    // Add identifier for easy removal
    name: 'connection-annotation'
  };
}

/**
 * Removes all connection annotations from existing annotations array
 *
 * @param {Array} existingAnnotations - Current annotations array from layout
 * @returns {Array} Filtered annotations array without connection annotations
 */
export function removeConnectionAnnotations(existingAnnotations = []) {
  return existingAnnotations.filter(ann => ann.name !== 'connection-annotation');
}

/**
 * Default styling presets for different use cases
 */
export const LINE_STYLES = {
  // Highlighted connection line (default)
  default: {
    color: '#FFD700',     // Gold
    width: 2,
    dash: 'dot',
    opacity: 0.8,
    layer: 'above'
  },

  // Subtle connection line
  subtle: {
    color: '#666666',
    width: 1,
    dash: 'dash',
    opacity: 0.5,
    layer: 'below'
  },

  // Bold connection line
  bold: {
    color: '#FF6B6B',     // Red
    width: 3,
    dash: 'solid',
    opacity: 0.9,
    layer: 'above'
  },

  // Measurement line (for distance calculations)
  measurement: {
    color: '#4ECDC4',     // Teal
    width: 2,
    dash: 'dashdot',
    opacity: 0.85,
    layer: 'above'
  },

  // Comparison line
  comparison: {
    color: '#95E1D3',     // Mint
    width: 2,
    dash: 'longdash',
    opacity: 0.75,
    layer: 'above'
  }
};

/**
 * Example usage function demonstrating integration
 * This shows how to use the utilities in a React component
 */
export function exampleUsage() {
  /* Example integration in Dashboard.js:

  // Import the utilities
  import {
    generateConnectionShapes,
    createMidpointAnnotation,
    LINE_STYLES
  } from '../utils/lineDrawingUtils';

  // In your layout useMemo:
  const layout = useMemo(() => {
    // ... existing layout configuration ...

    // Generate connection line shapes from selected points
    const connectionShapes = generateConnectionShapes(
      selectedPoints,
      LINE_STYLES.measurement  // Use preset or custom options
    );

    // Optional: Add annotation with distance/time difference
    const annotations = [];
    if (selectedPoints.length === 2) {
      const timeDiff = calculateTimeDifference(selectedPoints[0], selectedPoints[1]);
      const levelDiff = (selectedPoints[1].y - selectedPoints[0].y).toFixed(3);

      annotations.push(
        createMidpointAnnotation(
          selectedPoints[0],
          selectedPoints[1],
          `ΔLevel: ${levelDiff}m<br>ΔTime: ${timeDiff}`
        )
      );
    }

    return {
      // ... other layout properties ...
      shapes: connectionShapes,  // Add shapes to layout
      annotations: annotations    // Add annotations to layout
    };
  }, [selectedPoints]);

  */

  return null;
}

/**
 * Helper function to calculate time difference between two points
 *
 * @param {Object} point1 - First point with x (timestamp)
 * @param {Object} point2 - Second point with x (timestamp)
 * @returns {string} Formatted time difference string
 */
export function calculateTimeDifference(point1, point2) {
  const time1 = point1.x instanceof Date ? point1.x : new Date(point1.x);
  const time2 = point2.x instanceof Date ? point2.x : new Date(point2.x);

  const diffMs = Math.abs(time2 - time1);

  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

  if (days > 0) {
    return `${days}d ${hours}h`;
  } else if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else {
    return `${minutes}m`;
  }
}

/**
 * Helper function to calculate vertical distance (level difference)
 *
 * @param {Object} point1 - First point with y (level)
 * @param {Object} point2 - Second point with y (level)
 * @returns {Object} Object with difference and formatted string
 */
export function calculateLevelDifference(point1, point2) {
  const diff = point2.y - point1.y;
  const absDiff = Math.abs(diff);
  const direction = diff > 0 ? 'rise' : 'drop';

  return {
    value: diff,
    absolute: absDiff,
    direction: direction,
    formatted: `${diff >= 0 ? '+' : ''}${diff.toFixed(3)}m`,
    description: `${absDiff.toFixed(3)}m ${direction}`
  };
}
