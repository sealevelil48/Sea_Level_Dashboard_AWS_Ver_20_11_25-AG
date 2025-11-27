import { useMemo } from 'react';

/**
 * Calculate trendline for sea level data using linear regression
 * @param {Array} data - Array of data points with Tab_DateTime and Tab_Value_mDepthC1
 * @param {string} period - Time period for trendline calculation
 * @returns {Object|null} Chart.js dataset for trendline or null
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

  const trendlineData = xValues.map((x, i) => ({
    x: new Date(filteredData[i].Tab_DateTime),
    y: slope * x + intercept
  }));

  return {
    label: `Trendline (${period})`,
    data: trendlineData,
    borderColor: '#fbbf24', // Yellow
    backgroundColor: '#fbbf24',
    borderWidth: 2,
    borderDash: [5, 5],
    pointRadius: 0,
    tension: 0,
    fill: false,
  };
};

/**
 * Calculate rolling average analysis for sea level data
 * @param {Array} data - Array of data points
 * @param {string} analysisType - Type of analysis (rolling_avg_3h, rolling_avg_6h, rolling_avg_24h, all)
 * @returns {Array|null} Array of Chart.js datasets or null
 */
const calculateAnalysis = (data, analysisType) => {
  if (!data || data.length === 0 || analysisType === 'none') return null;

  const analyses = {
    'rolling_avg_3h': { window: 3, name: '3-Hour Avg', color: '#a78bfa' }, // Violet
    'rolling_avg_6h': { window: 6, name: '6-Hour Avg', color: '#06b6d4' }, // Cyan
    'rolling_avg_24h': { window: 24, name: '24-Hour Avg', color: '#e879f9' }, // Magenta
    'all': null
  };

  if (analysisType === 'all') {
    return Object.entries(analyses)
      .filter(([key]) => key !== 'all')
      .map(([key]) => calculateAnalysis(data, key))
      .flat()
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

  const rollingAvgData = data.map((d, i) => ({
    x: new Date(d.Tab_DateTime),
    y: rollingAvg[i]
  }));

  return [{
    label: config.name,
    data: rollingAvgData,
    borderColor: config.color,
    backgroundColor: config.color,
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.4, // Smooth curves
    fill: false,
    spanGaps: true,
  }];
};

/**
 * Custom hook to convert Plotly-style data to Chart.js format
 *
 * This hook transforms the data structure from Plotly traces to Chart.js datasets
 * while maintaining all the functionality like predictions, anomalies, trendlines, etc.
 *
 * @param {Object} params - Configuration parameters
 * @param {Array} params.graphData - Raw sea level data
 * @param {Object} params.predictions - Prediction model outputs
 * @param {Object} params.filters - Active filters
 * @param {Array} params.selectedStations - Selected station names
 * @param {Array} params.selectedPoints - User-selected points
 * @param {boolean} params.isFullscreen - Fullscreen mode flag
 * @param {boolean} params.isMobile - Mobile device flag
 * @returns {Object} Chart.js compatible data and options
 */
export const useChartJsConfig = ({
  graphData,
  predictions,
  filters,
  selectedStations,
  selectedPoints,
  isFullscreen, // eslint-disable-line no-unused-vars
  isMobile // eslint-disable-line no-unused-vars
}) => {
  const chartData = useMemo(() => {
    const datasets = [];

    if (!graphData || graphData.length === 0) {
      return { datasets: [] };
    }

    // Station colors - each station gets a unique, distinct color
    const stationColors = {
      'Acre': '#00bfff',      // Cyan/Sky Blue
      'Ashdod': '#ff7f0e',    // Orange
      'Ashkelon': '#8c564b',  // Brown
      'Eilat': '#ff0000',     // Red
      'Haifa': '#9467bd',     // Purple
      'Yafo': '#2ca02c',      // Green
      'Tel-Aviv': '#d62728',  // Red (fallback)
      'Hadera': '#17becf',    // Teal (fallback)
    };

    // Get default color for unknown stations
    const getStationColor = (station) => {
      return stationColors[station] || '#00bfff';
    };

    // Group data by station with comprehensive validation
    const stationData = {};
    graphData.forEach(point => {
      try {
        // Validate point exists
        if (!point) {
          return;
        }

        // Validate station name
        const station = point.Station;
        if (!station || typeof station !== 'string' || station.trim() === '') {
          return;
        }

        // Validate value is a valid number
        const value = point.Tab_Value_mDepthC1;
        if (value === null ||
            value === undefined ||
            typeof value !== 'number' ||
            isNaN(value)) {
          return;
        }

        // Validate timestamp exists
        const timestamp = point.Tab_DateTime;
        if (!timestamp) {
          return;
        }

        // Try to parse date with error handling
        let dateObj;
        try {
          dateObj = new Date(timestamp);
          // Check if date is valid
          if (isNaN(dateObj.getTime())) {
            console.warn('Invalid date:', timestamp);
            return;
          }
        } catch (dateError) {
          console.warn('Error parsing date:', timestamp, dateError);
          return;
        }

        // Add to station data
        if (!stationData[station]) {
          stationData[station] = [];
        }
        stationData[station].push({
          x: dateObj,
          y: Number(value)
        });
      } catch (error) {
        console.warn('Error processing data point:', error);
      }
    });

    // Create main data traces for each station
    Object.entries(stationData).forEach(([station, points]) => {
      // Filter out stations not selected
      if (selectedStations.length > 0 &&
          !selectedStations.includes('All Stations') &&
          !selectedStations.includes(station)) {
        return;
      }

      // Sort points by time
      const sortedPoints = points.sort((a, b) => a.x - b.x);

      const color = getStationColor(station);

      datasets.push({
        label: station,
        data: sortedPoints,
        borderColor: color,
        backgroundColor: color,
        borderWidth: 2,
        pointRadius: 0, // Hide dots for performance
        pointHoverRadius: 5,
        tension: 0.4, // Smooth curves (similar to Plotly spline)
        fill: false,
        spanGaps: false, // Show gaps when data is missing
      });
    });

    // Add anomalies if enabled
    if (filters.showAnomalies) {
      console.log('[useChartJsConfig] Anomaly detection enabled');
      console.log('[useChartJsConfig] Total data points:', graphData.length);

      // Check what anomaly values exist in the data
      const anomalyValues = [...new Set(graphData.map(point => point.anomaly))];
      console.log('[useChartJsConfig] Anomaly values in data:', anomalyValues);

      // Count anomalies by value
      const anomalyCounts = {};
      graphData.forEach(point => {
        const val = point.anomaly ?? 'undefined';
        anomalyCounts[val] = (anomalyCounts[val] || 0) + 1;
      });
      console.log('[useChartJsConfig] Anomaly counts:', anomalyCounts);

      const anomalyPoints = graphData
        .filter(point => point.anomaly === -1)
        .map(point => ({
          x: new Date(point.Tab_DateTime),
          y: point.Tab_Value_mDepthC1,
          station: point.Station
        }));

      console.log('[useChartJsConfig] Filtered anomaly points:', anomalyPoints.length);

      if (anomalyPoints.length > 0) {
        console.log('[useChartJsConfig] Adding anomaly dataset to chart');
        datasets.push({
          label: 'Anomalies',
          data: anomalyPoints,
          borderColor: '#ff4444',
          backgroundColor: '#ff4444',
          pointRadius: 6,
          pointStyle: 'crossRot',
          showLine: false,
          pointHoverRadius: 8,
        });
      } else {
        console.log('[useChartJsConfig] No anomaly points found with anomaly === -1');
      }
    } else {
      console.log('[useChartJsConfig] Anomaly detection disabled');
    }

    // Add prediction models
    // Note: API returns predictions in nested structure: { StationName: { kalman: [...], ensemble: [...], etc } }
    if (predictions && filters.predictionModels && Object.keys(predictions).length > 0) {
      console.log('[useChartJsConfig] Processing predictions:', {
        stationKeys: Object.keys(predictions),
        enabledModels: filters.predictionModels,
        predictionsStructure: Object.entries(predictions).map(([key, val]) => ({
          station: key,
          models: typeof val === 'object' ? Object.keys(val) : 'invalid'
        }))
      });

      // Prediction colors for different models
      const predictionColors = {
        kalman_filter: '#00bfff',  // Cyan
        ensemble: '#ff7f0e',       // Orange
        arima: '#2ca02c',          // Green
        prophet: '#9467bd'         // Purple
      };

      // Track if we've added confidence intervals (only add for first station)
      let confidenceIntervalsAdded = false;

      // Iterate through each station's predictions
      Object.entries(predictions).forEach(([stationKey, stationPredictions]) => {
        // Skip metadata or invalid entries
        if (stationKey === 'global_metadata' || !stationPredictions || typeof stationPredictions !== 'object') {
          return;
        }

        // Kalman Filter predictions
        if (filters.predictionModels.includes('kalman_filter') &&
            stationPredictions.kalman &&
            Array.isArray(stationPredictions.kalman) &&
            stationPredictions.kalman.length > 0) {
          const kalmanData = stationPredictions.kalman.map(point => ({
            x: new Date(point.ds),
            y: point.yhat
          }));

          console.log(`[useChartJsConfig] Adding Kalman Filter for ${stationKey}: ${kalmanData.length} points`);

          datasets.push({
            label: `${stationKey} - Kalman Filter`,
            data: kalmanData,
            borderColor: predictionColors.kalman_filter,
            backgroundColor: predictionColors.kalman_filter,
            borderWidth: 2,
            borderDash: [5, 5], // Dashed line for predictions
            pointRadius: 0,
            tension: 0.4,
            fill: false,
          });

          // Add confidence intervals (only for first station to avoid clutter)
          if (!confidenceIntervalsAdded &&
              stationPredictions.kalman[0] &&
              stationPredictions.kalman[0].yhat_upper !== undefined &&
              stationPredictions.kalman[0].yhat_lower !== undefined) {
            const upperBand = stationPredictions.kalman.map(point => ({
              x: new Date(point.ds),
              y: point.yhat_upper
            }));
            const lowerBand = stationPredictions.kalman.map(point => ({
              x: new Date(point.ds),
              y: point.yhat_lower
            }));

            datasets.push({
              label: `${stationKey} - Kalman 95% CI (Upper)`,
              data: upperBand,
              borderColor: 'rgba(0, 191, 255, 0.3)',
              backgroundColor: 'rgba(0, 191, 255, 0.1)',
              borderWidth: 1,
              borderDash: [2, 2],
              pointRadius: 0,
              tension: 0.4,
              fill: '+1', // Fill to next dataset
            });

            datasets.push({
              label: `${stationKey} - Kalman 95% CI (Lower)`,
              data: lowerBand,
              borderColor: 'rgba(0, 191, 255, 0.3)',
              backgroundColor: 'rgba(0, 191, 255, 0.1)',
              borderWidth: 1,
              borderDash: [2, 2],
              pointRadius: 0,
              tension: 0.4,
              fill: false,
            });

            confidenceIntervalsAdded = true;
          }
        }

        // Ensemble predictions
        if (filters.predictionModels.includes('ensemble') &&
            stationPredictions.ensemble &&
            Array.isArray(stationPredictions.ensemble) &&
            stationPredictions.ensemble.length > 0) {
          const ensembleData = stationPredictions.ensemble.map(point => ({
            x: new Date(point.ds),
            y: point.yhat
          }));

          console.log(`[useChartJsConfig] Adding Ensemble for ${stationKey}: ${ensembleData.length} points`);

          datasets.push({
            label: `${stationKey} - Ensemble`,
            data: ensembleData,
            borderColor: predictionColors.ensemble,
            backgroundColor: predictionColors.ensemble,
            borderWidth: 2,
            borderDash: [10, 5], // Different dash pattern
            pointRadius: 0,
            tension: 0.4,
            fill: false,
          });
        }

        // ARIMA predictions
        if (filters.predictionModels.includes('arima') &&
            stationPredictions.arima &&
            Array.isArray(stationPredictions.arima) &&
            stationPredictions.arima.length > 0) {
          const arimaData = stationPredictions.arima.map(point => ({
            x: new Date(point.ds),
            y: point.yhat
          }));

          console.log(`[useChartJsConfig] Adding ARIMA for ${stationKey}: ${arimaData.length} points`);

          datasets.push({
            label: `${stationKey} - ARIMA`,
            data: arimaData,
            borderColor: predictionColors.arima,
            backgroundColor: predictionColors.arima,
            borderWidth: 2,
            borderDash: [2, 2], // Dotted line
            pointRadius: 0,
            tension: 0.4,
            fill: false,
          });
        }

        // Prophet predictions
        if (filters.predictionModels.includes('prophet') &&
            stationPredictions.prophet &&
            Array.isArray(stationPredictions.prophet) &&
            stationPredictions.prophet.length > 0) {
          const prophetData = stationPredictions.prophet.map(point => ({
            x: new Date(point.ds),
            y: point.yhat
          }));

          console.log(`[useChartJsConfig] Adding Prophet for ${stationKey}: ${prophetData.length} points`);

          datasets.push({
            label: `${stationKey} - Prophet`,
            data: prophetData,
            borderColor: predictionColors.prophet,
            backgroundColor: predictionColors.prophet,
            borderWidth: 2,
            borderDash: [5, 2, 2, 2], // Dash-dot pattern
            pointRadius: 0,
            tension: 0.4,
            fill: false,
          });
        }
      });
    }

    // Add trendlines
    if (filters.trendline && filters.trendline !== 'none' && graphData.length > 0) {
      const trendlineDataset = calculateTrendline(graphData, filters.trendline);
      if (trendlineDataset) {
        datasets.push(trendlineDataset);
      }
    }

    // Add rolling averages
    if (filters.analysisType && filters.analysisType !== 'none' && graphData.length > 0) {
      const analysisDatasets = calculateAnalysis(graphData, filters.analysisType);
      if (analysisDatasets && Array.isArray(analysisDatasets)) {
        datasets.push(...analysisDatasets);
      }
    }

    // Add selected points highlight
    if (selectedPoints && selectedPoints.length > 0) {
      const selectedData = selectedPoints.map(point => ({
        x: new Date(point.x),
        y: point.y
      }));

      datasets.push({
        label: 'Selected Points',
        data: selectedData,
        borderColor: '#FFD700',
        backgroundColor: '#FFD700',
        pointRadius: 8,
        pointStyle: 'star',
        showLine: false,
        pointHoverRadius: 10,
      });

      // Add connection line between exactly 2 selected points
      // Matching the old Plotly implementation from lineDrawingUtils.js
      if (selectedPoints.length === 2) {
        const connectionLineData = [
          {
            x: new Date(selectedPoints[0].x),
            y: selectedPoints[0].y
          },
          {
            x: new Date(selectedPoints[1].x),
            y: selectedPoints[1].y
          }
        ];

        datasets.push({
          label: 'Connection Line',
          data: connectionLineData,
          borderColor: '#4ECDC4',      // Teal color (matching LINE_STYLES.measurement)
          backgroundColor: '#4ECDC4',
          borderWidth: 2,
          borderDash: [10, 5],         // Dash-dot pattern (matching LINE_STYLES.measurement)
          pointRadius: 0,              // No points, just the line
          tension: 0,                  // Straight line
          fill: false,
          showLine: true,              // Show the line
          spanGaps: false,
        });
      }
    }

    return { datasets };
  }, [graphData, predictions, filters, selectedStations, selectedPoints]);

  return chartData;
};
