import { useMemo, useCallback } from 'react';
import { generateConnectionShapes, LINE_STYLES } from '../utils/lineDrawingUtils';

/**
 * Calculate trendline for sea level data
 * Supports various time periods: 7d, 30d, 90d, 1y, last_decade, last_two_decades, all
 *
 * @param {Array} data - Array of data points with Tab_DateTime and Tab_Value_mDepthC1
 * @param {string} period - Time period for trendline calculation
 * @returns {Object|null} Plotly trace object for trendline or null
 */
const calculateTrendline = (data, period) => {
  if (!data || data.length < 2 || period === 'none') return null;

  const periodDays = {
    '7d': 7,
    '30d': 30,
    '90d': 90,
    '1y': 365,
    'last_decade': 3650,
    'last_two_decades': 7300,
    'all': null
  };

  const days = periodDays[period];
  let filteredData = data;

  if (days !== null) {
    const endDate = new Date(data[data.length - 1].Tab_DateTime);
    const startDate = new Date(endDate - days * 24 * 60 * 60 * 1000);
    filteredData = data.filter(d => new Date(d.Tab_DateTime) >= startDate);
  }

  if (filteredData.length < 2) return null;

  const n = filteredData.length;
  const xValues = filteredData.map((_, i) => i);
  const yValues = filteredData.map(d => d.Tab_Value_mDepthC1);

  // Simple linear regression
  const sumX = xValues.reduce((a, b) => a + b, 0);
  const sumY = yValues.reduce((a, b) => a + b, 0);
  const sumXY = xValues.reduce((sum, x, i) => sum + x * yValues[i], 0);
  const sumXX = xValues.reduce((sum, x) => sum + x * x, 0);

  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;

  return {
    x: filteredData.map(d => d.Tab_DateTime),
    y: xValues.map(x => slope * x + intercept),
    type: 'scattergl',
    mode: 'lines',
    name: `Trendline (${period})`,
    line: { color: 'yellow', dash: 'dash', width: 2 }
  };
};

/**
 * Calculate rolling average analysis for sea level data
 * Supports 3h, 6h, 24h rolling averages
 *
 * @param {Array} data - Array of data points
 * @param {string} analysisType - Type of analysis (rolling_avg_3h, rolling_avg_6h, rolling_avg_24h, all)
 * @returns {Object|Array|null} Plotly trace object(s) or null
 */
const calculateAnalysis = (data, analysisType) => {
  if (!data || data.length === 0 || analysisType === 'none') return null;

  const analyses = {
    'rolling_avg_3h': { window: 3, name: '3-Hour Avg', color: 'violet' },
    'rolling_avg_6h': { window: 6, name: '6-Hour Avg', color: 'cyan' },
    'rolling_avg_24h': { window: 24, name: '24-Hour Avg', color: 'magenta' },
    'all': null
  };

  if (analysisType === 'all') {
    return Object.entries(analyses)
      .filter(([key]) => key !== 'all')
      .map(([key]) => calculateAnalysis(data, key))
      .filter(Boolean);
  }

  const config = analyses[analysisType];
  if (!config) return null;

  const rollingAvg = [];
  const windowSize = config.window;

  for (let i = 0; i < data.length; i++) {
    const start = Math.max(0, i - windowSize + 1);
    const window = data.slice(start, i + 1);
    const validValues = window.map(d => d.Tab_Value_mDepthC1).filter(v => !isNaN(v));
    const avg = validValues.length > 0
      ? validValues.reduce((sum, v) => sum + v, 0) / validValues.length
      : null;
    rollingAvg.push(avg);
  }

  return {
    x: data.map(d => d.Tab_DateTime),
    y: rollingAvg,
    type: 'scattergl',
    mode: 'lines',
    name: config.name,
    line: {
      color: config.color,
      width: 2,
      shape: 'spline',
      smoothing: 1.3
    }
  };
};

/**
 * Custom hook to generate Plotly chart configuration for sea level dashboard
 *
 * @param {Object} params - Hook parameters
 * @param {Array} params.graphData - Array of sea level data points
 * @param {Object} params.predictions - Predictions object keyed by station
 * @param {Object} params.filters - Filter settings (dataType, showAnomalies, trendline, analysisType)
 * @param {Array} params.selectedStations - Array of selected station names
 * @param {Array} params.selectedPoints - Array of user-selected points for delta calculation
 * @param {boolean} params.isFullscreen - Whether the graph is in fullscreen mode
 * @param {boolean} params.isMobile - Whether the device is mobile
 * @returns {Object} { traces, layout, config }
 */
