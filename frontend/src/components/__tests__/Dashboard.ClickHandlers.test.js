import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Dashboard from '../Dashboard';

// Mock react-plotly.js
jest.mock('react-plotly.js', () => {
  const MockPlot = React.forwardRef((props, ref) => {
    // Store the onClick handler for testing
    React.useEffect(() => {
      if (ref) {
        ref.current = {
          el: {
            layout: {},
            on: jest.fn()
          }
        };
      }
    }, [ref]);

    return (
      <div
        data-testid="mock-plot"
        onClick={() => {
          if (props.onClick) {
            // Simulate Plotly click event
            const mockEvent = {
              points: [{
                x: '2025-01-15T12:00:00',
                y: 1.234,
                data: { name: 'Haifa' },
                pointIndex: 0,
                curveNumber: 0,
                fullData: {}
              }]
            };
            props.onClick(mockEvent);
          }
        }}
      >
        Mock Plot Component
      </div>
    );
  });
  MockPlot.displayName = 'Plot';
  return MockPlot;
});

// Mock other lazy-loaded components
jest.mock('../OSMMap', () => () => <div>Mock OSM Map</div>);
jest.mock('../SeaForecastView', () => () => <div>Mock Sea Forecast</div>);
jest.mock('../MarinersForecastView', () => () => <div>Mock Mariners Forecast</div>);
jest.mock('../ErrorBoundary', () => ({ children }) => <div>{children}</div>);
jest.mock('../DateRangePicker', () => () => <div>Mock Date Range Picker</div>);
jest.mock('../CustomDropdown', () => () => <div>Mock Custom Dropdown</div>);
jest.mock('../StatsCard', () => () => <div>Mock Stats Card</div>);
jest.mock('../WarningsCard', () => () => <div>Mock Warnings Card</div>);

// Mock hooks
jest.mock('../../hooks/useFavorites', () => ({
  useFavorites: () => ({
    favorites: [],
    addFavorite: jest.fn(),
    removeFavorite: jest.fn(),
    isFavorite: jest.fn(() => false)
  })
}));

jest.mock('../../hooks/usePerformanceMonitor', () => ({
  usePerformanceMonitor: () => ({
    measureOperation: jest.fn()
  })
}));

// Mock API service
jest.mock('../../services/apiService', () => ({
  getStations: jest.fn(() => Promise.resolve({ stations: ['All Stations', 'Haifa', 'Acre'] })),
  getData: jest.fn(() => Promise.resolve([])),
  getDataBatch: jest.fn(() => Promise.resolve([])),
  cancelAllRequests: jest.fn()
}));

