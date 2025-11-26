/**
 * Unified Chart Configuration Hook
 * Replaces duplicate logic in usePlotConfig.js and useChartJsConfig.js
 *
 * This hook consolidates all chart-related configuration and data transformation
 * into a single, maintainable module that works with both Plotly and Chart.js
 */

import { useMemo } from 'react';
import { calculateTrendline, calculateRollingAverage } from '../../services/analytics/trendlineCalculator';
import { mapToChartJsDataset, mapToPlotlyTrace } from '../../services/data/chartDataMapper';
import { generateConnectionShapes } from '../../utils/lineDrawingUtils';

/**
 * Unified chart configuration hook
 *
 * @param {Object} params
 * @param {Array} params.graphData - Raw sea level data points
 * @param {Object} params.predictions - Prediction data by station and model
 * @param {Object} params.filters - Active filters (dataType, trendline, analysisType, etc.)
 * @param {Array} params.selectedStations - Selected station names
 * @param {Array} params.selectedPoints - User-selected points for delta calculation
 * @param {string} params.chartType - 'plotly' or 'chartjs'
 * @param {boolean} params.isFullscreen - Fullscreen mode flag
 * @param {boolean} params.isMobile - Mobile device flag
 * @returns {Object} Chart configuration { data, layout, config }
 */
export const useChartConfig = ({
  graphData,
  predictions,
  filters,
  selectedStations,
  selectedPoints,
  chartType = 'chartjs', // Default to Chart.js
  isFullscreen,
  isMobile
}) => {
  // Memoized data transformation
  const chartData = useMemo(() => {
    if (!graphData || graphData.length === 0) {
      return chartType === 'chartjs' ? { datasets: [] } : [];
    }

    const mapper = chartType === 'chartjs' ? mapToChartJsDataset : mapToPlotlyTrace;

    // Build base datasets/traces
    const result = buildBaseData(graphData, filters, selectedStations, mapper);

    // Add predictions
    if (predictions && Object.keys(predictions).length > 0) {
      addPredictions(result, predictions, filters, mapper);
    }

    // Add trendlines
    if (filters.trendline && filters.trendline !== 'none') {
      addTrendlines(result, graphData, filters, selectedStations, mapper);
    }

    // Add rolling averages
    if (filters.analysisType && filters.analysisType !== 'none') {
      addRollingAverages(result, graphData, filters, mapper);
    }

    // Add selected points
    if (selectedPoints && selectedPoints.length > 0) {
      addSelectedPoints(result, selectedPoints, mapper);
    }

    return chartType === 'chartjs' ? { datasets: result } : result;
  }, [graphData, predictions, filters, selectedStations, selectedPoints, chartType]);

  // Memoized layout configuration
  const layout = useMemo(() => {
    return buildLayout(filters, isFullscreen, isMobile, selectedPoints, chartType);
  }, [filters, isFullscreen, isMobile, selectedPoints, chartType]);

  // Memoized configuration
  const config = useMemo(() => {
    return buildConfig(filters, isFullscreen, isMobile, chartType);
  }, [filters, isFullscreen, isMobile, chartType]);

  return chartType === 'chartjs'
    ? { data: chartData, options: layout }
    : { data: chartData, layout, config };
};

/**
 * Build base data from graphData
 */
function buildBaseData(graphData, filters, selectedStations, mapper) {
  const result = [];

  if (filters.dataType === 'tides') {
    return buildTideData(graphData, mapper);
  }

  // Group by station
  const stationGroups = groupByStation(graphData);

  // Filter by selected stations
  const stations = selectedStations.includes('All Stations')
    ? Object.keys(stationGroups)
    : selectedStations.filter(s => s !== 'All Stations');

  // Create trace/dataset for each station
  stations.forEach(station => {
    const stationData = stationGroups[station];
    if (stationData && stationData.length > 0) {
      result.push(mapper.createMainTrace(station, stationData));
    }
  });

  // Add anomalies if enabled
  if (filters.showAnomalies) {
    const anomalies = graphData.filter(d => d.anomaly === -1);
    if (anomalies.length > 0) {
      result.push(mapper.createAnomalyTrace(anomalies));
    }
  }

  return result;
}

/**
 * Build tide-specific data
 */
function buildTideData(graphData, mapper) {
  const result = [];
  const highTideData = graphData.filter(d => d.HighTide != null && !isNaN(d.HighTide));
  const lowTideData = graphData.filter(d => d.LowTide != null && !isNaN(d.LowTide));

  if (highTideData.length > 0) {
    result.push(mapper.createTideTrace('High Tide', highTideData, 'high'));
  }

  if (lowTideData.length > 0) {
    result.push(mapper.createTideTrace('Low Tide', lowTideData, 'low'));
  }

  return result;
}

/**
 * Add prediction traces
 */
