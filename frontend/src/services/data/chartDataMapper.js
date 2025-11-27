/**
 * Chart Data Mapper Service
 * Maps raw data to chart-specific formats (Plotly and Chart.js)
 *
 * This eliminates code duplication between usePlotConfig and useChartJsConfig
 * by providing a unified mapping interface for both chart libraries
 */

// Color schemes for different data types
const STATION_COLORS = {
  'Acre': '#00bfff',      // Cyan/Sky Blue
  'Ashdod': '#ff7f0e',    // Orange
  'Ashkelon': '#8c564b',  // Brown
  'Eilat': '#ff0000',     // Red
  'Haifa': '#9467bd',     // Purple
  'Yafo': '#2ca02c',      // Green
  'Tel-Aviv': '#d62728',  // Red
  'Hadera': '#17becf'     // Teal
};

const PREDICTION_COLORS = {
  'kalman': '#00ff88',
  'kalman_filter': '#00ff88',
  'ensemble': '#ffaa00',
  'arima': '#2ca02c',
  'prophet': '#9467bd'
};

const TRENDLINE_COLORS = ['#fbbf24', '#f97316', '#84cc16', '#06b6d4', '#e879f9'];

/**
 * Get station color with fallback
 */
const getStationColor = (station) => {
  return STATION_COLORS[station] || '#00bfff';
};

/**
 * Chart.js Data Mapper
 * Creates Chart.js dataset objects
 */
export const mapToChartJsDataset = {
  /**
   * Create main sea level trace for a station
   */
  createMainTrace: (station, data) => {
    const color = getStationColor(station);
    const sortedData = data
      .filter(d => d.Tab_Value_mDepthC1 != null && !isNaN(d.Tab_Value_mDepthC1))
      .sort((a, b) => new Date(a.Tab_DateTime) - new Date(b.Tab_DateTime))
      .map(d => ({
        x: new Date(d.Tab_DateTime),
        y: Number(d.Tab_Value_mDepthC1)
      }));

    return {
      label: station,
      data: sortedData,
      borderColor: color,
      backgroundColor: color,
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 5,
      tension: 0.4, // Smooth curves
      fill: false,
      spanGaps: false
    };
  },

  /**
   * Create anomaly points trace
   */
  createAnomalyTrace: (anomalies) => {
    return {
      label: 'Anomalies',
      data: anomalies.map(d => ({
        x: new Date(d.Tab_DateTime),
        y: d.Tab_Value_mDepthC1,
        station: d.Station
      })),
      borderColor: '#ff4444',
      backgroundColor: '#ff4444',
      pointRadius: 6,
      pointStyle: 'crossRot',
      showLine: false,
      pointHoverRadius: 8
    };
  },

  /**
   * Create tide trace (high or low)
   */
  createTideTrace: (name, data, type) => {
    const color = type === 'high' ? '#00bfff' : '#ff6b6b';
    return {
      label: name,
      data: data.map(d => ({
        x: new Date(d.Date || d.Tab_DateTime),
        y: type === 'high' ? d.HighTide : d.LowTide
      })),
      borderColor: color,
      backgroundColor: color,
      borderWidth: 2,
      pointRadius: 4,
      tension: 0.4,
      fill: false
    };
  },

  /**
   * Create prediction trace
   */
  createPredictionTrace: (station, model, data) => {
    const modelKey = model.replace('_filter', '');
    const color = PREDICTION_COLORS[modelKey] || '#00ff88';
    const dashPattern = {
      'kalman': [5, 5],
      'kalman_filter': [5, 5],
      'ensemble': [10, 5],
      'arima': [2, 2],
      'prophet': [5, 2, 2, 2]
    };

    return {
      label: `${station} - ${model.toUpperCase()}`,
      data: data.map(d => ({
        x: new Date(d.ds),
        y: d.yhat
      })),
      borderColor: color,
      backgroundColor: color,
      borderWidth: 2,
      borderDash: dashPattern[modelKey] || [5, 5],
      pointRadius: 0,
      tension: 0.4,
      fill: false
    };
  },

  /**
   * Create trendline trace
   */
  createTrendlineTrace: (name, trendlineData, period, colorIndex = 0) => {
    return {
      label: `${name} Trendline (${period})`,
      data: trendlineData.data.map(d => ({
        x: new Date(d.Tab_DateTime),
        y: d.value
      })),
      borderColor: TRENDLINE_COLORS[colorIndex % TRENDLINE_COLORS.length],
      backgroundColor: TRENDLINE_COLORS[colorIndex % TRENDLINE_COLORS.length],
      borderWidth: 2,
      borderDash: [5, 5],
      pointRadius: 0,
      tension: 0,
      fill: false
    };
  },

  /**
   * Create rolling average trace
   */
  createAnalysisTrace: (analysisData) => {
    return {
      label: analysisData.name,
      data: analysisData.data.map(d => ({
        x: new Date(d.Tab_DateTime),
        y: d.value
      })),
      borderColor: analysisData.color,
      backgroundColor: analysisData.color,
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.4,
      fill: false,
      spanGaps: true
    };
  },

  /**
   * Create selected points trace
   */
  createSelectedPointsTrace: (selectedPoints) => {
    return {
      label: 'Selected Points',
      data: selectedPoints.map(p => ({
        x: new Date(p.x || p.timestamp),
        y: p.y
      })),
      borderColor: '#FFD700',
      backgroundColor: '#FFD700',
      pointRadius: 8,
      pointStyle: 'star',
      showLine: false,
      pointHoverRadius: 10
    };
  },

  /**
   * Create connection line between selected points
   */
  createConnectionLineTrace: (selectedPoints) => {
    return {
      label: 'Connection Line',
      data: [
        {
          x: new Date(selectedPoints[0].x || selectedPoints[0].timestamp),
          y: selectedPoints[0].y
        },
        {
          x: new Date(selectedPoints[1].x || selectedPoints[1].timestamp),
          y: selectedPoints[1].y
        }
      ],
      borderColor: '#4ECDC4',
      backgroundColor: '#4ECDC4',
      borderWidth: 2,
      borderDash: [10, 5],
      pointRadius: 0,
      tension: 0,
      fill: false,
      showLine: true
    };
  }
};

