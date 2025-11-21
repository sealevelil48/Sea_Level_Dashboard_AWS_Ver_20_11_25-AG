/**
 * Unit tests for line drawing utilities
 * Tests the core functionality of drawing lines between selected points
 */

import {
  generateConnectionShapes,
  createLineBetweenPoints,
  createMidpointAnnotation,
  calculateTimeDifference,
  calculateLevelDifference,
  removeConnectionLines,
  updateLayoutWithConnectionLine,
  LINE_STYLES
} from '../lineDrawingUtils';

describe('lineDrawingUtils', () => {
  // Sample test data
  const point1 = {
    x: new Date('2024-01-01T00:00:00Z'),
    y: 1.5,
    station: 'Ashdod',
    timestamp: '2024-01-01T00:00:00Z',
    pointIndex: 0,
    traceIndex: 0
  };

  const point2 = {
    x: new Date('2024-01-02T12:00:00Z'),
    y: 2.3,
    station: 'Ashdod',
    timestamp: '2024-01-02T12:00:00Z',
    pointIndex: 50,
    traceIndex: 0
  };

  describe('createLineBetweenPoints', () => {
    test('creates a valid line shape object', () => {
      const shape = createLineBetweenPoints(point1, point2);

      expect(shape).toHaveProperty('type', 'line');
      expect(shape).toHaveProperty('x0');
      expect(shape).toHaveProperty('y0', 1.5);
      expect(shape).toHaveProperty('x1');
      expect(shape).toHaveProperty('y1', 2.3);
      expect(shape).toHaveProperty('line');
      expect(shape.line).toHaveProperty('color');
      expect(shape.line).toHaveProperty('width');
      expect(shape.line).toHaveProperty('dash');
    });

    test('applies custom styling options', () => {
      const options = {
        color: '#FF0000',
        width: 5,
        dash: 'solid',
        opacity: 1.0
      };

      const shape = createLineBetweenPoints(point1, point2, options);

      expect(shape.line.color).toBe('#FF0000');
      expect(shape.line.width).toBe(5);
      expect(shape.line.dash).toBe('solid');
      expect(shape.opacity).toBe(1.0);
    });

    test('uses default styling when no options provided', () => {
      const shape = createLineBetweenPoints(point1, point2);

      expect(shape.line.color).toBe('#FFD700');
      expect(shape.line.width).toBe(2);
      expect(shape.line.dash).toBe('dot');
      expect(shape.opacity).toBe(0.8);
    });

    test('handles string date inputs', () => {
      const p1 = { ...point1, x: '2024-01-01T00:00:00Z' };
      const p2 = { ...point2, x: '2024-01-02T12:00:00Z' };

      const shape = createLineBetweenPoints(p1, p2);

      expect(shape.x0).toBeInstanceOf(Date);
      expect(shape.x1).toBeInstanceOf(Date);
    });
  });

  describe('generateConnectionShapes', () => {
    test('returns empty array when no points selected', () => {
      const shapes = generateConnectionShapes([]);
      expect(shapes).toEqual([]);
    });

    test('returns empty array when only one point selected', () => {
      const shapes = generateConnectionShapes([point1]);
      expect(shapes).toEqual([]);
    });

    test('returns array with one shape when two points selected', () => {
      const shapes = generateConnectionShapes([point1, point2]);

      expect(shapes).toHaveLength(1);
      expect(shapes[0]).toHaveProperty('type', 'line');
      expect(shapes[0]).toHaveProperty('name', 'connection-line');
    });

    test('returns empty array when more than two points provided', () => {
      const point3 = { ...point2, pointIndex: 100 };
      const shapes = generateConnectionShapes([point1, point2, point3]);

      expect(shapes).toEqual([]);
    });

    test('returns empty array for invalid points', () => {
      const invalidPoint = { x: null, y: undefined };
      const shapes = generateConnectionShapes([point1, invalidPoint]);

      expect(shapes).toEqual([]);
    });

    test('applies preset styles correctly', () => {
      const shapes = generateConnectionShapes([point1, point2], LINE_STYLES.bold);

      expect(shapes[0].line.color).toBe(LINE_STYLES.bold.color);
      expect(shapes[0].line.width).toBe(LINE_STYLES.bold.width);
    });
  });

  describe('calculateTimeDifference', () => {
    test('calculates time difference in days and hours', () => {
      const diff = calculateTimeDifference(point1, point2);
      expect(diff).toBe('1d 12h');
    });

    test('formats hours and minutes when less than a day', () => {
      const p1 = { x: new Date('2024-01-01T00:00:00Z'), y: 1.0 };
      const p2 = { x: new Date('2024-01-01T03:30:00Z'), y: 1.5 };

      const diff = calculateTimeDifference(p1, p2);
      expect(diff).toBe('3h 30m');
    });

    test('formats minutes only when less than an hour', () => {
      const p1 = { x: new Date('2024-01-01T00:00:00Z'), y: 1.0 };
      const p2 = { x: new Date('2024-01-01T00:45:00Z'), y: 1.5 };

      const diff = calculateTimeDifference(p1, p2);
      expect(diff).toBe('45m');
    });

    test('handles reversed point order', () => {
      const diff1 = calculateTimeDifference(point1, point2);
      const diff2 = calculateTimeDifference(point2, point1);

      expect(diff1).toBe(diff2);
    });

    test('handles string date inputs', () => {
      const p1 = { x: '2024-01-01T00:00:00Z', y: 1.0 };
      const p2 = { x: '2024-01-02T00:00:00Z', y: 1.5 };

      const diff = calculateTimeDifference(p1, p2);
      expect(diff).toBe('1d 0h');
    });
  });

  describe('calculateLevelDifference', () => {
    test('calculates positive level difference (rise)', () => {
      const diff = calculateLevelDifference(point1, point2);

      expect(diff.value).toBeCloseTo(0.8, 3);
      expect(diff.absolute).toBeCloseTo(0.8, 3);
      expect(diff.direction).toBe('rise');
      expect(diff.formatted).toBe('+0.800m');
    });

    test('calculates negative level difference (drop)', () => {
      const diff = calculateLevelDifference(point2, point1);

      expect(diff.value).toBeCloseTo(-0.8, 3);
      expect(diff.absolute).toBeCloseTo(0.8, 3);
      expect(diff.direction).toBe('drop');
      expect(diff.formatted).toBe('-0.800m');
    });

    test('handles zero level difference', () => {
      const p1 = { x: new Date(), y: 1.5 };
      const p2 = { x: new Date(), y: 1.5 };

      const diff = calculateLevelDifference(p1, p2);

      expect(diff.value).toBe(0);
      expect(diff.absolute).toBe(0);
      expect(diff.formatted).toBe('+0.000m');
    });

    test('formats description correctly', () => {
      const diff1 = calculateLevelDifference(point1, point2);
      expect(diff1.description).toBe('0.800m rise');

      const diff2 = calculateLevelDifference(point2, point1);
      expect(diff2.description).toBe('0.800m drop');
    });
  });

  describe('createMidpointAnnotation', () => {
    test('creates annotation at correct midpoint', () => {
      const annotation = createMidpointAnnotation(point1, point2, 'Test');

      expect(annotation).toHaveProperty('x');
      expect(annotation).toHaveProperty('y');
      expect(annotation).toHaveProperty('text', 'Test');
      expect(annotation).toHaveProperty('name', 'connection-annotation');

      // Check y midpoint
      const expectedY = (point1.y + point2.y) / 2;
      expect(annotation.y).toBeCloseTo(expectedY, 3);
    });

    test('applies custom styling options', () => {
      const options = {
        font: { size: 16, color: '#FF0000' },
        bgcolor: 'rgba(255, 0, 0, 0.5)',
        bordercolor: '#FF0000'
      };

      const annotation = createMidpointAnnotation(point1, point2, 'Test', options);

      expect(annotation.font.size).toBe(16);
      expect(annotation.font.color).toBe('#FF0000');
      expect(annotation.bgcolor).toBe('rgba(255, 0, 0, 0.5)');
      expect(annotation.bordercolor).toBe('#FF0000');
    });

    test('uses default styling when no options provided', () => {
      const annotation = createMidpointAnnotation(point1, point2, 'Test');

      expect(annotation.font.size).toBe(12);
      expect(annotation.font.color).toBe('#FFD700');
      expect(annotation.bgcolor).toBe('rgba(0, 0, 0, 0.7)');
    });
  });

  describe('removeConnectionLines', () => {
    test('removes connection line shapes', () => {
      const shapes = [
        { type: 'line', name: 'connection-line' },
        { type: 'rect', name: 'other-shape' },
        { type: 'line', name: 'connection-line' }
      ];

      const filtered = removeConnectionLines(shapes);

      expect(filtered).toHaveLength(1);
      expect(filtered[0].name).toBe('other-shape');
    });

    test('returns empty array for empty input', () => {
      const filtered = removeConnectionLines([]);
      expect(filtered).toEqual([]);
    });

    test('returns all shapes when no connection lines present', () => {
      const shapes = [
        { type: 'rect', name: 'shape1' },
        { type: 'circle', name: 'shape2' }
      ];

      const filtered = removeConnectionLines(shapes);
      expect(filtered).toEqual(shapes);
    });
  });

  describe('updateLayoutWithConnectionLine', () => {
    test('adds connection line to layout', () => {
      const currentLayout = {
        title: 'Test',
        shapes: []
      };

      const updated = updateLayoutWithConnectionLine(
        currentLayout,
        [point1, point2]
      );

      expect(updated.shapes).toHaveLength(1);
      expect(updated.shapes[0].type).toBe('line');
      expect(updated.title).toBe('Test');
    });

    test('preserves existing shapes', () => {
      const currentLayout = {
        shapes: [
          { type: 'rect', name: 'existing-shape' }
        ]
      };

      const updated = updateLayoutWithConnectionLine(
        currentLayout,
        [point1, point2]
      );

      expect(updated.shapes).toHaveLength(2);
      expect(updated.shapes[0].name).toBe('existing-shape');
      expect(updated.shapes[1].name).toBe('connection-line');
    });

    test('removes old connection lines before adding new', () => {
      const currentLayout = {
        shapes: [
          { type: 'line', name: 'connection-line' },
          { type: 'rect', name: 'other-shape' }
        ]
      };

      const updated = updateLayoutWithConnectionLine(
        currentLayout,
        [point1, point2]
      );

      expect(updated.shapes).toHaveLength(2);
      expect(updated.shapes.filter(s => s.name === 'connection-line')).toHaveLength(1);
    });

    test('handles layout without shapes property', () => {
      const currentLayout = { title: 'Test' };

      const updated = updateLayoutWithConnectionLine(
        currentLayout,
        [point1, point2]
      );

      expect(updated.shapes).toHaveLength(1);
    });
  });

  describe('LINE_STYLES presets', () => {
    test('has all required style presets', () => {
      expect(LINE_STYLES).toHaveProperty('default');
      expect(LINE_STYLES).toHaveProperty('subtle');
      expect(LINE_STYLES).toHaveProperty('bold');
      expect(LINE_STYLES).toHaveProperty('measurement');
      expect(LINE_STYLES).toHaveProperty('comparison');
    });

    test('each preset has required properties', () => {
      Object.values(LINE_STYLES).forEach(style => {
        expect(style).toHaveProperty('color');
        expect(style).toHaveProperty('width');
        expect(style).toHaveProperty('dash');
        expect(style).toHaveProperty('opacity');
        expect(style).toHaveProperty('layer');
      });
    });

    test('preset styles have valid values', () => {
      Object.values(LINE_STYLES).forEach(style => {
        expect(typeof style.color).toBe('string');
        expect(typeof style.width).toBe('number');
        expect(style.width).toBeGreaterThan(0);
        expect(style.opacity).toBeGreaterThan(0);
        expect(style.opacity).toBeLessThanOrEqual(1);
        expect(['above', 'below']).toContain(style.layer);
      });
    });
  });

  describe('Edge cases', () => {
    test('handles points with identical coordinates', () => {
      const p1 = { x: new Date('2024-01-01'), y: 1.5 };
      const p2 = { x: new Date('2024-01-01'), y: 1.5 };

      const shape = createLineBetweenPoints(p1, p2);

      expect(shape.x0).toEqual(shape.x1);
      expect(shape.y0).toEqual(shape.y1);
    });

    test('handles very small level differences', () => {
      const p1 = { x: new Date(), y: 1.5000 };
      const p2 = { x: new Date(), y: 1.5001 };

      const diff = calculateLevelDifference(p1, p2);

      expect(diff.formatted).toBe('+0.000m');
      expect(diff.value).toBeCloseTo(0.0001, 4);
    });

    test('handles very large time differences', () => {
      const p1 = { x: new Date('2020-01-01'), y: 1.0 };
      const p2 = { x: new Date('2024-01-01'), y: 2.0 };

      const diff = calculateTimeDifference(p1, p2);

      expect(diff).toContain('d');
      expect(diff).toContain('h');
    });

    test('handles null/undefined in selectedPoints gracefully', () => {
      expect(generateConnectionShapes(null)).toEqual([]);
      expect(generateConnectionShapes(undefined)).toEqual([]);
      expect(generateConnectionShapes([null, point1])).toEqual([]);
      expect(generateConnectionShapes([point1, undefined])).toEqual([]);
    });
  });
});