export const usePlotConfig = ({
  graphData,
  predictions,
  filters,
  selectedStations,
  selectedPoints,
  isFullscreen,
  isMobile
}) => {
  // Memoized trendline calculator
  const memoizedCalculateTrendline = useCallback((data, period) => {
    return calculateTrendline(data, period);
  }, []);

  // Memoized analysis calculator
  const memoizedCalculateAnalysis = useCallback((data, analysisType) => {
    return calculateAnalysis(data, analysisType);
  }, []);

  const traces = useMemo(() => {
    if (!graphData || graphData.length === 0) return [];

    const result = [];

    // Handle tidal data vs sea level data
    if (filters.dataType === 'tides') {
      // Tidal data handling
      const highTideData = graphData.filter(d => d.HighTide != null && !isNaN(d.HighTide));
      const lowTideData = graphData.filter(d => d.LowTide != null && !isNaN(d.LowTide));

      if (highTideData.length > 0) {
        result.push({
          x: highTideData.map(d => d.Date || d.Tab_DateTime),
          y: highTideData.map(d => d.HighTide),
          type: 'scattergl',
          mode: 'lines+markers',
          name: 'High Tide',
          line: { color: 'deepskyblue', width: 2 },
          marker: { size: 4 }
        });
      }

      if (lowTideData.length > 0) {
        result.push({
          x: lowTideData.map(d => d.Date || d.Tab_DateTime),
          y: lowTideData.map(d => d.LowTide),
          type: 'scattergl',
          mode: 'lines+markers',
          name: 'Low Tide',
          line: { color: 'lightcoral', width: 2 },
          marker: { size: 4 }
        });
      }
    } else {
      // Regular sea level data
      if (selectedStations.includes('All Stations')) {
        // Group by station
        const stationGroups = {};
        graphData.forEach(d => {
          if (!stationGroups[d.Station]) {
            stationGroups[d.Station] = [];
          }
          stationGroups[d.Station].push(d);
        });

        Object.entries(stationGroups).forEach(([station, data]) => {
          result.push({
            x: data.map(d => d.Tab_DateTime),
            y: data.map(d => d.Tab_Value_mDepthC1),
            type: 'scattergl',
            mode: 'lines',
            name: station,
            line: {
              width: 2,
              shape: 'spline',
              smoothing: 1.3
            }
          });
        });
      } else {
        selectedStations.forEach(station => {
          const stationData = graphData.filter(d => d.Station === station);
          if (stationData.length > 0) {
            result.push({
              x: stationData.map(d => d.Tab_DateTime),
              y: stationData.map(d => d.Tab_Value_mDepthC1),
              type: 'scattergl',
              mode: 'lines',
              name: station,
              line: {
                width: 2,
                shape: 'spline',
                smoothing: 1.3
              }
            });
          }
        });
      }

      // Add anomalies if enabled
      if (filters.showAnomalies) {
        const anomalies = graphData.filter(d => d.anomaly === -1 || d.anomaly === 1);
        if (anomalies.length > 0) {
          result.push({
            x: anomalies.map(d => d.Tab_DateTime),
            y: anomalies.map(d => d.Tab_Value_mDepthC1),
            type: 'scattergl',
            mode: 'markers',
            name: 'Anomalies',
            marker: {
              color: 'red',
              size: 10,
              symbol: 'x',
              line: { color: 'white', width: 1 }
            },
            showlegend: true
          });
        }
      }

      // Add trendlines if selected - separate for each station
      if (filters.trendline && filters.trendline !== 'none') {
        const trendlineColors = ['yellow', 'orange', 'lime', 'cyan', 'magenta'];
        let colorIndex = 0;

        if (selectedStations.includes('All Stations')) {
          // Collective trendline for all stations
          const trendline = memoizedCalculateTrendline(graphData, filters.trendline);
          if (trendline) {
            trendline.name = `Collective Trendline (${filters.trendline})`;
            result.push(trendline);
          }
        } else {
          // Individual trendlines for each selected station
          selectedStations.forEach(station => {
            const stationData = graphData.filter(d => d.Station === station);
            if (stationData.length > 1) {
              const trendline = memoizedCalculateTrendline(stationData, filters.trendline);
              if (trendline) {
                trendline.name = `${station} Trendline (${filters.trendline})`;
                trendline.line.color = trendlineColors[colorIndex % trendlineColors.length];
                colorIndex++;
                result.push(trendline);
              }
            }
          });
        }
      }

      // Add analysis if selected
      if (filters.analysisType && filters.analysisType !== 'none') {
        const analysis = memoizedCalculateAnalysis(graphData, filters.analysisType);
        if (analysis) {
          if (Array.isArray(analysis)) {
            result.push(...analysis);
          } else {
            result.push(analysis);
          }
        }
      }
    }

    // Add selected points trace for visual feedback
    if (selectedPoints && selectedPoints.length > 0) {
      result.push({
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

    // Add predictions for multiple stations
    if (predictions && Object.keys(predictions).length > 0) {
      const stationColors = ['#00ff88', '#ffaa00', '#ff6600', '#00aaff', '#ff00aa'];
      let colorIndex = 0;

      // Process each station's predictions
      Object.entries(predictions).forEach(([stationKey, stationPredictions]) => {
        if (stationKey === 'global_metadata' || !stationPredictions) return;

        const baseColor = stationColors[colorIndex % stationColors.length];
        colorIndex++;

        // KALMAN FILTER PREDICTIONS
        if (stationPredictions?.kalman && stationPredictions.kalman.length > 0) {
          const kalmanData = stationPredictions.kalman;

          // Check for nowcast
          const nowcast = kalmanData.find(p => p.type === 'nowcast');
          if (nowcast) {
            result.push({
              x: [new Date(nowcast.ds)],
              y: [nowcast.yhat],
              type: 'scattergl',
              mode: 'markers',
              name: `${stationKey} - Nowcast`,
              marker: {
                color: baseColor,
                symbol: 'star',
                size: 12,
                line: { color: 'white', width: 2 }
              },
              hovertemplate: `<b>${stationKey} Nowcast</b><br>%{x}<br>Level: %{y:.3f}m<br>Uncertainty: ` +
                (nowcast.uncertainty ? nowcast.uncertainty.toFixed(3) : '0.000') + 'm<extra></extra>'
            });
          }

          // Forecast line
          const forecastData = kalmanData.filter(p => p.type !== 'nowcast');
          if (forecastData.length > 0) {
            result.push({
              x: forecastData.map(item => new Date(item.ds)),
              y: forecastData.map(item => item.yhat),
              type: 'scatter',
              mode: 'lines',
              name: `${stationKey} - Kalman Forecast`,
              line: {
                color: baseColor,
                width: 2,
                shape: 'spline',
                smoothing: 1.3
              },
              hovertemplate: `<b>${stationKey} Kalman</b><br>%{x}<br>Level: %{y:.3f}m<extra></extra>`
            });

            // Confidence intervals (only for first station to avoid clutter)
            if (colorIndex === 1 && forecastData[0]?.yhat_lower !== undefined) {
              result.push({
                x: forecastData.map(item => new Date(item.ds)),
                y: forecastData.map(item => item.yhat_upper),
                type: 'scattergl',
                mode: 'lines',
                name: '95% CI Upper',
                line: {
                  color: `rgba(${parseInt(baseColor.slice(1, 3), 16)}, ${parseInt(baseColor.slice(3, 5), 16)}, ${parseInt(baseColor.slice(5, 7), 16)}, 0.2)`,
                  width: 0
                },
                showlegend: false,
                hoverinfo: 'skip',
                fill: 'tonexty',
                fillcolor: `rgba(${parseInt(baseColor.slice(1, 3), 16)}, ${parseInt(baseColor.slice(3, 5), 16)}, ${parseInt(baseColor.slice(5, 7), 16)}, 0.1)`
              });

              result.push({
                x: forecastData.map(item => new Date(item.ds)),
                y: forecastData.map(item => item.yhat_lower),
                type: 'scattergl',
                mode: 'lines',
                name: '95% CI Lower',
                line: {
                  color: `rgba(${parseInt(baseColor.slice(1, 3), 16)}, ${parseInt(baseColor.slice(3, 5), 16)}, ${parseInt(baseColor.slice(5, 7), 16)}, 0.2)`,
                  width: 1,
                  dash: 'dot'
                },
                showlegend: false,
                hovertemplate: `<b>${stationKey} 95% CI</b><br>%{x}<br>Lower: %{y:.3f}m<extra></extra>`
              });
            }
          }
        }

        // ENSEMBLE PREDICTIONS
        if (stationPredictions?.ensemble && stationPredictions.ensemble.length > 0) {
          result.push({
            x: stationPredictions.ensemble.map(item => new Date(item.ds)),
            y: stationPredictions.ensemble.map(item => item.yhat),
            type: 'scatter',
            mode: 'lines',
            name: `${stationKey} - Ensemble`,
            line: {
              color: baseColor,
              width: 2,
              dash: 'dash',
              shape: 'spline',
              smoothing: 1.3
            },
            hovertemplate: `<b>${stationKey} Ensemble</b><br>%{x}<br>Level: %{y:.3f}m<extra></extra>`
          });
        }

        // ARIMA PREDICTIONS
        if (stationPredictions?.arima && Array.isArray(stationPredictions.arima) && stationPredictions.arima.length > 0) {
          if (typeof stationPredictions.arima[0] === 'object' && stationPredictions.arima[0].ds) {
            result.push({
              x: stationPredictions.arima.map(item => new Date(item.ds)),
              y: stationPredictions.arima.map(item => item.yhat),
              type: 'scatter',
              mode: 'lines',
              name: `${stationKey} - ARIMA`,
              line: {
                color: baseColor,
                dash: 'dot',
                width: 2,
                shape: 'spline',
                smoothing: 1.3
              }
            });
          }
        }
      });
    }

    return result;
  }, [graphData, predictions, filters, selectedStations, selectedPoints, memoizedCalculateTrendline, memoizedCalculateAnalysis]);

  const layout = useMemo(() => ({
    title: {
      text: filters.dataType === 'tides' ? 'Tide Levels' : 'Sea Level Over Time',
      font: {
        color: 'white',
        size: isFullscreen ? 20 : (isMobile ? 14 : 16)
      }
    },
    plot_bgcolor: '#142950',
    paper_bgcolor: '#142950',
    font: { color: 'white' },

    xaxis: {
      title: 'Date/Time',
      color: 'white',
      gridcolor: '#1e3c72',
      tickfont: {
        size: isFullscreen ? 12 : (isMobile ? 9 : 10)
      }
    },
    yaxis: {
      title: filters.dataType === 'tides' ? 'Tide Level (m)' : 'Sea Level (m)',
      color: 'white',
      gridcolor: '#1e3c72',
      tickfont: {
        size: isFullscreen ? 12 : (isMobile ? 9 : 10)
      }
    },

    // Fullscreen-aware margins
    margin: isFullscreen
      ? { l: 60, r: 40, t: 60, b: 60 }
      : { t: 50, r: 20, b: 50, l: 60 },

    height: 400,
    showlegend: true,
    legend: {
      orientation: isFullscreen ? 'h' : 'v',
      y: isFullscreen ? -0.15 : 1,
      x: isFullscreen ? 0.5 : 0,
      xanchor: isFullscreen ? 'center' : 'left',
      font: {
        color: 'white',
        size: isFullscreen ? 11 : (isMobile ? 9 : 10)
      },
      bgcolor: 'rgba(20, 41, 80, 0.8)',
      bordercolor: '#2a4a8c',
      borderwidth: 1
    },

    // Mobile & fullscreen settings
    dragmode: isMobile ? 'pan' : 'zoom',
    hovermode: 'closest',

    // Mobile-optimized modebar - always horizontal
    modebar: {
      orientation: 'h',
      bgcolor: 'rgba(20, 41, 80, 0.95)',
      color: 'white',
      activecolor: '#3b82f6'
    },

    // Connection line shapes between selected points
    shapes: generateConnectionShapes(selectedPoints || [], LINE_STYLES.measurement),

    uirevision: 'constant'
  }), [filters.dataType, isFullscreen, isMobile, selectedPoints]);

  const config = useMemo(() => ({
    displayModeBar: !isMobile || isFullscreen,
    displaylogo: false,
    responsive: true,
    modeBarButtonsToRemove: isMobile && !isFullscreen ? [] : ['lasso2d', 'select2d'],
    toImageButtonOptions: {
      format: 'png',
      filename: 'sea_level_chart',
      height: isFullscreen ? 1080 : (isMobile ? 400 : 600),
      width: isFullscreen ? 1920 : (isMobile ? 800 : 1200),
      scale: 2
    }
  }), [isMobile, isFullscreen]);

  return { traces, layout, config };
};

export default usePlotConfig;
