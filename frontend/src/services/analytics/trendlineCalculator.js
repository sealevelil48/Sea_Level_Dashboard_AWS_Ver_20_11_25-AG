/**
 * Trendline and Rolling Average Calculator Service
 * Extracted from usePlotConfig.js and useChartJsConfig.js to eliminate duplication
 *
 * Contains all statistical calculation logic for:
 * - Linear regression trendlines
 * - Rolling averages (3h, 6h, 24h)
 * - Statistical analysis
 */

/**
 * Calculate linear regression trendline for sea level data
 *
 * @param {Array} data - Array of data points with Tab_DateTime and Tab_Value_mDepthC1
 * @param {string} period - Time period: '7d', '30d', '90d', '1y', 'last_decade', 'last_two_decades', 'all'
 * @returns {Object|null} Trendline data points or null
 */
export const calculateTrendline = (data, period) => {
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

  // Filter data by time period
  if (days !== null) {
    const endDate = new Date(data[data.length - 1].Tab_DateTime);
    const startDate = new Date(endDate - days * 24 * 60 * 60 * 1000);
    filteredData = data.filter(d => new Date(d.Tab_DateTime) >= startDate);
  }

  if (filteredData.length < 2) return null;

  // Perform linear regression
  const regression = linearRegression(filteredData);

  return {
    period,
    data: filteredData.map((d, i) => ({
      Tab_DateTime: d.Tab_DateTime,
      value: regression.slope * i + regression.intercept
    })),
    slope: regression.slope,
    intercept: regression.intercept,
    yearlyTrend: regression.slope * 365 * 24 // Approximate yearly trend
  };
};

/**
 * Calculate rolling average analysis for sea level data
 *
 * @param {Array} data - Array of data points
 * @param {string} analysisType - 'rolling_avg_3h', 'rolling_avg_6h', 'rolling_avg_24h', 'all'
 * @returns {Object|Array|null} Analysis data or null
 */
export const calculateRollingAverage = (data, analysisType) => {
  if (!data || data.length === 0 || analysisType === 'none') return null;

  const analyses = {
    'rolling_avg_3h': { window: 3, name: '3-Hour Avg', color: '#a78bfa' },
    'rolling_avg_6h': { window: 6, name: '6-Hour Avg', color: '#06b6d4' },
    'rolling_avg_24h': { window: 24, name: '24-Hour Avg', color: '#e879f9' },
    'all': null
  };

  // Handle 'all' case - return all rolling averages
  if (analysisType === 'all') {
    return Object.entries(analyses)
      .filter(([key]) => key !== 'all')
      .map(([key]) => calculateRollingAverage(data, key))
      .filter(Boolean);
  }

  const config = analyses[analysisType];
  if (!config) return null;

  const rollingData = computeRollingWindow(data, config.window);

  return {
    type: analysisType,
    name: config.name,
    color: config.color,
    window: config.window,
    data: data.map((d, i) => ({
      Tab_DateTime: d.Tab_DateTime,
      value: rollingData[i]
    }))
  };
};

/**
 * Perform linear regression on time series data
 * Uses simple least squares method
 *
 * @param {Array} data - Array of data points with Tab_Value_mDepthC1
 * @returns {Object} { slope, intercept, r2 }
 */
function linearRegression(data) {
  const n = data.length;
  const xValues = data.map((_, i) => i);
  const yValues = data.map(d => d.Tab_Value_mDepthC1);

  // Calculate sums
  const sumX = xValues.reduce((a, b) => a + b, 0);
  const sumY = yValues.reduce((a, b) => a + b, 0);
  const sumXY = xValues.reduce((sum, x, i) => sum + x * yValues[i], 0);
  const sumXX = xValues.reduce((sum, x) => sum + x * x, 0);

  // Calculate slope and intercept
  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;

  // Calculate R-squared
  const meanY = sumY / n;
  const ssTotal = yValues.reduce((sum, y) => sum + Math.pow(y - meanY, 2), 0);
  const ssResidual = yValues.reduce((sum, y, i) => {
    const predicted = slope * xValues[i] + intercept;
    return sum + Math.pow(y - predicted, 2);
  }, 0);
  const r2 = 1 - (ssResidual / ssTotal);

  return { slope, intercept, r2 };
}

/**
 * Compute rolling window average
 *
 * @param {Array} data - Array of data points
 * @param {number} windowSize - Window size in data points
 * @returns {Array} Array of rolling averages
 */
function computeRollingWindow(data, windowSize) {
  const result = [];

  for (let i = 0; i < data.length; i++) {
    const start = Math.max(0, i - windowSize + 1);
    const window = data.slice(start, i + 1);
    const validValues = window
      .map(d => d.Tab_Value_mDepthC1)
      .filter(v => v != null && !isNaN(v));

    const avg = validValues.length > 0
      ? validValues.reduce((sum, v) => sum + v, 0) / validValues.length
      : null;

    result.push(avg);
  }

  return result;
}

/**
 * Calculate exponential moving average (EMA)
 * More weight on recent values
 *
 * @param {Array} data - Array of data points
 * @param {number} alpha - Smoothing factor (0-1, default 0.3)
 * @returns {Array} Array of EMA values
 */
export const calculateEMA = (data, alpha = 0.3) => {
  if (!data || data.length === 0) return [];

  const result = [];
  let ema = data[0].Tab_Value_mDepthC1;

  result.push(ema);

  for (let i = 1; i < data.length; i++) {
    const value = data[i].Tab_Value_mDepthC1;
    if (value != null && !isNaN(value)) {
      ema = alpha * value + (1 - alpha) * ema;
    }
    result.push(ema);
  }

  return result;
};

/**
 * Calculate standard deviation for a dataset
 *
 * @param {Array} values - Array of numeric values
 * @returns {number} Standard deviation
 */
export const calculateStdDev = (values) => {
  if (!values || values.length === 0) return 0;

  const validValues = values.filter(v => v != null && !isNaN(v));
  if (validValues.length === 0) return 0;

  const mean = validValues.reduce((sum, v) => sum + v, 0) / validValues.length;
  const variance = validValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / validValues.length;

  return Math.sqrt(variance);
};

/**
 * Detect trend direction and strength
 *
 * @param {Array} data - Array of data points
 * @returns {Object} { direction: 'rising'|'falling'|'stable', strength: number }
 */
export const detectTrend = (data) => {
  if (!data || data.length < 10) {
    return { direction: 'unknown', strength: 0 };
  }

  const regression = linearRegression(data);
  const slopeThreshold = 0.001; // Adjust based on data scale

  let direction;
  if (Math.abs(regression.slope) < slopeThreshold) {
    direction = 'stable';
  } else if (regression.slope > 0) {
    direction = 'rising';
  } else {
    direction = 'falling';
  }

  // Strength based on R-squared (0-1 scale)
  const strength = Math.abs(regression.r2);

  return {
    direction,
    strength,
    slope: regression.slope,
    r2: regression.r2
  };
};

export default {
  calculateTrendline,
  calculateRollingAverage,
  calculateEMA,
  calculateStdDev,
  detectTrend
};
