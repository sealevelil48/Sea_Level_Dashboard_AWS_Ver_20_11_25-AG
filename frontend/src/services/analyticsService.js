/**
 * Analytics Service - Client for server-side analytical calculations
 * Replaces client-side rolling averages, trendlines, and comparisons
 * with efficient database window functions
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:30886';

class AnalyticsService {
  /**
   * Fetch rolling averages from server (replaces client-side calculation)
   *
   * @param {string} station - Station name or 'All Stations'
   * @param {string} startDate - Start date (YYYY-MM-DD)
   * @param {string} endDate - End date (YYYY-MM-DD)
   * @param {Array<number>} windowHours - Window sizes in hours [3, 6, 24]
   * @returns {Promise<Array>} Array of data with rolling averages
   */
  async getRollingAverages(station, startDate, endDate, windowHours = [3, 6, 24]) {
    try {
      const params = new URLSearchParams({
        analysis_type: 'rolling_avg',
        station: station || 'All Stations',
        start_date: startDate,
        end_date: endDate,
        window_hours: windowHours.join(',')
      });

      const response = await fetch(`${API_BASE_URL}/api/analytics?${params}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Analytics API error: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('[ANALYTICS] Rolling averages fetched:', data.length, 'records');
      return data;

    } catch (error) {
      console.error('[ANALYTICS ERROR] Failed to fetch rolling averages:', error);
      throw error;
    }
  }

  /**
   * Fetch trendline data from server (replaces client-side calculation)
   *
   * @param {string} station - Station name or 'All Stations'
   * @param {string} startDate - Start date (YYYY-MM-DD)
   * @param {string} endDate - End date (YYYY-MM-DD)
   * @param {number} periodDays - Period in days (7, 30, 90, 365)
   * @returns {Promise<Array>} Array of data with trendline values
   */
  async getTrendline(station, startDate, endDate, periodDays = null) {
    try {
      const params = new URLSearchParams({
        analysis_type: 'trendline',
        station: station || 'All Stations',
        start_date: startDate,
        end_date: endDate
      });

      if (periodDays) {
        params.append('period_days', periodDays);
      }

      const response = await fetch(`${API_BASE_URL}/api/analytics?${params}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Analytics API error: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('[ANALYTICS] Trendline fetched:', data.length, 'records');
      return data;

    } catch (error) {
      console.error('[ANALYTICS ERROR] Failed to fetch trendline:', error);
      throw error;
    }
  }

  /**
   * Fetch station comparison/difference from server
   *
   * @param {string} station1 - First station name
   * @param {string} station2 - Second station name
   * @param {string} startDate - Start date (YYYY-MM-DD)
   * @param {string} endDate - End date (YYYY-MM-DD)
   * @returns {Promise<Array>} Array of comparison data
   */
  async getStationDifference(station1, station2, startDate, endDate) {
    try {
      const params = new URLSearchParams({
        analysis_type: 'station_diff',
        station1: station1,
        station2: station2,
        start_date: startDate,
        end_date: endDate
      });

      const response = await fetch(`${API_BASE_URL}/api/analytics?${params}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Analytics API error: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('[ANALYTICS] Station difference fetched:', data.length, 'records');
      return data;

    } catch (error) {
      console.error('[ANALYTICS ERROR] Failed to fetch station difference:', error);
      throw error;
    }
  }

  /**
   * Fetch lag/lead analysis from server
   *
   * @param {string} station - Station name or 'All Stations'
   * @param {string} startDate - Start date (YYYY-MM-DD)
   * @param {string} endDate - End date (YYYY-MM-DD)
   * @param {number} lagHours - Hours to lag/lead (default 1)
   * @returns {Promise<Array>} Array of lag/lead analysis
   */
  async getLagLeadAnalysis(station, startDate, endDate, lagHours = 1) {
    try {
      const params = new URLSearchParams({
        analysis_type: 'lag_lead',
        station: station || 'All Stations',
        start_date: startDate,
        end_date: endDate,
        lag_hours: lagHours
      });

      const response = await fetch(`${API_BASE_URL}/api/analytics?${params}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Analytics API error: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('[ANALYTICS] Lag/Lead analysis fetched:', data.length, 'records');
      return data;

    } catch (error) {
      console.error('[ANALYTICS ERROR] Failed to fetch lag/lead analysis:', error);
      throw error;
    }
  }

  /**
   * Convert server-side rolling averages to Plotly traces
   *
   * @param {Array} data - Data from getRollingAverages()
   * @param {Array<number>} windowHours - Window sizes to extract
   * @returns {Array} Plotly trace objects
   */
  convertToPlotlyTraces(data, windowHours = [3, 6, 24]) {
    if (!data || data.length === 0) return [];

    const traces = [];
    const colorMap = {
      3: 'violet',
      6: 'cyan',
      24: 'magenta'
    };

    windowHours.forEach(hours => {
      const columnName = `rolling_avg_${hours}h`;

      if (data[0] && columnName in data[0]) {
        traces.push({
          x: data.map(d => d.Tab_DateTime),
          y: data.map(d => d[columnName]),
          type: 'scattergl',
          mode: 'lines',
          name: `${hours}-Hour Avg`,
          line: {
            color: colorMap[hours] || 'blue',
            width: 2,
            shape: 'spline',
            smoothing: 1.3
          }
        });
      }
    });

    return traces;
  }

  /**
   * Convert server-side trendline to Plotly trace
   *
   * @param {Array} data - Data from getTrendline()
   * @param {string} period - Period label (e.g., '7d', '30d')
   * @returns {Object} Plotly trace object
   */
  convertTrendlineToTrace(data, period = 'all') {
    if (!data || data.length === 0) return null;

    return {
      x: data.map(d => d.Tab_DateTime),
      y: data.map(d => d.trendline_value),
      type: 'scattergl',
      mode: 'lines',
      name: `Trendline (${period})`,
      line: {
        color: 'yellow',
        dash: 'dash',
        width: 2
      }
    };
  }
}

// Export singleton instance
const analyticsService = new AnalyticsService();
export default analyticsService;