/**
 * Plotly Data Mapper
 * Creates Plotly trace objects
 */
export const mapToPlotlyTrace = {
  /**
   * Create main sea level trace for a station
   */
  createMainTrace: (station, data) => {
    const color = getStationColor(station);
    const sortedData = data
      .filter(d => d.Tab_Value_mDepthC1 != null && !isNaN(d.Tab_Value_mDepthC1))
      .sort((a, b) => new Date(a.Tab_DateTime) - new Date(b.Tab_DateTime));

    return {
      x: sortedData.map(d => new Date(d.Tab_DateTime)),
      y: sortedData.map(d => d.Tab_Value_mDepthC1),
      type: 'scattergl',
      mode: 'lines',
      name: station,
      line: {
        color,
        width: 2,
        shape: 'spline',
        smoothing: 1.3
      },
      hovertemplate: `<b>${station}</b><br>%{x}<br>Level: %{y:.3f}m<extra></extra>`
    };
  },

  /**
   * Create anomaly points trace
   */
  createAnomalyTrace: (anomalies) => {
    return {
      x: anomalies.map(d => new Date(d.Tab_DateTime)),
      y: anomalies.map(d => d.Tab_Value_mDepthC1),
      type: 'scattergl',
      mode: 'markers',
      name: 'Anomalies',
      marker: {
        color: '#ff4444',
        size: 10,
        symbol: 'x',
        line: { color: 'white', width: 1 }
      },
      hovertemplate: '<b>Anomaly</b><br>%{x}<br>Level: %{y:.3f}m<extra></extra>'
    };
  },

  /**
   * Create tide trace (high or low)
   */
  createTideTrace: (name, data, type) => {
    const color = type === 'high' ? 'deepskyblue' : 'lightcoral';
    return {
      x: data.map(d => d.Date || d.Tab_DateTime),
      y: data.map(d => type === 'high' ? d.HighTide : d.LowTide),
      type: 'scattergl',
      mode: 'lines+markers',
      name,
      line: { color, width: 2 },
      marker: { size: 4 }
    };
  },

  /**
   * Create prediction trace
   */
  createPredictionTrace: (station, model, data) => {
    const modelKey = model.replace('_filter', '');
    const color = PREDICTION_COLORS[modelKey] || '#00ff88';
    const dashStyle = {
      'kalman': 'solid',
      'kalman_filter': 'solid',
      'ensemble': 'dash',
      'arima': 'dot',
      'prophet': 'dashdot'
    };

    return {
      x: data.map(d => new Date(d.ds)),
      y: data.map(d => d.yhat),
      type: 'scatter',
      mode: 'lines',
      name: `${station} - ${model.toUpperCase()}`,
      line: {
        color,
        width: 2,
        dash: dashStyle[modelKey] || 'dash',
        shape: 'spline',
        smoothing: 1.3
      },
      hovertemplate: `<b>${station} ${model}</b><br>%{x}<br>Level: %{y:.3f}m<extra></extra>`
    };
  },

  /**
   * Create trendline trace
   */
  createTrendlineTrace: (name, trendlineData, period, colorIndex = 0) => {
    return {
      x: trendlineData.data.map(d => new Date(d.Tab_DateTime)),
      y: trendlineData.data.map(d => d.value),
      type: 'scattergl',
      mode: 'lines',
      name: `${name} Trendline (${period})`,
      line: {
        color: TRENDLINE_COLORS[colorIndex % TRENDLINE_COLORS.length],
        dash: 'dash',
        width: 2
      }
    };
  },

  /**
   * Create rolling average trace
   */
  createAnalysisTrace: (analysisData) => {
    return {
      x: analysisData.data.map(d => new Date(d.Tab_DateTime)),
      y: analysisData.data.map(d => d.value),
      type: 'scattergl',
      mode: 'lines',
      name: analysisData.name,
      line: {
        color: analysisData.color,
        width: 2,
        shape: 'spline',
        smoothing: 1.3
      }
    };
  },

  /**
   * Create selected points trace
   */
  createSelectedPointsTrace: (selectedPoints) => {
    return {
      x: selectedPoints.map(p => new Date(p.x || p.timestamp)),
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
      )
    };
  },

  /**
   * Create connection line between selected points (using shapes, not trace)
   */
  createConnectionLineTrace: (selectedPoints) => {
    // For Plotly, this is handled via layout.shapes
    // Return null to indicate no trace needed
    return null;
  }
};

export default {
  mapToChartJsDataset,
  mapToPlotlyTrace
};
