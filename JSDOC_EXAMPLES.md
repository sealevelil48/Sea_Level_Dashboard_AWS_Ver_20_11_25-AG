# JSDoc Documentation Examples

This document provides JSDoc examples for key JavaScript functions in the Sea Level Dashboard frontend application.

## Table of Contents

- [API Service](#api-service)
- [Custom Hooks](#custom-hooks)
- [Utility Functions](#utility-functions)
- [Component Examples](#component-examples)

---

## API Service

### apiService.js

```javascript
/**
 * Custom error class for API-related errors
 * @class ApiError
 * @extends Error
 */
class ApiError extends Error {
  /**
   * Create an ApiError
   * @param {number} status - HTTP status code
   * @param {string} statusText - HTTP status text
   * @param {Object|null} data - Additional error data from the API
   */
  constructor(status, statusText, data = null) {
    super(`HTTP ${status}: ${statusText}`);
    this.status = status;
    this.statusText = statusText;
    this.data = data;
    this.name = 'ApiError';
  }
}

/**
 * API Service for managing HTTP requests to the backend
 * Provides caching, retry logic, and request management
 * @class ApiService
 */
class ApiService {
  /**
   * Initialize API Service
   * @param {string} [baseURL] - Base URL for API requests. Defaults to environment variable or localhost
   */
  constructor(baseURL = process.env.REACT_APP_API_URL || 'http://localhost:30886') {
    this.baseURL = baseURL;
    this.timeout = 60000; // 60 seconds
    this.activeRequests = new Map();
    this.cache = new Map();
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
    this.retryAttempts = 2;
    this.retryDelay = 2000;
  }

  /**
   * Generate a cache key for request caching
   * @param {string} endpoint - API endpoint
   * @param {Object} [params={}] - Request parameters
   * @returns {string} Cache key
   */
  getCacheKey(endpoint, params = {}) {
    return `${endpoint}_${JSON.stringify(params)}`;
  }

  /**
   * Retrieve data from cache if available and not expired
   * @param {string} key - Cache key
   * @returns {*|null} Cached data or null if expired/not found
   */
  getFromCache(key) {
    const cached = this.cache.get(key);
    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
      return cached.data;
    }
    this.cache.delete(key);
    return null;
  }

  /**
   * Store data in cache with timestamp
   * @param {string} key - Cache key
   * @param {*} data - Data to cache
   */
  setCache(key, data) {
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
    // Cleanup old cache entries
    if (this.cache.size > 100) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }
  }

  /**
   * Make an HTTP request with retry logic and caching
   * @param {string} endpoint - API endpoint (e.g., '/api/stations')
   * @param {Object} [options={}] - Fetch options
   * @param {string} [options.method='GET'] - HTTP method
   * @param {Object} [options.headers] - HTTP headers
   * @param {Object} [options.params] - Query parameters (for cache key)
   * @returns {Promise<*>} Response data
   * @throws {ApiError} When request fails after retries
   * @throws {Error} When request is cancelled
   * @example
   * const data = await apiService.request('/api/stations');
   */
  async request(endpoint, options = {}) {
    // Implementation details...
  }

  /**
   * Fetch all available monitoring stations
   * @returns {Promise<Object>} Object containing stations array and database status
   * @returns {Array<string>} return.stations - Array of station names
   * @returns {boolean} return.database_available - Database availability status
   * @example
   * const { stations, database_available } = await apiService.getStations();
   * // stations: ['Acre', 'Yafo', 'Ashkelon', 'Eilat']
   */
  async getStations() {
    try {
      const data = await this.request('/api/stations');
      return {
        stations: Array.isArray(data.stations) ? data.stations : [],
        database_available: data.database_available || false
      };
    } catch (error) {
      console.error('Error fetching stations:', error);
      return { stations: [], database_available: false };
    }
  }

  /**
   * Fetch historical sea level data for a station
   * @param {Object} params - Query parameters
   * @param {string} params.station - Station name or 'All Stations'
   * @param {string} params.start_date - Start date in YYYY-MM-DD format
   * @param {string} params.end_date - End date in YYYY-MM-DD format
   * @param {string} [params.data_source='default'] - Data source type
   * @param {boolean} [params.show_anomalies=false] - Include anomaly markers
   * @param {boolean} [params.include_outliers=false] - Include outlier data
   * @param {number} [params.limit=15000] - Maximum number of records
   * @returns {Promise<Array<Object>>} Array of data records
   * @example
   * const data = await apiService.getData({
   *   station: 'Acre',
   *   start_date: '2025-01-01',
   *   end_date: '2025-01-31',
   *   show_anomalies: true
   * });
   */
  async getData(params) {
    // Implementation details...
  }

  /**
   * Fetch data for multiple stations in a single batch request
   * @param {Array<string>|string} stations - Array of station names or comma-separated string
   * @param {Object} params - Query parameters (same as getData)
   * @returns {Promise<Array<Object>>} Combined array of data records for all stations
   * @example
   * const data = await apiService.getDataBatch(
   *   ['Acre', 'Yafo', 'Eilat'],
   *   { start_date: '2025-01-01', end_date: '2025-01-31' }
   * );
   */
  async getDataBatch(stations, params) {
    // Implementation details...
  }

  /**
   * Fetch sea level predictions for one or more stations
   * @param {Object} params - Prediction parameters
   * @param {string} params.stations - Station name(s), comma-separated
   * @param {string} [params.model='kalman'] - Prediction model ('kalman' or 'prophet')
   * @param {number} [params.steps=240] - Number of forecast steps (6-minute intervals)
   * @returns {Promise<Object>} Prediction results by station
   * @example
   * const predictions = await apiService.getPredictions({
   *   stations: 'Acre,Yafo',
   *   model: 'kalman',
   *   steps: 144 // 24 hours (144 * 6 minutes)
   * });
   */
  async getPredictions(params) {
    // Implementation details...
  }

  /**
   * Fetch anomalies/outliers detected in sea level data
   * @param {Object} params - Query parameters
   * @param {string} [params.station='All Stations'] - Station name
   * @param {string} params.start_date - Start date
   * @param {string} params.end_date - End date
   * @returns {Promise<Object>} Outlier detection results
   * @returns {Array<Object>} return.outliers - Array of detected outliers
   * @returns {number} return.total_records - Total records analyzed
   * @returns {number} return.outliers_detected - Number of outliers found
   * @returns {number} return.outlier_percentage - Percentage of outliers
   * @example
   * const { outliers, outlier_percentage } = await apiService.getOutliers({
   *   station: 'Acre',
   *   start_date: '2025-01-01',
   *   end_date: '2025-01-31'
   * });
   */
  async getOutliers(params) {
    // Implementation details...
  }

  /**
   * Fetch optimized outliers using SQL-based Southern Baseline Rules
   * Significantly faster than the standard outliers endpoint (10-50x speedup)
   * @param {Object} params - Query parameters
   * @param {string} [params.station='All Stations'] - Station name
   * @param {string} params.start_date - Start date
   * @param {string} params.end_date - End date
   * @param {boolean} [params.use_cache=true] - Use materialized view cache
   * @returns {Promise<Object>} Optimized outlier detection results with performance metrics
   * @example
   * const { outliers, performance } = await apiService.getOutliersOptimized({
   *   station: 'Acre',
   *   start_date: '2025-01-01',
   *   end_date: '2025-01-07',
   *   use_cache: true
   * });
   * console.log(`Query completed in ${performance.query_time_seconds}s`);
   */
  async getOutliersOptimized(params) {
    // Implementation details...
  }

  /**
   * Cancel all active API requests
   * Useful when component unmounts or when initiating a new data fetch
   * @example
   * componentWillUnmount() {
   *   apiService.cancelAllRequests();
   * }
   */
  cancelAllRequests() {
    this.activeRequests.forEach(controller => controller.abort());
    this.activeRequests.clear();
  }

  /**
   * Clear all cached data
   * @example
   * // Clear cache after user logout or data refresh
   * apiService.clearCache();
   */
  clearCache() {
    this.cache.clear();
  }
}
```

---

## Custom Hooks

### useStations.js

```javascript
/**
 * Custom hook for managing station selection and data
 * @hook
 * @returns {Object} Station state and handlers
 * @returns {Array<string>} return.stations - Available stations
 * @returns {Array<string>} return.selectedStations - Currently selected stations
 * @returns {Function} return.setSelectedStations - Setter for selected stations
 * @returns {boolean} return.stationsFetched - Whether stations have been loaded
 * @returns {boolean} return.loading - Loading state
 * @returns {Function} return.handleStationChange - Handler for station selection
 * @returns {Function} return.stationsToFetch - Get stations to fetch data for (excludes 'All Stations')
 *
 * @example
 * function Dashboard() {
 *   const {
 *     stations,
 *     selectedStations,
 *     handleStationChange,
 *     stationsToFetch
 *   } = useStations();
 *
 *   return (
 *     <select onChange={(e) => handleStationChange(e.target.value)}>
 *       {stations.map(station => (
 *         <option key={station} value={station}>{station}</option>
 *       ))}
 *     </select>
 *   );
 * }
 */
export const useStations = () => {
  // Implementation details...
};
```

### useFilters.js

```javascript
/**
 * Custom hook for managing dashboard filter state
 * Handles date ranges, data types, analysis options, and prediction settings
 *
 * @hook
 * @returns {Object} Filter state and handlers
 * @returns {Object} return.filters - Current filter values (Date objects)
 * @returns {Object} return.filterValues - Formatted filter values for API (strings)
 * @returns {Function} return.setFilters - Set all filters at once
 * @returns {Function} return.updateFilter - Update a single filter
 * @returns {Function} return.updateDateRange - Update start and end dates
 * @returns {Function} return.toggleModel - Toggle a prediction model on/off
 * @returns {Function} return.resetFilters - Reset all filters to defaults
 *
 * @example
 * function FilterPanel() {
 *   const {
 *     filters,
 *     filterValues,
 *     updateFilter,
 *     updateDateRange,
 *     toggleModel
 *   } = useFilters();
 *
 *   return (
 *     <div>
 *       <DatePicker
 *         startDate={filters.startDate}
 *         endDate={filters.endDate}
 *         onChange={updateDateRange}
 *       />
 *       <Checkbox
 *         checked={filters.showAnomalies}
 *         onChange={() => updateFilter('showAnomalies', !filters.showAnomalies)}
 *       />
 *     </div>
 *   );
 * }
 */
export const useFilters = () => {
  // Implementation details...
};
```

### useFavorites.js

```javascript
/**
 * Custom hook for managing user favorite stations
 * Persists favorites in localStorage
 *
 * @hook
 * @returns {Object} Favorites state and handlers
 * @returns {Array<string>} return.favorites - Array of favorite station names
 * @returns {Function} return.addFavorite - Add a station to favorites
 * @returns {Function} return.removeFavorite - Remove a station from favorites
 * @returns {Function} return.isFavorite - Check if a station is favorited
 * @returns {Function} return.toggleFavorite - Toggle favorite status
 *
 * @example
 * function StationCard({ station }) {
 *   const { isFavorite, toggleFavorite } = useFavorites();
 *
 *   return (
 *     <div>
 *       <h3>{station}</h3>
 *       <button onClick={() => toggleFavorite(station)}>
 *         {isFavorite(station) ? '★' : '☆'}
 *       </button>
 *     </div>
 *   );
 * }
 */
export const useFavorites = () => {
  // Implementation details...
};
```

### useChartJsConfig.js

```javascript
/**
 * Custom hook for generating Chart.js configuration
 * Provides consistent charting options across the application
 *
 * @hook
 * @param {Object} options - Chart configuration options
 * @param {boolean} [options.showLegend=true] - Show chart legend
 * @param {boolean} [options.enableZoom=true] - Enable zoom/pan plugin
 * @param {boolean} [options.showGrid=true] - Show grid lines
 * @param {string} [options.xAxisType='time'] - X-axis type ('time', 'linear', 'category')
 * @param {Function} [options.onClickPoint] - Click handler for data points
 * @returns {Object} Chart.js configuration object
 *
 * @example
 * function SeaLevelChart({ data }) {
 *   const chartConfig = useChartJsConfig({
 *     showLegend: true,
 *     enableZoom: true,
 *     onClickPoint: (point) => console.log('Clicked:', point)
 *   });
 *
 *   return <Line data={data} options={chartConfig} />;
 * }
 */
export const useChartJsConfig = (options) => {
  // Implementation details...
};
```

---

## Utility Functions

### formatters.js

```javascript
/**
 * Format a number as meters with specified decimal places
 * @param {number} value - Value in meters
 * @param {number} [decimals=3] - Number of decimal places
 * @returns {string} Formatted string with 'm' suffix
 * @example
 * formatMeters(1.23456); // "1.235m"
 * formatMeters(1.23456, 2); // "1.23m"
 */
export const formatMeters = (value, decimals = 3) => {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  return `${Number(value).toFixed(decimals)}m`;
};

/**
 * Format a date object to YYYY-MM-DD string
 * @param {Date} date - Date object to format
 * @returns {string} Formatted date string
 * @example
 * formatDate(new Date('2025-01-15T10:30:00')); // "2025-01-15"
 */
export const formatDate = (date) => {
  if (!(date instanceof Date) || isNaN(date)) {
    return '';
  }
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

/**
 * Format a date object to readable datetime string
 * @param {Date|string} date - Date object or ISO string
 * @param {boolean} [includeSeconds=false] - Include seconds in output
 * @returns {string} Formatted datetime string
 * @example
 * formatDateTime(new Date('2025-01-15T10:30:45'));
 * // "2025-01-15 10:30"
 *
 * formatDateTime(new Date('2025-01-15T10:30:45'), true);
 * // "2025-01-15 10:30:45"
 */
export const formatDateTime = (date, includeSeconds = false) => {
  if (!date) return 'N/A';
  const d = date instanceof Date ? date : new Date(date);
  if (isNaN(d)) return 'Invalid Date';

  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  const seconds = String(d.getSeconds()).padStart(2, '0');

  let result = `${year}-${month}-${day} ${hours}:${minutes}`;
  if (includeSeconds) {
    result += `:${seconds}`;
  }
  return result;
};

/**
 * Calculate the difference between two values and format with sign
 * @param {number} current - Current value
 * @param {number} previous - Previous value
 * @param {number} [decimals=3] - Decimal places
 * @returns {string} Formatted delta with + or - sign
 * @example
 * formatDelta(1.5, 1.2); // "+0.300m"
 * formatDelta(1.2, 1.5); // "-0.300m"
 */
export const formatDelta = (current, previous, decimals = 3) => {
  if (current === null || previous === null ||
      current === undefined || previous === undefined ||
      isNaN(current) || isNaN(previous)) {
    return 'N/A';
  }
  const delta = current - previous;
  const sign = delta >= 0 ? '+' : '';
  return `${sign}${delta.toFixed(decimals)}m`;
};
```

### validators.js

```javascript
/**
 * Validate a date string in YYYY-MM-DD format
 * @param {string} dateString - Date string to validate
 * @returns {boolean} True if valid, false otherwise
 * @example
 * validateDateFormat('2025-01-15'); // true
 * validateDateFormat('15/01/2025'); // false
 * validateDateFormat('2025-13-01'); // false (invalid month)
 */
export const validateDateFormat = (dateString) => {
  if (typeof dateString !== 'string') return false;
  const regex = /^\d{4}-\d{2}-\d{2}$/;
  if (!regex.test(dateString)) return false;

  const date = new Date(dateString);
  return !isNaN(date) && date.toISOString().slice(0, 10) === dateString;
};

/**
 * Validate a date range
 * @param {Date|string} startDate - Start date
 * @param {Date|string} endDate - End date
 * @param {number} [maxDays=365] - Maximum allowed range in days
 * @returns {Object} Validation result
 * @returns {boolean} return.valid - Whether the range is valid
 * @returns {string} [return.error] - Error message if invalid
 * @example
 * const result = validateDateRange('2025-01-01', '2025-01-31');
 * if (!result.valid) {
 *   console.error(result.error);
 * }
 */
export const validateDateRange = (startDate, endDate, maxDays = 365) => {
  const start = new Date(startDate);
  const end = new Date(endDate);

  if (isNaN(start) || isNaN(end)) {
    return { valid: false, error: 'Invalid date format' };
  }

  if (start > end) {
    return { valid: false, error: 'Start date must be before end date' };
  }

  const daysDiff = (end - start) / (1000 * 60 * 60 * 24);
  if (daysDiff > maxDays) {
    return {
      valid: false,
      error: `Date range exceeds maximum of ${maxDays} days`
    };
  }

  return { valid: true };
};
```

### dataProcessing.js

```javascript
/**
 * Group data points by station
 * @param {Array<Object>} data - Array of data records
 * @returns {Object} Data grouped by station name
 * @example
 * const grouped = groupByStation([
 *   { Station: 'Acre', Tab_Value: 1.2 },
 *   { Station: 'Yafo', Tab_Value: 1.3 },
 *   { Station: 'Acre', Tab_Value: 1.4 }
 * ]);
 * // { Acre: [...], Yafo: [...] }
 */
export const groupByStation = (data) => {
  return data.reduce((acc, record) => {
    const station = record.Station || 'Unknown';
    if (!acc[station]) {
      acc[station] = [];
    }
    acc[station].push(record);
    return acc;
  }, {});
};

/**
 * Calculate rolling average for a time series
 * @param {Array<Object>} data - Time series data
 * @param {string} valueField - Field name containing values
 * @param {number} windowSize - Number of points in moving window
 * @returns {Array<number>} Array of rolling averages
 * @example
 * const data = [
 *   { Tab_Value: 1.0 },
 *   { Tab_Value: 1.2 },
 *   { Tab_Value: 1.1 },
 *   { Tab_Value: 1.3 }
 * ];
 * calculateRollingAverage(data, 'Tab_Value', 2);
 * // [null, 1.1, 1.15, 1.2]
 */
export const calculateRollingAverage = (data, valueField, windowSize) => {
  if (!data || data.length === 0) return [];

  const result = [];
  for (let i = 0; i < data.length; i++) {
    if (i < windowSize - 1) {
      result.push(null);
    } else {
      let sum = 0;
      for (let j = 0; j < windowSize; j++) {
        sum += parseFloat(data[i - j][valueField] || 0);
      }
      result.push(sum / windowSize);
    }
  }
  return result;
};

/**
 * Export data to Excel format
 * @param {Array<Object>} data - Data to export
 * @param {string} filename - Name for the downloaded file
 * @param {Array<string>} [columns] - Column names to include (all if not specified)
 * @example
 * exportToExcel(
 *   seaLevelData,
 *   'sea_level_data_2025_01.xlsx',
 *   ['Station', 'Tab_DateTime', 'Tab_Value', 'Tab_Temp']
 * );
 */
export const exportToExcel = (data, filename, columns = null) => {
  // Implementation uses xlsx library
  const XLSX = require('xlsx');

  // Filter columns if specified
  let exportData = data;
  if (columns && columns.length > 0) {
    exportData = data.map(row => {
      const filtered = {};
      columns.forEach(col => {
        if (row.hasOwnProperty(col)) {
          filtered[col] = row[col];
        }
      });
      return filtered;
    });
  }

  const worksheet = XLSX.utils.json_to_sheet(exportData);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Data');
  XLSX.writeFile(workbook, filename);
};
```

---

## Component Examples

### Dashboard Component

```javascript
/**
 * Main Dashboard component
 * Manages overall application state and coordinates sub-components
 *
 * @component
 * @returns {React.Element} Dashboard UI
 *
 * @example
 * import Dashboard from './components/Dashboard';
 *
 * function App() {
 *   return (
 *     <Router>
 *       <Route path="/" element={<Dashboard />} />
 *     </Router>
 *   );
 * }
 */
function Dashboard() {
  // Implementation details...
}
```

### DeltaDisplay Component

```javascript
/**
 * Display component for showing value changes with color coding
 *
 * @component
 * @param {Object} props - Component props
 * @param {number} props.current - Current value
 * @param {number} props.previous - Previous value for comparison
 * @param {string} [props.unit='m'] - Unit of measurement
 * @param {boolean} [props.showIcon=true] - Show up/down arrow icon
 *
 * @returns {React.Element} Delta display with color-coded indicator
 *
 * @example
 * <DeltaDisplay
 *   current={1.523}
 *   previous={1.498}
 *   unit="m"
 *   showIcon={true}
 * />
 * // Renders: "▲ +0.025m" in green
 */
function DeltaDisplay({ current, previous, unit = 'm', showIcon = true }) {
  // Implementation details...
}
```

This document provides comprehensive JSDoc examples that can be applied to the actual codebase. Each function includes:

- Description of purpose
- Parameter documentation with types
- Return value documentation
- Usage examples
- Edge case handling

To apply these to your code:

1. Copy the JSDoc blocks above each function definition
2. Adjust parameter names and types as needed
3. Update examples to match actual usage
4. Run JSDoc generator: `npm run jsdoc` (after configuring jsdoc.json)
