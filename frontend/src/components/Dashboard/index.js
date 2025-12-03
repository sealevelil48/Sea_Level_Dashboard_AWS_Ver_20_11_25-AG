import React, { useState, useEffect, useCallback, useRef, useMemo, Suspense, lazy } from 'react';
import { Container, Row, Col, Card, Tabs, Tab, Badge, Button, Spinner } from 'react-bootstrap';
import { Link } from 'react-router-dom';

// Hooks
import { useFilters } from '../../hooks/useFilters';
import { useStations } from '../../hooks/useStations';
import { useChartJsConfig } from '../../hooks/useChartJsConfig';
import { useFavorites } from '../../hooks/useFavorites';

// Components
import ErrorBoundary from '../ErrorBoundary';
import DashboardHeader from './DashboardHeader';
import DashboardFilters from './DashboardFilters';
import SeaLevelChart from './SeaLevelChart';
import DashboardMap from './DashboardMap';
import WarningsCard from '../WarningsCard';
import StatsCard from '../StatsCard';

// Lazy load heavy components
const SeaForecastView = lazy(() => import('../SeaForecastView'));
const MarinersForecastView = lazy(() => import('../MarinersForecastView'));

// Utils
import apiService from '../../services/apiService';
import { calculateDelta } from '../../utils/deltaCalculator';
import { formatDateTime } from '../../utils/dateUtils';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:30886';

/**
 * Safely format a number to fixed decimal places
 * Returns fallback value if input is not a valid number
 * @param {*} value - The value to format
 * @param {number} decimals - Number of decimal places
 * @param {string} fallback - Fallback value if invalid
 * @returns {string} Formatted number or fallback
 */
const safeToFixed = (value, decimals = 3, fallback = '0.000') => {
  if (value === null || value === undefined || typeof value !== 'number' || isNaN(value)) {
    return fallback;
  }
  return value.toFixed(decimals);
};

