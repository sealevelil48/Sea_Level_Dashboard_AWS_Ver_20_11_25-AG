/**
 * Delta Calculation Utility
 * Handles computation and formatting of differences between two selected points
 * Supports multiple scenarios: different stations, different times, same station/time
 */

import { safeParseDate, formatDateTime } from './dateUtils';

/**
 * Validates that a data point has the required fields
 * @param {Object} point - The data point to validate
 * @returns {Object} Validation result with isValid flag and error message
 */
export const validateDataPoint = (point) => {
  if (!point) {
    return { isValid: false, error: 'Data point is null or undefined' };
  }

  if (typeof point !== 'object') {
    return { isValid: false, error: 'Data point must be an object' };
  }

  // Check if it has a value field (either Tab_Value_mDepthC1, level, or value)
  const valueField = point.Tab_Value_mDepthC1 ?? point.level ?? point.value;
  if (valueField === null || valueField === undefined) {
    return { isValid: false, error: 'Data point missing sea level value' };
  }

  if (typeof valueField !== 'number' || isNaN(valueField)) {
    return { isValid: false, error: 'Sea level value must be a valid number' };
  }

  // Check if it has a timestamp
  const timestamp = point.Tab_DateTime || point.timestamp || point.date;
  if (!timestamp) {
    return { isValid: false, error: 'Data point missing timestamp' };
  }

  const parsedDate = safeParseDate(timestamp);
  if (!parsedDate) {
    return { isValid: false, error: 'Invalid timestamp format' };
  }

  return { isValid: true };
};

/**
 * Extracts the sea level value from a data point
 * Tries multiple field names for compatibility
 * @param {Object} point - The data point
 * @returns {number|null} The sea level value or null if not found
 */
const extractValue = (point) => {
  if (!point) return null;
  return point.Tab_Value_mDepthC1 ?? point.level ?? point.value ?? null;
};

/**
 * Extracts the station name from a data point
 * Tries multiple field names for compatibility
 * @param {Object} point - The data point
 * @returns {string|null} The station name or null if not found
 */
const extractStation = (point) => {
  if (!point) return null;
  return point.Station ?? point.station ?? point.name ?? null;
};

/**
 * Extracts the timestamp from a data point
 * Tries multiple field names for compatibility
 * @param {Object} point - The data point
 * @returns {Date|null} The parsed date or null if not found
 */
const extractTimestamp = (point) => {
  if (!point) return null;
  const timestamp = point.Tab_DateTime ?? point.timestamp ?? point.date;
  return timestamp ? safeParseDate(timestamp) : null;
};

/**
 * Determines which point has a higher value
 * @param {number} value1 - First value
 * @param {number} value2 - Second value
 * @returns {Object} Object with higher/lower information
 */
const determineHigherLower = (value1, value2) => {
  const diff = value1 - value2;
  return {
    difference: Math.abs(diff),
    isPoint1Higher: diff > 0,
    isPoint2Higher: diff < 0,
    isEqual: diff === 0
  };
};

/**
 * Calculates time difference between two dates
 * @param {Date} date1 - First date
 * @param {Date} date2 - Second date
 * @returns {Object} Time difference breakdown
 */
const calculateTimeDelta = (date1, date2) => {
  const olderDate = date1 < date2 ? date1 : date2;
  const newerDate = date1 < date2 ? date2 : date1;

  const diffMs = newerDate - olderDate;
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  let timeString = '';
  if (diffDays > 0) {
    timeString += `${diffDays}d `;
  }
  if (diffHours % 24 > 0) {
    timeString += `${diffHours % 24}h `;
  }
  if (diffMinutes % 60 > 0) {
    timeString += `${diffMinutes % 60}m`;
  }

  return {
    totalMs: diffMs,
    days: diffDays,
    hours: diffHours,
    minutes: diffMinutes,
    seconds: diffSeconds,
    formattedString: timeString.trim()
  };
};

/**
 * Main delta calculation function
 * Computes the difference between two data points
 *
 * @param {Object} point1 - First data point
 * @param {Object} point2 - Second data point
 * @returns {Object} Delta calculation result
 */