function addPredictions(result, predictions, filters, mapper) {
  const enabledModels = filters.predictionModels || [];

  Object.entries(predictions).forEach(([stationKey, stationPredictions]) => {
    if (stationKey === 'global_metadata' || !stationPredictions) return;

    enabledModels.forEach(model => {
      const modelData = stationPredictions[model] || stationPredictions[model.replace('_filter', '')];
      if (modelData && Array.isArray(modelData) && modelData.length > 0) {
        result.push(mapper.createPredictionTrace(stationKey, model, modelData));
      }
    });
  });
}

/**
 * Add trendline traces
 */
function addTrendlines(result, graphData, filters, selectedStations, mapper) {
  if (selectedStations.includes('All Stations')) {
    // Collective trendline
    const trendlineData = calculateTrendline(graphData, filters.trendline);
    if (trendlineData) {
      result.push(mapper.createTrendlineTrace('Collective', trendlineData, filters.trendline));
    }
  } else {
    // Individual trendlines per station
    const stationGroups = groupByStation(graphData);
    selectedStations.forEach((station, index) => {
      const stationData = stationGroups[station];
      if (stationData && stationData.length > 1) {
        const trendlineData = calculateTrendline(stationData, filters.trendline);
        if (trendlineData) {
          result.push(mapper.createTrendlineTrace(station, trendlineData, filters.trendline, index));
        }
      }
    });
  }
}

/**
 * Add rolling average traces
 */
function addRollingAverages(result, graphData, filters, mapper) {
  const analysisData = calculateRollingAverage(graphData, filters.analysisType);

  if (Array.isArray(analysisData)) {
    analysisData.forEach(analysis => {
      if (analysis) {
        result.push(mapper.createAnalysisTrace(analysis));
      }
    });
  } else if (analysisData) {
    result.push(mapper.createAnalysisTrace(analysisData));
  }
}

/**
 * Add selected points trace
 */
function addSelectedPoints(result, selectedPoints, mapper) {
  result.push(mapper.createSelectedPointsTrace(selectedPoints));

  // Add connection line for exactly 2 points
  if (selectedPoints.length === 2) {
    result.push(mapper.createConnectionLineTrace(selectedPoints));
  }
}

/**
 * Build layout configuration
 */
function buildLayout(filters, isFullscreen, isMobile, selectedPoints, chartType) {
  const baseLayout = {
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
      tickfont: { size: isFullscreen ? 12 : (isMobile ? 9 : 10) }
    },
    yaxis: {
      title: filters.dataType === 'tides' ? 'Tide Level (m)' : 'Sea Level (m)',
      color: 'white',
      gridcolor: '#1e3c72',
      tickfont: { size: isFullscreen ? 12 : (isMobile ? 9 : 10) }
    },
    margin: isFullscreen
      ? { l: 60, r: 40, t: 60, b: 60 }
      : { t: 50, r: 20, b: 50, l: 60 },
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
    dragmode: isMobile ? 'pan' : 'zoom',
    hovermode: 'closest'
  };

  // Add connection shapes for Plotly
  if (chartType === 'plotly' && selectedPoints && selectedPoints.length === 2) {
    baseLayout.shapes = generateConnectionShapes(selectedPoints);
  }

  return chartType === 'chartjs'
    ? convertToChartJsOptions(baseLayout, isMobile)
    : baseLayout;
}

/**
 * Convert Plotly layout to Chart.js options
 */
function convertToChartJsOptions(layout, isMobile) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        type: 'time',
        time: {
          displayFormats: {
            hour: isMobile ? 'HH:mm' : 'MMM D, HH:mm',
            day: 'MMM D',
            month: 'MMM YYYY'
          }
        },
        title: {
          display: !isMobile,
          text: layout.xaxis.title,
          color: layout.xaxis.color
        },
        grid: {
          color: layout.xaxis.gridcolor
        },
        ticks: {
          color: layout.xaxis.color,
          font: layout.xaxis.tickfont
        }
      },
      y: {
        title: {
          display: true,
          text: layout.yaxis.title,
          color: layout.yaxis.color
        },
        grid: {
          color: layout.yaxis.gridcolor
        },
        ticks: {
          color: layout.yaxis.color,
          font: layout.yaxis.tickfont
        }
      }
    },
    plugins: {
      legend: {
        display: true,
        position: layout.legend.orientation === 'h' ? 'bottom' : 'right',
        labels: {
          color: layout.legend.font.color,
          font: { size: layout.legend.font.size },
          boxWidth: 20,
          padding: 10
        }
      },
      tooltip: {
        mode: 'nearest',
        intersect: false,
        backgroundColor: 'rgba(20, 41, 80, 0.95)',
        titleColor: '#fff',
        bodyColor: '#fff',
        borderColor: '#2a4a8c',
        borderWidth: 1
      }
    }
  };
}

/**
 * Build config object
 */
function buildConfig(filters, isFullscreen, isMobile, chartType) {
  if (chartType === 'chartjs') {
    return {}; // Chart.js doesn't use separate config
  }

  return {
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
  };
}

/**
 * Group data by station
 */
function groupByStation(graphData) {
  const groups = {};
  graphData.forEach(point => {
    const station = point.Station;
    if (!groups[station]) {
      groups[station] = [];
    }
    groups[station].push(point);
  });
  return groups;
}

export default useChartConfig;