function Dashboard() {
  // Use extracted hooks
  const { filters, filterValues, updateFilter, updateDateRange, toggleModel } = useFilters();
  const {
    stations,
    selectedStations,
    handleStationChange,
    stationsFetched,
    loading: _stationsLoading
  } = useStations();
  const { favorites, addFavorite, removeFavorite, isFavorite } = useFavorites();

  // Local state
  const [activeTab, setActiveTab] = useState('graph');
  const [mapTab, setMapTab] = useState('govmap'); // CEO requirement: GovMap default
  const [tableTab, setTableTab] = useState('historical');
  const [loading, setLoading] = useState(false);
  const [graphData, setGraphData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [predictions, setPredictions] = useState({});
  const [forecastData, setForecastData] = useState(null);
  const [stats, setStats] = useState({
    current_level: 0,
    '24h_change': 0,
    avg_temp: 0,
    anomalies: 0
  });

  // UI state
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);
  const [filtersOpen, setFiltersOpen] = useState(window.innerWidth > 768);
  const [isGraphFullscreen, setIsGraphFullscreen] = useState(false);
  const [isTableFullscreen, setIsTableFullscreen] = useState(false);
  const [isMapFullscreen, setIsMapFullscreen] = useState(false);
  const [isMarinersFullscreen, setIsMarinersFullscreen] = useState(false);
  const [govmapReady, setGovmapReady] = useState(false);

  // Table state
  const [currentPage, setCurrentPage] = useState(1);
  const [forecastPage, setForecastPage] = useState(1);
  const [itemsPerPage] = useState(50);
  const [sortConfig, setSortConfig] = useState({ key: 'Tab_DateTime', direction: 'desc' });

  // Point selection state
  const [selectedPoints, setSelectedPoints] = useState([]);
  const [deltaResult, setDeltaResult] = useState(null);

  // Refs
  const isMounted = useRef(true);
  const isInitialLoadRef = useRef(true);
  const isFetchingRef = useRef(false);
  const debounceTimerRef = useRef(null);
  const abortControllerRef = useRef(null);
  const chartRef = useRef(null);

  const isMobile = windowWidth < 768;

  // Resize handler
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      setWindowWidth(width);
      if (width <= 768) {
        setFiltersOpen(false);
      } else {
        setFiltersOpen(true);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
      if (abortControllerRef.current) abortControllerRef.current.abort();
      apiService.cancelAllRequests();
      isFetchingRef.current = false;
    };
  }, []);

  // Lock body scroll when Table or Mariners fullscreen is active (iOS Safari fix)
  // NOTE: Only lock for Table/Mariners, NOT for Graph/Map to avoid conflicts
  useEffect(() => {
    const shouldLockBody = isTableFullscreen || isMarinersFullscreen;

    if (shouldLockBody) {
      console.log('🔒 Locking body for fullscreen:', { isTableFullscreen, isMarinersFullscreen });

      // Store original values
      const originalOverflow = document.body.style.overflow;
      const originalPosition = document.body.style.position;
      const originalWidth = document.body.style.width;
      const originalTop = document.body.style.top;

      // Lock scroll (iOS Safari fix for fixed positioning)
      document.body.style.overflow = 'hidden';
      document.body.style.position = 'fixed';
      document.body.style.width = '100%';
      document.body.style.top = '0';

      // Cleanup: restore original values
      return () => {
        console.log('🔓 Unlocking body from fullscreen');
        document.body.style.overflow = originalOverflow;
        document.body.style.position = originalPosition;
        document.body.style.width = originalWidth;
        document.body.style.top = originalTop;
      };
    }
  }, [isTableFullscreen, isMarinersFullscreen]);

  // Fetch forecast data on mount
  useEffect(() => {
    const fetchForecast = async () => {
      // Create AbortController with timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout

      try {
        const response = await fetch(`${API_BASE_URL}/api/sea-forecast`, {
          signal: controller.signal
        });

        // Clear timeout on successful response
        clearTimeout(timeoutId);

        if (response.ok) {
          // Validate content-type
          const contentType = response.headers.get('content-type');
          if (!contentType || !contentType.includes('application/json')) {
            console.error('Invalid content-type for forecast:', contentType);
            return;
          }

          const data = await response.json();

          // Validate response data structure
          if (!data || typeof data !== 'object') {
            console.error('Invalid forecast data structure:', data);
            return;
          }

          // Only update state if component is still mounted
          if (isMounted.current) {
            setForecastData(data);
          }
        } else {
          console.error(`Forecast fetch failed with status: ${response.status}`);
        }
      } catch (err) {
        // Clear timeout on error
        clearTimeout(timeoutId);

        if (err.name === 'AbortError') {
          console.error('Forecast fetch timeout after 30 seconds');
        } else {
          console.error('Forecast fetch error:', err);
        }

        // Set error state if component is still mounted
        if (isMounted.current) {
          setForecastData(null);
        }
      }
    };

    if (stationsFetched) {
      fetchForecast();

      // Refresh every 30 minutes
      const interval = setInterval(fetchForecast, 30 * 60 * 1000);
      return () => clearInterval(interval);
    }
  }, [stationsFetched]);

  // GovMap deferred loading
  useEffect(() => {
    if (graphData.length > 0 && !loading) {
      const timer = setTimeout(() => {
        if (isMounted.current) {
          setGovmapReady(true);
          console.log('GovMap ready to load');
        }
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [graphData, loading]);

  // Delta calculation when 2 points selected
  useEffect(() => {
    try {
      // Validate selectedPoints array exists and has exactly 2 points
      if (!selectedPoints || !Array.isArray(selectedPoints) || selectedPoints.length !== 2) {
        setDeltaResult(null);
        return;
      }

      // Validate first point
      const pt1 = selectedPoints[0];
      if (!pt1 ||
          typeof pt1.y !== 'number' ||
          isNaN(pt1.y) ||
          !pt1.timestamp ||
          !pt1.station) {
        console.warn('Invalid first selected point:', pt1);
        setDeltaResult(null);
        return;
      }

      // Validate second point
      const pt2 = selectedPoints[1];
      if (!pt2 ||
          typeof pt2.y !== 'number' ||
          isNaN(pt2.y) ||
          !pt2.timestamp ||
          !pt2.station) {
        console.warn('Invalid second selected point:', pt2);
        setDeltaResult(null);
        return;
      }

      const point1 = {
        Tab_Value_mDepthC1: pt1.y,
        Tab_DateTime: pt1.timestamp,
        Station: pt1.station
      };
      const point2 = {
        Tab_Value_mDepthC1: pt2.y,
        Tab_DateTime: pt2.timestamp,
        Station: pt2.station
      };

      // Calculate delta with try-catch
      const delta = calculateDelta(point1, point2);
      setDeltaResult(delta);
    } catch (error) {
      console.error('Error calculating delta:', error);
      setDeltaResult(null);
    }
  }, [selectedPoints]);

  // Calculate 24-hour change for a station's data
  const calculate24hChange = useCallback((stationData) => {
    if (!stationData || stationData.length < 2) return 0;

    const sortedData = [...stationData].sort((a, b) =>
      new Date(a.Tab_DateTime) - new Date(b.Tab_DateTime)
    );

    const latestPoint = sortedData[sortedData.length - 1];
    const latestTime = new Date(latestPoint.Tab_DateTime);
    const latestLevel = latestPoint.Tab_Value_mDepthC1;

    if (isNaN(latestLevel)) return 0;

    const target24hAgo = new Date(latestTime.getTime() - 24 * 60 * 60 * 1000);
    const toleranceMs = 2 * 60 * 60 * 1000;

    let closestPoint = null;
    let closestDiff = Infinity;

    for (const point of sortedData) {
      const pointTime = new Date(point.Tab_DateTime);
      const diff = Math.abs(pointTime.getTime() - target24hAgo.getTime());

      if (diff < closestDiff && diff <= toleranceMs && !isNaN(point.Tab_Value_mDepthC1)) {
        closestDiff = diff;
        closestPoint = point;
      }
    }

    if (closestPoint) {
      return latestLevel - closestPoint.Tab_Value_mDepthC1;
    }

    return 0;
  }, []);

  // Calculate stats from data
  const calculateStats = useCallback((data) => {
    if (!data || data.length === 0) return;

    let currentLevel = 0;
    let change24h = 0;
    let avgTemp = 0;
    let anomalyCount = 0;

    if (selectedStations.includes('All Stations') || selectedStations.length > 1) {
      const stationGroups = {};
      data.forEach(d => {
        if (!stationGroups[d.Station]) {
          stationGroups[d.Station] = [];
        }
        stationGroups[d.Station].push(d);
      });

      let stationCount = 0;
      let validChangeCount = 0;

      Object.values(stationGroups).forEach(stationData => {
        if (stationData.length > 0) {
          stationCount++;
          const levels = stationData.map(d => d.Tab_Value_mDepthC1).filter(v => !isNaN(v));
          const temps = stationData.map(d => d.Tab_Value_monT2m).filter(v => !isNaN(v));

          if (levels.length > 0) {
            currentLevel += levels[levels.length - 1];
          }

          const stationChange = calculate24hChange(stationData);
          if (stationChange !== 0) {
            change24h += stationChange;
            validChangeCount++;
          }

          if (temps.length > 0) {
            avgTemp += temps.reduce((a, b) => a + b, 0) / temps.length;
          }
          anomalyCount += stationData.filter(d => d.anomaly === -1).length;
        }
      });

      if (stationCount > 0) {
        currentLevel /= stationCount;
        avgTemp /= stationCount;
      }
      if (validChangeCount > 0) {
        change24h /= validChangeCount;
      }
    } else {
      const levels = data.map(d => d.Tab_Value_mDepthC1).filter(v => !isNaN(v));
      const temps = data.map(d => d.Tab_Value_monT2m).filter(v => !isNaN(v));

      if (levels.length > 0) {
        currentLevel = levels[levels.length - 1];
      }

      change24h = calculate24hChange(data);

      if (temps.length > 0) {
        avgTemp = temps.reduce((a, b) => a + b, 0) / temps.length;
      }
      anomalyCount = data.filter(d => d.anomaly === -1).length;
    }

    setStats({
      current_level: currentLevel,
      '24h_change': change24h,
      avg_temp: avgTemp,
      anomalies: anomalyCount
    });
  }, [selectedStations, calculate24hChange]);

  // Main data fetch function
  const fetchData = useCallback(async () => {
    if (!stationsFetched || isFetchingRef.current) return;
    if (selectedStations.length === 0) return;

    isFetchingRef.current = true;
    setLoading(true);

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      // Determine which stations to fetch
      let stationsToFetch = [];
      if (selectedStations.includes('All Stations')) {
        stationsToFetch = stations.filter(s => s !== 'All Stations');
      } else {
        stationsToFetch = selectedStations.filter(s => s !== 'All Stations').slice(0, 3);
      }

      if (stationsToFetch.length === 0) {
        setLoading(false);
        isFetchingRef.current = false;
        return;
      }

      const params = {
        start_date: filterValues.startDate,
        end_date: filterValues.endDate,
        data_source: filterValues.dataType,
        include_outliers: filterValues.showAnomalies ? 'true' : 'false'
      };

      console.log(`Fetching data for ${stationsToFetch.length} stations in parallel`);
      const startTime = performance.now();

      let allData = await apiService.getDataBatch(stationsToFetch, params);

      const endTime = performance.now();
      console.log(`Batch fetch completed in ${(endTime - startTime).toFixed(0)}ms for ${stationsToFetch.length} stations`);

      if (!Array.isArray(allData)) {
        console.error('Batch data is not an array:', allData);
        allData = [];
      }

      if (isMounted.current) {
        // Log anomaly data if showAnomalies is enabled
        if (filterValues.showAnomalies && allData.length > 0) {
          const anomalyCount = allData.filter(d => d.anomaly === -1).length;
          const totalCount = allData.length;
          const anomalyValues = [...new Set(allData.map(d => d.anomaly))];
          console.log(`[Dashboard] Anomaly detection enabled:`, {
            totalPoints: totalCount,
            anomaliesFound: anomalyCount,
            anomalyValues: anomalyValues,
            percentage: ((anomalyCount / totalCount) * 100).toFixed(2) + '%'
          });
          if (anomalyCount > 0) {
            console.log(`[Dashboard] Sample anomaly point:`, allData.find(d => d.anomaly === -1));
          }
        }

        setGraphData(allData || []);

        // Sort data in DESC order by default (newest first)
        setTableData([...(allData || [])].sort((a, b) => {
          const dateA = a.Tab_DateTime || a.Date || '';
          const dateB = b.Tab_DateTime || b.Date || '';
          return dateB.localeCompare(dateA);
        }));
        setCurrentPage(1);

        // Calculate stats
        calculateStats(allData);
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('Data fetch error:', err);
      }
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
      abortControllerRef.current = null;
      isFetchingRef.current = false;
    }
  }, [stationsFetched, selectedStations, stations, filterValues, calculateStats]);

  // Debounced fetch trigger
  useEffect(() => {
    if (stations.length > 0 && selectedStations.length > 0) {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      const debounceTime = isInitialLoadRef.current ? 300 : 1500;

      debounceTimerRef.current = setTimeout(() => {
        if (isMounted.current && !isFetchingRef.current) {
          fetchData();
          if (isInitialLoadRef.current) {
            isInitialLoadRef.current = false;
          }
        }
      }, debounceTime);

      return () => {
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }
      };
    }
  }, [fetchData, stations.length, selectedStations.length]);

  // Fetch predictions when models selected
  const fetchPredictions = useCallback(async (stationsToPredict) => {
    if (filters.predictionModels.length === 0) {
      setPredictions({});
      return;
    }

    // Create AbortController with timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout

    try {
      const modelParam = filters.predictionModels.join(',');
      const stationParam = stationsToPredict.join(',');

      const params = new URLSearchParams({
        stations: stationParam,
        model: modelParam,
        steps: filters.forecastHours.toString()
      });

      console.log('Fetching predictions:', {
        stations: stationParam,
        models: modelParam,
        steps: filters.forecastHours
      });

      const response = await fetch(`${API_BASE_URL}/api/predictions?${params}`, {
        signal: controller.signal
      });

      // Clear timeout on successful response
      clearTimeout(timeoutId);

      if (!response.ok) {
        // Validate content-type
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('text/html')) {
          throw new Error('Received HTML instead of JSON. Check if backend route is /api/predictions');
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Validate content-type
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        console.error('Invalid content-type for predictions:', contentType);
        if (isMounted.current) {
          setPredictions({});
        }
        return;
      }

      const data = await response.json();

      // Validate response data structure
      if (!data || typeof data !== 'object') {
        console.error('Invalid predictions data structure:', data);
        if (isMounted.current) {
          setPredictions({});
        }
        return;
      }

      console.log('Predictions received successfully:', Object.keys(data));

      // Only update state if component is still mounted
      if (isMounted.current) {
        setPredictions(data);
      }
    } catch (error) {
      // Clear timeout on error
      clearTimeout(timeoutId);

      if (error.name === 'AbortError') {
        console.error('Predictions fetch timeout after 15 seconds');
      } else {
        console.error('Error fetching predictions:', error);
      }

      // Set error state if component is still mounted
      if (isMounted.current) {
        setPredictions({});
      }
    }
  }, [filters.predictionModels, filters.forecastHours]);

  // Effect for predictions
  useEffect(() => {
    if (filters.predictionModels.length > 0 &&
        selectedStations.length > 0 &&
        !selectedStations.includes('All Stations')) {
      const stationsToPredict = selectedStations.filter(s => s !== 'All Stations').slice(0, 3);
      if (stationsToPredict.length > 0) {
        console.log(`Fetching predictions for ${stationsToPredict.join(', ')} with ${filters.forecastHours} hour forecast`);
        fetchPredictions(stationsToPredict);
      }
    } else {
      setPredictions({});
    }
  }, [filters.predictionModels, filters.forecastHours, selectedStations, fetchPredictions]);

  // Use Chart.js config hook
  const chartData = useChartJsConfig({
    graphData,
    predictions,
    filters,
    selectedStations,
    selectedPoints,
    isFullscreen: isGraphFullscreen,
    isMobile
  });

  // Point selection handlers
  const handlePointSelect = useCallback((pointData) => {
    setSelectedPoints(prev => {
      const isSelected = prev.some(
        p => p.pointIndex === pointData.pointIndex && p.traceIndex === pointData.traceIndex
      );
      if (isSelected) {
        return prev.filter(
          p => !(p.pointIndex === pointData.pointIndex && p.traceIndex === pointData.traceIndex)
        );
      }
      if (prev.length >= 2) return [...prev.slice(1), pointData];
      return [...prev, pointData];
    });
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedPoints([]);
  }, []);

  // Sort handler
  const handleSort = useCallback((key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
    setCurrentPage(1);
  }, []);

  // Fullscreen toggle handlers
  const toggleGraphFullscreen = useCallback(() => {
    setIsGraphFullscreen(prev => !prev);
  }, []);

  const toggleTableFullscreen = useCallback(() => {
    setIsTableFullscreen(prev => !prev);
  }, []);

  const toggleMapFullscreen = useCallback(() => {
    setIsMapFullscreen(prev => !prev);
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 300);
  }, []);

  const toggleMarinersFullscreen = useCallback(() => {
    setIsMarinersFullscreen(prev => !prev);
  }, []);

  // Export handlers
  const exportGraph = useCallback(() => {
    if (chartRef.current && chartRef.current.exportAsImage) {
      const url = chartRef.current.exportAsImage();
      if (url) {
        const link = document.createElement('a');
        link.download = `sea_level_graph_${selectedStations.join('_')}_${filterValues.endDate}.png`;
        link.href = url;
        link.click();
      }
    }
  }, [selectedStations, filterValues.endDate]);

  const exportTable = useCallback(() => {
    if (activeTab === 'mariners') {
      const marinersExportEvent = new CustomEvent('exportMarinersTable');
      window.dispatchEvent(marinersExportEvent);
      return;
    }

    if (tableData.length === 0) {
      alert('No data to export');
      return;
    }

    import('xlsx').then(XLSX => {
      const workbook = {
        SheetNames: ['Historical Data'],
        Sheets: {}
      };

      workbook.Sheets['Historical Data'] = XLSX.utils.json_to_sheet(tableData);

      // Forecast data worksheet
      const predictionRows = [];
      Object.entries(predictions).forEach(([stationKey, stationPredictions]) => {
        if (stationKey === 'global_metadata' || !stationPredictions) return;

        ['kalman', 'ensemble', 'arima'].forEach(model => {
          if (stationPredictions[model] && Array.isArray(stationPredictions[model])) {
            stationPredictions[model].forEach((pred) => {
              predictionRows.push({
                Station: stationKey,
                Model: model,
                DateTime: pred.ds,
                PredictedLevel: pred.yhat || pred,
                Type: pred.type || 'forecast',
                Uncertainty: pred.uncertainty || '',
                UpperBound: pred.yhat_upper || '',
                LowerBound: pred.yhat_lower || ''
              });
            });
          }
        });
      });

      if (predictionRows.length > 0) {
        workbook.SheetNames.push('Forecast Data');
        workbook.Sheets['Forecast Data'] = XLSX.utils.json_to_sheet(predictionRows);
      }

      XLSX.writeFile(workbook, `sea_level_data_${selectedStations.join('_')}_${filterValues.endDate}.xlsx`);
    }).catch(err => {
      console.error('Failed to load XLSX library:', err);
      alert('Failed to export data. Please try again.');
    });
  }, [activeTab, tableData, predictions, selectedStations, filterValues.endDate]);

  // Sorted table data
  const sortedTableData = useMemo(() => {
    if (!tableData || tableData.length === 0) return [];

    return [...tableData].sort((a, b) => {
      let aValue, bValue;

      if (sortConfig.key === 'Tab_DateTime') {
        aValue = a.Tab_DateTime || a.Date || '';
        bValue = b.Tab_DateTime || b.Date || '';
      } else if (sortConfig.key === 'Station') {
        aValue = a.Station || '';
        bValue = b.Station || '';
      } else {
        return 0;
      }

      if (sortConfig.direction === 'asc') {
        return aValue.localeCompare(bValue);
      } else {
        return bValue.localeCompare(aValue);
      }
    });
  }, [tableData, sortConfig]);

  // Render sortable column header
  const renderSortableHeader = (label, key) => {
    const isSorted = sortConfig.key === key;
    const sortIcon = isSorted ? (sortConfig.direction === 'asc' ? ' ▲' : ' ▼') : ' ⇅';

    return (
      <th
        onClick={() => handleSort(key)}
        style={{ cursor: 'pointer', userSelect: 'none' }}
        title={`Click to sort by ${label}`}
      >
        {label}{sortIcon}
      </th>
    );
  };

  // Prediction rows for forecast table
  const predictionRows = useMemo(() => {
    const rows = [];
    Object.entries(predictions).forEach(([stationKey, stationPredictions]) => {
      if (stationKey === 'global_metadata' || !stationPredictions) return;

      ['kalman', 'ensemble', 'arima'].forEach(model => {
        if (stationPredictions[model] && Array.isArray(stationPredictions[model])) {
          stationPredictions[model].forEach((pred) => {
            rows.push({
              station: stationKey,
              model: model,
              datetime: pred.ds,
              value: pred.yhat || pred,
              type: pred.type || 'forecast',
              uncertainty: pred.uncertainty,
              upper: pred.yhat_upper,
              lower: pred.yhat_lower
            });
          });
        }
      });
    });

    rows.sort((a, b) => {
      if (a.station !== b.station) return a.station.localeCompare(b.station);
      if (a.model !== b.model) return a.model.localeCompare(b.model);
      return a.datetime.localeCompare(b.datetime);
    });

    return rows;
  }, [predictions]);

  return (
    <ErrorBoundary>
      <div className="dash-container">
        <DashboardHeader isMobile={isMobile} />

        <Container fluid className="p-1 p-md-3">
          {/* IMS Warnings - Mobile: Below header */}
          {isMobile && (
            <Row className="mb-3">
              <Col xs={12}>
                <WarningsCard apiBaseUrl={API_BASE_URL} />
              </Col>
            </Row>
          )}

          <Row className="g-2">
            {/* Filters Column */}
            <Col xs={12} lg={3} xl={2}>
              <DashboardFilters
                filters={filters}
                stations={stations}
                selectedStations={selectedStations}
                favorites={favorites}
                addFavorite={addFavorite}
                removeFavorite={removeFavorite}
                isFavorite={isFavorite}
                onFilterChange={updateFilter}
                onDateRangeChange={updateDateRange}
                onStationChange={handleStationChange}
                onModelChange={toggleModel}
                onExportGraph={exportGraph}
                onExportData={exportTable}
                isMobile={isMobile}
                filtersOpen={filtersOpen}
                setFiltersOpen={setFiltersOpen}
              />
            </Col>

            {/* Main Content */}
            <Col xs={12} lg={9} xl={10}>
              {/* IMS Warnings - Desktop: In main area */}
              {!isMobile && (
                <Row className="mb-3">
                  <Col xs={12}>
                    <WarningsCard apiBaseUrl={API_BASE_URL} />
                  </Col>
                </Row>
              )}

              {/* Stats Grid - Responsive KPI Cards */}
              <div className="kpi-grid">
                <StatsCard
                  label="Current Level"
                  value={safeToFixed(stats.current_level, 3, '0.000')}
                  unit="m"
                  isMobile={isMobile}
                />
                <StatsCard
                  label="24h Change"
                  value={`${stats['24h_change'] >= 0 ? '+' : ''}${safeToFixed(stats['24h_change'], 3, '0.000')}`}
                  unit="m"
                  colorClass={stats['24h_change'] >= 0 ? 'green' : 'red'}
                  isMobile={isMobile}
                />
                <StatsCard
                  label="Avg. Temp"
                  value={safeToFixed(stats.avg_temp, 1, '0.0')}
                  unit="°C"
                  isMobile={isMobile}
                />
                <StatsCard
                  label="Anomalies"
                  value={stats.anomalies}
                  isMobile={isMobile}
                />
              </div>

              {/* Main Tabs */}
              <Card>
                <Card.Body>
                  <Tabs activeKey={activeTab} onSelect={setActiveTab} className="mb-3">
                    {/* Graph View Tab */}
                    <Tab eventKey="graph" title="Graph View">
                      {loading ? (
                        <div className="text-center p-5">
                          <Spinner animation="border" variant="primary" />
                          <p className="mt-2">Loading data...</p>
                        </div>
                      ) : graphData.length > 0 ? (
                        <div className="dashboard-chart-wrapper" style={{
                          height: isGraphFullscreen ? '100vh' : '500px',
                          position: isGraphFullscreen ? 'fixed' : 'relative',
                          top: isGraphFullscreen ? 0 : 'auto',
                          left: isGraphFullscreen ? 0 : 'auto',
                          right: isGraphFullscreen ? 0 : 'auto',
                          bottom: isGraphFullscreen ? 0 : 'auto',
                          zIndex: isGraphFullscreen ? 9999 : 'auto'
                        }}>
                          {/* Fullscreen button - PC: top right, Mobile: shown below chart */}
                          {!isGraphFullscreen && !isMobile && (
                            <Button
                              variant="outline-primary"
                              size="sm"
                              onClick={toggleGraphFullscreen}
                              style={{
                                position: 'absolute',
                                top: '10px',
                                right: '10px',
                                zIndex: 100,
                                fontSize: '0.75rem'
                              }}
                            >
                              Full Screen
                            </Button>
                          )}
                          {/* Exit fullscreen button - centered at bottom */}
                          {isGraphFullscreen && (
                            <div style={{
                              position: 'fixed',
                              bottom: '20px',
                              left: '50%',
                              transform: 'translateX(-50%)',
                              zIndex: 10000
                            }}>
                              <Button
                                variant="outline-danger"
                                size="sm"
                                className="py-1"
                                onClick={toggleGraphFullscreen}
                                style={{ fontSize: '0.75rem' }}
                              >
                                Exit Full Screen
                              </Button>
                            </div>
                          )}
                          {selectedPoints.length > 0 && !isGraphFullscreen && (
                            <Button
                              variant="warning"
                              size="sm"
                              onClick={handleClearSelection}
                              style={{
                                position: 'absolute',
                                top: isMobile ? 'auto' : '10px',
                                bottom: isMobile ? '10px' : 'auto',
                                right: !isMobile ? '120px' : '10px',
                                zIndex: 100,
                                backgroundColor: '#fbbf24',
                                borderColor: '#fbbf24',
                                color: '#000',
                                fontSize: '0.75rem'
                              }}
                            >
                              Clear ({selectedPoints.length})
                            </Button>
                          )}
                          <SeaLevelChart
                            ref={chartRef}
                            data={chartData}
                            activeStations={selectedStations}
                            isMobile={isMobile}
                            isFullscreen={isGraphFullscreen}
                            onPointClick={handlePointSelect}
                          />
                          {deltaResult && (
                            <div style={{
                              position: 'absolute',
                              bottom: '20px',
                              right: '20px',
                              backgroundColor: 'rgba(15, 23, 42, 0.95)',
                              padding: '15px',
                              borderRadius: '8px',
                              border: '1px solid rgba(59, 130, 246, 0.3)',
                              color: 'white',
                              minWidth: '250px',
                              zIndex: 100
                            }}>
                              <h6 style={{ color: '#60a5fa', marginBottom: '10px' }}>Delta Comparison</h6>
                              <div style={{ fontSize: '0.9em', marginBottom: '8px' }}>
                                <strong>{deltaResult.point1?.station}:</strong> {safeToFixed(deltaResult.point1?.value, 3, 'N/A')} m
                              </div>
                              <div style={{ fontSize: '0.9em', marginBottom: '8px' }}>
                                <strong>{deltaResult.point2?.station}:</strong> {safeToFixed(deltaResult.point2?.value, 3, 'N/A')} m
                              </div>
                              <div style={{
                                fontSize: '1em',
                                fontWeight: 'bold',
                                color: '#fbbf24',
                                marginTop: '10px',
                                marginBottom: '8px'
                              }}>
                                Delta: {safeToFixed(deltaResult.delta?.valueDelta, 3, 'N/A')} m
                                {deltaResult.delta && !deltaResult.delta.isEqual && (
                                  <span style={{ marginLeft: '5px' }}>
                                    {deltaResult.delta.isPoint1Higher ? '↑' : '↓'}
                                  </span>
                                )}
                              </div>
                              {deltaResult.delta?.percentageDifference !== undefined && (
                                <div style={{ fontSize: '0.85em', color: '#9ca3af', marginBottom: '8px' }}>
                                  Change: {safeToFixed(deltaResult.delta.percentageDifference, 2, 'N/A')}%
                                </div>
                              )}
                              {deltaResult.timeDelta && (
                                <div style={{ fontSize: '0.85em', color: '#9ca3af', marginBottom: '8px' }}>
                                  Time span: {deltaResult.timeDelta.formattedString}
                                </div>
                              )}
                              <Button
                                variant="outline-danger"
                                size="sm"
                                onClick={handleClearSelection}
                                style={{ marginTop: '10px', width: '100%' }}
                              >
                                Clear Selection
                              </Button>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="text-center p-5">
                          <p>No data to display. Select a station to view data.</p>
                        </div>
                      )}
                      {/* Graph Fullscreen Button (Mobile) */}
                      {!isGraphFullscreen && isMobile && graphData.length > 0 && (
                        <div className="mt-2 text-center">
                          <Button
                            variant="outline-primary"
                            size="sm"
                            className="py-1"
                            onClick={toggleGraphFullscreen}
                            style={{ fontSize: '0.75rem' }}
                          >
                            Full Screen
                          </Button>
                        </div>
                      )}
                      {/* Model Status Indicator */}
                      {filters.predictionModels && filters.predictionModels.length > 0 && (
                        <div className="mt-2 text-center">
                          <small style={{ color: '#00ff00' }}>
                            Active Models: {filters.predictionModels.join(', ')} |
                            Stations: {selectedStations.filter(s => s !== 'All Stations').length > 0 ?
                              selectedStations.filter(s => s !== 'All Stations').slice(0, 3).join(', ') : 'None'}
                          </small>
                        </div>
                      )}
                    </Tab>

                    {/* Table View Tab */}
                    <Tab eventKey="table" title="Table View">
                      <div
                        style={{
                          position: isTableFullscreen ? 'fixed' : 'relative',
                          top: isTableFullscreen ? 0 : 'auto',
                          left: isTableFullscreen ? 0 : 'auto',
                          right: isTableFullscreen ? 0 : 'auto',
                          bottom: isTableFullscreen ? 0 : 'auto',
                          width: isTableFullscreen ? '100%' : 'auto',
                          height: isTableFullscreen ? '100%' : 'auto',
                          zIndex: isTableFullscreen ? 9999 : 'auto',
                          backgroundColor: isTableFullscreen ? '#0c1c35' : 'transparent',
                          padding: isTableFullscreen ? '15px' : '0',
                          overflow: isTableFullscreen ? 'auto' : 'visible',
                          WebkitOverflowScrolling: isTableFullscreen ? 'touch' : 'auto',
                          transform: isTableFullscreen ? 'translateZ(0)' : 'none',
                          WebkitTransform: isTableFullscreen ? 'translateZ(0)' : 'none'
                        }}
                      >
                        <Tabs activeKey={tableTab} onSelect={setTableTab} className="mb-2">
                          <Tab eventKey="historical" title="Historical">
                            <div style={{
                              overflowX: 'auto',
                              maxHeight: isTableFullscreen ? 'calc(100vh - 120px)' : 'clamp(300px, 40vh, 400px)',
                              WebkitOverflowScrolling: 'touch'
                            }}>
                              {tableData.length > 0 ? (
                                <>
                                  <table className="table table-dark table-striped table-sm">
                                    <thead>
                                      <tr>
                                        {renderSortableHeader('Date/Time', 'Tab_DateTime')}
                                        {renderSortableHeader('Station', 'Station')}
                                        {filters.dataType === 'tides' ? (
                                          <>
                                            <th>High Tide (m)</th>
                                            <th>Low Tide (m)</th>
                                          </>
                                        ) : (
                                          <>
                                            <th>Sea Level (m)</th>
                                            <th>Temperature (°C)</th>
                                          </>
                                        )}
                                        <th>Anomaly</th>
                                        {filters.trendline !== 'none' && <th>Trendline</th>}
                                        {filters.analysisType !== 'none' && <th>Analysis</th>}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {sortedTableData
                                        .slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
                                        .map((row, idx) => (
                                          <tr key={idx}>
                                            <td>{filters.dataType === 'tides' ? row.Date : formatDateTime(row.Tab_DateTime)}</td>
                                            <td>{row.Station}</td>
                                            {filters.dataType === 'tides' ? (
                                              <>
                                                <td>{safeToFixed(row.HighTide, 3, 'N/A')}</td>
                                                <td>{safeToFixed(row.LowTide, 3, 'N/A')}</td>
                                              </>
                                            ) : (
                                              <>
                                                <td>{safeToFixed(row.Tab_Value_mDepthC1, 3, 'N/A')}</td>
                                                <td>{safeToFixed(row.Tab_Value_monT2m, 1, 'N/A')}</td>
                                              </>
                                            )}
                                            <td>{row.anomaly || 0}</td>
                                            {filters.trendline !== 'none' && <td>{safeToFixed(row.trendlineValue, 3, 'N/A')}</td>}
                                            {filters.analysisType !== 'none' && <td>{safeToFixed(row.analysisValue, 3, 'N/A')}</td>}
                                          </tr>
                                        ))}
                                    </tbody>
                                  </table>
                                  <div className="d-flex justify-content-between align-items-center mt-3">
                                    <span className="text-muted">
                                      Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, sortedTableData.length)} of {sortedTableData.length} entries
                                    </span>
                                    <div>
                                      <Button
                                        variant="outline-primary"
                                        size="sm"
                                        className="me-2"
                                        onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                                        disabled={currentPage === 1}
                                      >
                                        Previous
                                      </Button>
                                      <span className="mx-2">Page {currentPage} of {Math.ceil(sortedTableData.length / itemsPerPage)}</span>
                                      <Button
                                        variant="outline-primary"
                                        size="sm"
                                        className="ms-2"
                                        onClick={() => setCurrentPage(prev => Math.min(prev + 1, Math.ceil(sortedTableData.length / itemsPerPage)))}
                                        disabled={currentPage === Math.ceil(sortedTableData.length / itemsPerPage)}
                                      >
                                        Next
                                      </Button>
                                    </div>
                                  </div>
                                </>
                              ) : (
                                <p className="text-center">No data to display</p>
                              )}
                            </div>

                            {/* Table Fullscreen Controls */}
                            {!isTableFullscreen && isMobile && (
                              <div className="mt-2 text-center">
                                <Button
                                  variant="outline-primary"
                                  size="sm"
                                  className="py-1"
                                  onClick={toggleTableFullscreen}
                                  style={{ fontSize: '0.75rem' }}
                                >
                                  Full Screen
                                </Button>
                              </div>
                            )}
                          </Tab>

                          <Tab eventKey="forecast" title="Forecast">
                            <div style={{
                              overflowX: 'auto',
                              maxHeight: isTableFullscreen ? 'calc(100vh - 120px)' : 'clamp(300px, 40vh, 400px)'
                            }}>
                              {predictionRows.length > 0 ? (
                                <>
                                  <table className="table table-dark table-striped">
                                    <thead>
                                      <tr>
                                        <th>Station</th>
                                        <th>Model</th>
                                        <th>Date/Time</th>
                                        <th>Predicted Level (m)</th>
                                        <th>Type</th>
                                        <th>Uncertainty</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {predictionRows
                                        .slice((forecastPage - 1) * itemsPerPage, forecastPage * itemsPerPage)
                                        .map((row, idx) => (
                                          <tr key={idx}>
                                            <td>{row.station}</td>
                                            <td>
                                              <Badge bg={row.model === 'kalman' ? 'success' : row.model === 'ensemble' ? 'warning' : 'info'}>
                                                {row.model.toUpperCase()}
                                              </Badge>
                                            </td>
                                            <td>{row.datetime.replace('T', ' ').replace(/\.\d+Z$/, '')}</td>
                                            <td>{safeToFixed(row.value, 3, 'N/A')}</td>
                                            <td>
                                              <Badge bg={row.type === 'nowcast' ? 'primary' : 'secondary'}>
                                                {row.type || 'forecast'}
                                              </Badge>
                                            </td>
                                            <td>
                                              {row.uncertainty ? `+/-${safeToFixed(row.uncertainty, 3, 'N/A')}` :
                                                (row.upper && row.lower) ? `${safeToFixed(row.lower, 3, 'N/A')} - ${safeToFixed(row.upper, 3, 'N/A')}` : 'N/A'}
                                            </td>
                                          </tr>
                                        ))}
                                    </tbody>
                                  </table>
                                  <div className="d-flex justify-content-between align-items-center mt-3">
                                    <span className="text-muted">
                                      Showing {((forecastPage - 1) * itemsPerPage) + 1} to {Math.min(forecastPage * itemsPerPage, predictionRows.length)} of {predictionRows.length} entries
                                    </span>
                                    <div>
                                      <Button
                                        variant="outline-primary"
                                        size="sm"
                                        className="me-2"
                                        onClick={() => setForecastPage(prev => Math.max(prev - 1, 1))}
                                        disabled={forecastPage === 1}
                                      >
                                        Previous
                                      </Button>
                                      <span className="mx-2">Page {forecastPage} of {Math.ceil(predictionRows.length / itemsPerPage)}</span>
                                      <Button
                                        variant="outline-primary"
                                        size="sm"
                                        className="ms-2"
                                        onClick={() => setForecastPage(prev => Math.min(prev + 1, Math.ceil(predictionRows.length / itemsPerPage)))}
                                        disabled={forecastPage === Math.ceil(predictionRows.length / itemsPerPage)}
                                      >
                                        Next
                                      </Button>
                                    </div>
                                  </div>
                                </>
                              ) : (
                                <p className="text-center">No predictions available. Select prediction models to see forecasts.</p>
                              )}
                            </div>
                          </Tab>
                        </Tabs>

                        {/* Table Fullscreen Exit Button */}
                        {isTableFullscreen && (
                          <div style={{
                            position: 'fixed',
                            bottom: '20px',
                            left: '50%',
                            transform: 'translateX(-50%)',
                            zIndex: 2000
                          }}>
                            <Button
                              variant="outline-danger"
                              size="sm"
                              className="py-1"
                              onClick={toggleTableFullscreen}
                              style={{ fontSize: '0.75rem' }}
                            >
                              Exit Full Screen
                            </Button>
                          </div>
                        )}
                      </div>
                    </Tab>

                    {/* Map View Tab */}
                    <Tab eventKey="map" title="Map View">
                      <DashboardMap
                        mapTab={mapTab}
                        onMapTabChange={setMapTab}
                        stations={stations}
                        selectedStations={selectedStations}
                        graphData={graphData}
                        forecastData={forecastData}
                        govmapReady={govmapReady}
                        filterEndDate={filterValues.endDate}
                        isFullscreen={isMapFullscreen}
                        onToggleFullscreen={toggleMapFullscreen}
                        isMobile={isMobile}
                      />
                    </Tab>

                    {/* Waves Forecast Tab */}
                    <Tab eventKey="forecast" title="Waves Forecast">
                      <Suspense fallback={
                        <div className="text-center p-5">
                          <Spinner animation="border" variant="primary" />
                          <p className="mt-2">Loading forecast...</p>
                        </div>
                      }>
                        <SeaForecastView apiBaseUrl={API_BASE_URL} />
                      </Suspense>
                    </Tab>

                    {/* Mariners Forecast Tab */}
                    <Tab eventKey="mariners" title="Mariners Forecast">
                      <div
                        style={{
                          position: isMarinersFullscreen ? 'fixed' : 'relative',
                          top: isMarinersFullscreen ? 0 : 'auto',
                          left: isMarinersFullscreen ? 0 : 'auto',
                          right: isMarinersFullscreen ? 0 : 'auto',
                          bottom: isMarinersFullscreen ? 0 : 'auto',
                          width: isMarinersFullscreen ? '100%' : 'auto',
                          height: isMarinersFullscreen ? '100%' : 'auto',
                          zIndex: isMarinersFullscreen ? 9999 : 'auto',
                          backgroundColor: isMarinersFullscreen ? '#0c1c35' : 'transparent',
                          padding: isMarinersFullscreen ? '15px' : '0',
                          overflow: isMarinersFullscreen ? 'auto' : 'visible',
                          WebkitOverflowScrolling: isMarinersFullscreen ? 'touch' : 'auto',
                          transform: isMarinersFullscreen ? 'translateZ(0)' : 'none',
                          WebkitTransform: isMarinersFullscreen ? 'translateZ(0)' : 'none'
                        }}
                      >
                        <Suspense fallback={<Spinner animation="border" />}>
                          <MarinersForecastView
                            apiBaseUrl={API_BASE_URL}
                            isFullscreen={isMarinersFullscreen}
                          />
                        </Suspense>

                        {/* Mariners Fullscreen Controls */}
                        {!isMarinersFullscreen && isMobile && (
                          <div className="mt-2 text-center">
                            <Button
                              variant="outline-primary"
                              size="sm"
                              className="py-1"
                              onClick={toggleMarinersFullscreen}
                              style={{ fontSize: '0.75rem' }}
                            >
                              Full Screen
                            </Button>
                          </div>
                        )}

                        {/* Mariners Fullscreen Exit Button */}
                        {isMarinersFullscreen && (
                          <div style={{
                            position: 'fixed',
                            bottom: '20px',
                            left: '50%',
                            transform: 'translateX(-50%)',
                            zIndex: 2000
                          }}>
                            <Button
                              variant="outline-danger"
                              size="sm"
                              className="py-1"
                              onClick={toggleMarinersFullscreen}
                              style={{ fontSize: '0.75rem' }}
                            >
                              Exit Full Screen
                            </Button>
                          </div>
                        )}
                      </div>
                    </Tab>
                  </Tabs>
                </Card.Body>
              </Card>
            </Col>
          </Row>
        </Container>

        {/* Footer */}
        <footer style={{
          backgroundColor: '#0a172c',
          padding: isMobile ? '15px' : '20px',
          textAlign: 'center',
          borderTop: '1px solid #1e3c72',
          marginTop: '20px',
          fontSize: isMobile ? '0.8rem' : '0.95rem'
        }}>
          <p style={{ color: '#a0c8f0', margin: 0 }}>
            2025 Survey of Israel. All rights reserved.
            {!isMobile && (
              <> | <Link to="/disclaimer" style={{ color: '#4dabf5' }}>Disclaimer</Link></>
            )}
          </p>
          {isMobile && (
            <p style={{ color: '#a0c8f0', margin: '5px 0 0 0' }}>
              <Link to="/disclaimer" style={{ color: '#4dabf5' }}>Disclaimer</Link>
            </p>
          )}
        </footer>
      </div>
    </ErrorBoundary>
  );
}

export default Dashboard;