export const calculateDelta = (point1, point2) => {
  // Validate inputs
  const validation1 = validateDataPoint(point1);
  const validation2 = validateDataPoint(point2);

  if (!validation1.isValid) {
    return {
      success: false,
      error: `Point 1: ${validation1.error}`
    };
  }

  if (!validation2.isValid) {
    return {
      success: false,
      error: `Point 2: ${validation2.error}`
    };
  }

  // Extract data from points
  const value1 = extractValue(point1);
  const value2 = extractValue(point2);
  const station1 = extractStation(point1);
  const station2 = extractStation(point2);
  const timestamp1 = extractTimestamp(point1);
  const timestamp2 = extractTimestamp(point2);

  // Calculate value delta
  const { difference, isPoint1Higher, isEqual } = determineHigherLower(value1, value2);

  // Determine scenario
  const sameStation = station1 === station2;
  const sameTime = Math.abs(timestamp1 - timestamp2) < 1000; // Within 1 second
  const timeDelta = calculateTimeDelta(timestamp1, timestamp2);

  // Build result object
  const result = {
    success: true,
    point1: {
      value: Number(value1.toFixed(3)),
      station: station1,
      timestamp: timestamp1,
      formattedTime: formatDateTime(point1.Tab_DateTime || point1.timestamp || point1.date)
    },
    point2: {
      value: Number(value2.toFixed(3)),
      station: station2,
      timestamp: timestamp2,
      formattedTime: formatDateTime(point2.Tab_DateTime || point2.timestamp || point2.date)
    },
    delta: {
      valueDelta: Number(difference.toFixed(3)),
      isPoint1Higher,
      isPoint2Higher: !isPoint1Higher && !isEqual,
      isEqual,
      highestValue: Math.max(value1, value2),
      lowestValue: Math.min(value1, value2),
      percentageDifference: value1 !== 0 ? Number(((difference / Math.abs(value1)) * 100).toFixed(2)) : 0
    },
    scenario: {
      sameStation,
      sameTime,
      isDifferentStations: !sameStation,
      isDifferentTimes: !sameTime
    }
  };

  // Add time delta if times are different
  if (!sameTime) {
    result.timeDelta = {
      days: timeDelta.days,
      hours: timeDelta.hours,
      minutes: timeDelta.minutes,
      seconds: timeDelta.seconds,
      formattedString: timeDelta.formattedString
    };
  }

  return result;
};

/**
 * Formats the delta calculation result into a human-readable string
 *
 * @param {Object} deltaResult - Result from calculateDelta()
 * @returns {string} Formatted output string
 */
export const formatDeltaOutput = (deltaResult) => {
  if (!deltaResult.success) {
    return `Error: ${deltaResult.error}`;
  }

  const { point1, point2, delta, scenario, timeDelta } = deltaResult;

  let output = '';

  // Header with stations
  if (scenario.sameStation) {
    output += `Station: ${point1.station}\n`;
    output += `Time Range: ${point1.formattedTime} to ${point2.formattedTime}\n`;
  } else {
    output += `Stations: ${point1.station} → ${point2.station}\n`;
    output += `Both measured at: ${point1.formattedTime}\n`;
  }

  // Values
  output += `\nValues:\n`;
  output += `  ${point1.station}: ${point1.value.toFixed(3)}m\n`;
  output += `  ${point2.station}: ${point2.value.toFixed(3)}m\n`;

  // Delta
  output += `\nDelta: Δ${delta.valueDelta.toFixed(3)}m`;
  if (delta.isPoint1Higher) {
    output += ` (${point1.station} is higher)`;
  } else if (delta.isPoint2Higher) {
    output += ` (${point2.station} is higher)`;
  } else {
    output += ` (Equal levels)`;
  }

  output += `\nPercentage Change: ${delta.percentageDifference}%`;

  // Time information
  if (timeDelta) {
    output += `\nTime Difference: ${timeDelta.formattedString}`;
  }

  return output;
};

/**
 * Generates a compact delta string for display purposes
 *
 * @param {Object} deltaResult - Result from calculateDelta()
 * @param {Object} options - Formatting options
 * @returns {string} Compact delta string
 */
export const generateCompactDeltaString = (deltaResult, options = {}) => {
  const { includeStations = true, includeTime = true } = options;

  if (!deltaResult.success) {
    return 'Invalid comparison';
  }

  const { point1, point2, delta, scenario } = deltaResult;
  let compactString = '';

  // Compact station info
  if (includeStations && scenario.isDifferentStations) {
    compactString += `${point1.station} vs ${point2.station}: `;
  }

  // Value and delta
  compactString += `${point1.value.toFixed(3)}m → ${point2.value.toFixed(3)}m`;
  compactString += ` (Δ${delta.valueDelta.toFixed(3)}m)`;

  // Indicator
  if (!delta.isEqual) {
    compactString += delta.isPoint1Higher ? ' ↑' : ' ↓';
  }

  return compactString;
};

/**
 * Generates a JSON summary for API responses
 *
 * @param {Object} deltaResult - Result from calculateDelta()
 * @returns {Object} Summary object
 */
export const generateDeltaSummary = (deltaResult) => {
  if (!deltaResult.success) {
    return {
      success: false,
      error: deltaResult.error
    };
  }

  return {
    success: true,
    point1: {
      station: deltaResult.point1.station,
      value: deltaResult.point1.value,
      timestamp: deltaResult.point1.timestamp.toISOString()
    },
    point2: {
      station: deltaResult.point2.station,
      value: deltaResult.point2.value,
      timestamp: deltaResult.point2.timestamp.toISOString()
    },
    delta: deltaResult.delta.valueDelta,
    difference_percent: deltaResult.delta.percentageDifference,
    higher_point: deltaResult.delta.isPoint1Higher ? deltaResult.point1.station : deltaResult.point2.station,
    time_difference_minutes: deltaResult.timeDelta ? Math.floor(deltaResult.timeDelta.seconds / 60) : 0,
    same_station: deltaResult.scenario.sameStation,
    same_time: deltaResult.scenario.sameTime
  };
};

export default {
  calculateDelta,
  validateDataPoint,
  formatDeltaOutput,
  generateCompactDeltaString,
  generateDeltaSummary
};
