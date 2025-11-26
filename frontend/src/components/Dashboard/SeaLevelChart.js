import React, { useRef, useEffect, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  Decimation,
  Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import zoomPlugin from 'chartjs-plugin-zoom';
import 'chartjs-adapter-date-fns';

// 1. Register Chart.js components including zoom plugin
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  Decimation,
  Filler,
  zoomPlugin
);

// 2. Global Styling for "Dark Mode"
ChartJS.defaults.color = '#94a3b8'; // Slate-400 text
ChartJS.defaults.borderColor = 'rgba(255, 255, 255, 0.05)'; // Subtle grid lines
ChartJS.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";

/**
 * SeaLevelChart Component
 *
 * A Chart.js-based chart component for visualizing sea level data with:
 * - Responsive legend positioning (mobile vs desktop)
 * - Performance optimization with decimation
 * - Support for multiple stations
 * - Prediction lines (Kalman, Ensemble, ARIMA, Prophet)
 * - Anomaly highlighting
 * - Trendlines and rolling averages
 */
const SeaLevelChart = React.forwardRef(({
  data,
  activeStations = [], // eslint-disable-line no-unused-vars
  isMobile = false,
  isFullscreen = false, // eslint-disable-line no-unused-vars
  onPointClick = null
}, ref) => {
  const chartRef = useRef(null);
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);

  // Expose chart ref to parent component
  React.useImperativeHandle(ref, () => ({
    exportAsImage: () => {
      if (chartRef.current && chartRef.current.canvas) {
        const canvas = chartRef.current.canvas;
        const url = canvas.toDataURL('image/png');
        return url;
      }
      return null;
    },
    getChart: () => chartRef.current
  }));

  // 3. Smart Resize Listener (Moves Legend on Mobile)
  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Determine if mobile based on window width
  const isMobileView = windowWidth < 768;

  // 4. Chart Configuration
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false, // Disable general animation for performance
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false,
    },
    onClick: (event, elements, chart) => {
      try {
        // Prevent event propagation and default behavior
        if (event && event.native) {
          event.native.preventDefault();
          event.native.stopPropagation();
        }

        if (!onPointClick || !elements || elements.length === 0) {
          return;
        }

        // FIX: When multiple datasets exist at the same x-coordinate,
        // Chart.js returns all of them. We need to find the CLOSEST one
        // to the actual mouse cursor position (y-axis distance matters!)
        let closestElement = elements[0];

        if (elements.length > 1) {
          try {
            // Get the click position in pixels with validation
            const rect = chart.canvas.getBoundingClientRect();
            if (!event.native || typeof event.native.clientX !== 'number' || typeof event.native.clientY !== 'number') {
              console.warn('Invalid mouse coordinates');
              return;
            }

            const mouseX = event.native.clientX - rect.left;
            const mouseY = event.native.clientY - rect.top;

            // Find the element with minimum distance to mouse cursor
            let minDistance = Infinity;

            elements.forEach(element => {
              try {
                // Get the element's pixel position on canvas with comprehensive null checks
                const meta = chart.getDatasetMeta(element.datasetIndex);
                if (!meta || !meta.data || !Array.isArray(meta.data)) {
                  return; // Skip this element
                }

                const elementPosition = meta.data[element.index];

                // Validate elementPosition and its coordinates
                if (elementPosition &&
                    typeof elementPosition.x === 'number' &&
                    typeof elementPosition.y === 'number' &&
                    !isNaN(elementPosition.x) &&
                    !isNaN(elementPosition.y)) {
                  const elementX = elementPosition.x;
                  const elementY = elementPosition.y;

                  // Calculate Euclidean distance from mouse to element
                  const distance = Math.sqrt(
                    Math.pow(mouseX - elementX, 2) +
                    Math.pow(mouseY - elementY, 2)
                  );

                  // Update closest element if this one is closer
                  if (distance < minDistance) {
                    minDistance = distance;
                    closestElement = element;
                  }
                }
              } catch (elementError) {
                console.warn('Error processing element:', elementError);
              }
            });
          } catch (distanceError) {
            console.warn('Error calculating distances:', distanceError);
          }
        }

        // Validate closestElement before accessing
        if (!closestElement ||
            typeof closestElement.datasetIndex !== 'number' ||
            typeof closestElement.index !== 'number') {
          return;
        }

        // Use the closest element instead of always using elements[0]
        const datasetIndex = closestElement.datasetIndex;
        const dataIndex = closestElement.index;

        // Validate dataset exists
        if (!chart.data || !chart.data.datasets || !chart.data.datasets[datasetIndex]) {
          return;
        }

        const dataset = chart.data.datasets[datasetIndex];

        // Validate point exists
        if (!dataset.data || !dataset.data[dataIndex]) {
          return;
        }

        const point = dataset.data[dataIndex];

        // Validate point data
        if (!point || typeof point.x === 'undefined' || typeof point.y === 'undefined') {
          return;
        }

        // Only allow clicking on station data (not predictions, anomalies, trendlines, etc.)
        const label = dataset.label || '';
        const isStationData = !label.includes('Kalman') &&
                             !label.includes('Ensemble') &&
                             !label.includes('ARIMA') &&
                             !label.includes('Prophet') &&
                             !label.includes('Trendline') &&
                             !label.includes('Avg') &&
                             !label.includes('Anomalies') &&
                             !label.includes('Selected Points') &&
                             !label.includes('Connection Line') &&
                             !label.includes('CI');

        if (isStationData) {
          onPointClick({
            x: point.x,
            y: point.y,
            station: dataset.label,
            timestamp: point.x,
            pointIndex: dataIndex,
            traceIndex: datasetIndex,
            fullData: dataset
          });
        }
      } catch (error) {
        console.error('Error in chart click handler:', error);
      }
    },
    plugins: {
      zoom: {
        pan: {
          enabled: true,
          mode: 'xy',
          modifierKey: null, // No need to hold a key
        },
        zoom: {
          wheel: {
            enabled: true,
            speed: 0.1,
          },
          pinch: {
            enabled: true,
          },
          mode: 'xy',
        },
        // No limits - allow panning to see predictions in future dates
      },
      decimation: {
        enabled: true,
        algorithm: 'lttb', // "Largest-Triangle-Three-Buckets" (Preserves peaks)
        samples: 500, // Downsamples 10k points to 500 pixels when zoomed out
      },
      legend: {
        position: isMobileView || isMobile ? 'bottom' : 'top', // UX WIN: Moves legend below chart on mobile
        align: 'start',
        labels: {
          boxWidth: 10,
          usePointStyle: true,
          color: '#e2e8f0', // High contrast text
          padding: 20,
          font: {
            size: isMobileView ? 10 : 12
          }
        },
      },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.95)', // Deep blue background
        titleColor: '#f8fafc',
        bodyColor: '#cbd5e1',
        borderColor: 'rgba(56, 189, 248, 0.3)', // Cyan border glow
        borderWidth: 1,
        padding: 12,
        boxPadding: 4,
        displayColors: true,
        callbacks: {
          label: function (context) {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null && context.parsed.y !== undefined && typeof context.parsed.y === 'number' && !isNaN(context.parsed.y)) {
              label += context.parsed.y.toFixed(3) + ' m';
            }
            return label;
          },
          title: function (context) {
            if (context[0] && context[0].parsed.x) {
              const date = new Date(context[0].parsed.x);
              return date.toLocaleString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              });
            }
            return '';
          }
        },
      },
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'day',
          displayFormats: {
            hour: 'HH:mm',
            day: 'MMM dd',
            week: 'MMM dd',
            month: 'MMM yyyy'
          },
        },
        grid: {
          display: false, // Cleaner look
          color: 'rgba(255, 255, 255, 0.05)'
        },
        ticks: {
          source: 'auto',
          maxRotation: isMobileView ? 45 : 0,
          autoSkip: true,
          color: '#94a3b8',
          font: {
            size: isMobileView ? 9 : 11
          }
        },
      },
      y: {
        beginAtZero: false, // Sea level can be negative relative to reference
        title: {
          display: !isMobileView,
          text: 'Sea Level (m)',
          color: '#94a3b8'
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.05)' // Very subtle horizontal lines
        },
        ticks: {
          color: '#94a3b8',
          font: {
            size: isMobileView ? 9 : 11
          }
        }
      },
    },
  };

  // Fallback for empty or invalid data
  if (!data || !data.datasets || data.datasets.length === 0) {
    return (
      <div className="chart-container" style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#94a3b8'
      }}>
        <p>No data available to display</p>
      </div>
    );
  }

  return (
    <div className="chart-container" style={{ position: 'relative', height: '100%', width: '100%' }}>
      <Line ref={chartRef} data={data} options={options} />
    </div>
  );
});

SeaLevelChart.displayName = 'SeaLevelChart';

export default SeaLevelChart;