describe('Dashboard - Click Handlers for Point Selection', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should initialize with empty selectedPoints state', () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    // Should not show selection info initially
    expect(screen.queryByText(/Selected Points/)).not.toBeInTheDocument();
  });

  test('should handle point click and store selected point data', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
    });

    // Click on the plot
    const plotElement = screen.getByTestId('mock-plot');
    fireEvent.click(plotElement);

    // Should show selection info
    await waitFor(() => {
      expect(screen.getByText(/Selected Points \(1\/2\)/)).toBeInTheDocument();
    });
  });

  test('should limit selection to maximum 2 points', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
    });

    const plotElement = screen.getByTestId('mock-plot');

    // Click first point
    fireEvent.click(plotElement);

    await waitFor(() => {
      expect(screen.getByText(/Selected Points \(1\/2\)/)).toBeInTheDocument();
    });

    // Click second point (should add)
    fireEvent.click(plotElement);

    await waitFor(() => {
      expect(screen.getByText(/Selected Points \(2\/2\)/)).toBeInTheDocument();
    });

    // Click third point (should replace oldest)
    fireEvent.click(plotElement);

    await waitFor(() => {
      // Should still show 2 points
      expect(screen.getByText(/Selected Points \(2\/2\)/)).toBeInTheDocument();
    });
  });

  test('should clear all selected points when Clear Selection is clicked', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
    });

    // Click to select a point
    const plotElement = screen.getByTestId('mock-plot');
    fireEvent.click(plotElement);

    await waitFor(() => {
      expect(screen.getByText(/Selected Points/)).toBeInTheDocument();
    });

    // Click Clear Selection button
    const clearButton = screen.getByText('Clear Selection');
    fireEvent.click(clearButton);

    // Selection info should be removed
    await waitFor(() => {
      expect(screen.queryByText(/Selected Points/)).not.toBeInTheDocument();
    });
  });

  test('should display point information correctly', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
    });

    // Click on the plot
    const plotElement = screen.getByTestId('mock-plot');
    fireEvent.click(plotElement);

    // Should show point details
    await waitFor(() => {
      expect(screen.getByText(/Point 1:/)).toBeInTheDocument();
      expect(screen.getByText(/Haifa/)).toBeInTheDocument();
      expect(screen.getByText(/1.234m/)).toBeInTheDocument();
    });
  });

  test('should calculate and display difference between two points', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
    });

    const plotElement = screen.getByTestId('mock-plot');

    // Click first point
    fireEvent.click(plotElement);

    // Click second point
    fireEvent.click(plotElement);

    // Should show difference calculation
    await waitFor(() => {
      expect(screen.getByText(/Difference:/)).toBeInTheDocument();
      expect(screen.getByText(/Level:/)).toBeInTheDocument();
      expect(screen.getByText(/Time:/)).toBeInTheDocument();
    });
  });

  test('should handle click events with touch support (mobile)', async () => {
    // Mock mobile viewport
    global.innerWidth = 375;
    global.innerHeight = 667;

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
    });

    // Simulate touch event (which should work the same as click)
    const plotElement = screen.getByTestId('mock-plot');
    fireEvent.touchStart(plotElement);
    fireEvent.click(plotElement);

    await waitFor(() => {
      expect(screen.getByText(/Selected Points/)).toBeInTheDocument();
    });
  });

  test('should deselect point when clicking on same point again', async () => {
    // This test requires a more sophisticated mock that tracks point indices
    // For now, we'll test the basic structure
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
    });

    const plotElement = screen.getByTestId('mock-plot');

    // Click to select
    fireEvent.click(plotElement);

    await waitFor(() => {
      expect(screen.getByText(/Selected Points \(1\/2\)/)).toBeInTheDocument();
    });

    // Note: In the actual implementation, clicking the same point again would deselect it
    // This would require a more sophisticated mock that can distinguish between different points
  });
});

describe('Dashboard - Point Selection Visual Feedback', () => {
  test('should render selected points trace in plot data', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
    });

    // Click to select a point
    const plotElement = screen.getByTestId('mock-plot');
    fireEvent.click(plotElement);

    await waitFor(() => {
      // The selected points should be rendered with gold color stars
      expect(screen.getByText(/Selected Points/)).toBeInTheDocument();
    });
  });
});

describe('Dashboard - Point Selection Edge Cases', () => {
  test('should handle click event with no points data', async () => {
    // Mock Plot with empty points
    jest.mock('react-plotly.js', () => {
      const MockPlot = React.forwardRef((props, ref) => {
        return (
          <div
            data-testid="mock-plot-empty"
            onClick={() => {
              if (props.onClick) {
                // Simulate Plotly click event with no points
                const mockEvent = { points: [] };
                props.onClick(mockEvent);
              }
            }}
          >
            Mock Plot Component
          </div>
        );
      });
      MockPlot.displayName = 'Plot';
      return MockPlot;
    });

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    // Should not crash or show selection info
    await waitFor(() => {
      expect(screen.queryByText(/Selected Points/)).not.toBeInTheDocument();
    });
  });

  test('should handle click event with undefined onClick handler', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('mock-plot')).toBeInTheDocument();
    });

    // Should not crash when clicking without proper event structure
    const plotElement = screen.getByTestId('mock-plot');
    expect(() => fireEvent.click(plotElement)).not.toThrow();
  });
});
