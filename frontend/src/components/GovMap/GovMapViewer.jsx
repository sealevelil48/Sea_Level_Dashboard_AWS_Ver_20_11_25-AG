/**
 * GovMapViewer Component
 * React component for displaying Israel's GovMap with sea level station markers
 * and wave forecast data
 *
 * Replaces iframe-based mapframe.html with direct React integration
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  processMarkersData,
  suppressGovMapErrors,
  applyMobilePortraitPositioning,
  resetMobileLandscapePositioning,
  isMobilePortrait,
  isMobileLandscape,
  debounce
} from '../../utils/govmapHelpers';
import { QUERY_KEYS, CACHE_TIMES } from '../../utils/queryClientSetup';
import './GovMapViewer.css';

// GovMap configuration matching the developer's pattern from mapframe.html
const GOVMAP_CONFIG = {
  token: '11aa3021-4ae0-4771-8ae0-df75e73fe73e',  // Your GovMap API token
  level: 0,                    // Zoom level (NOT 'zoom') - 0 for full country view
  showXY: true,                // Show coordinates
  identifyOnClick: true,       // Enable click identification
  isEmbeddedToggle: false,     // Not in iframe mode
  background: 0,               // Background type (NOT 'basemap')
  layersMode: 2,               // Layer display mode
  zoomButtons: false,          // Hide default zoom buttons
  center: { x: 176505, y: 662250 }  // Center on Israel
};

/**
 * GovMapViewer Component
 * @param {Object} props
 * @param {string} props.selectedDate - Date for station data (YYYY-MM-DD format)
 * @param {string} props.apiBaseUrl - Base URL for API calls (default: current host)
 * @param {boolean} props.isFullscreen - Fullscreen mode flag (optional)
 * @param {boolean} props.isMobile - Mobile device flag (optional)
 * @param {string} props.className - Additional CSS classes (optional)
 * @param {Object} props.style - Inline styles (optional)
 */
const GovMapViewer = ({
  selectedDate,
  apiBaseUrl = '',
  isFullscreen = false,
  isMobile = false,
  className = '',
  style = {}
}) => {
  // Refs
  const mapRef = useRef(null);
  const govmapInstanceRef = useRef(null);
  const mutationObserverRef = useRef(null);

  // State
  const [isMapReady, setIsMapReady] = useState(false);
  const [isMapLoaded, setIsMapLoaded] = useState(false);
  const [mapError, setMapError] = useState(null);

  // ============================================================================
  // DATA FETCHING WITH REACT QUERY
  // ============================================================================

  // Fetch station data with caching
  const {
    data: stationsData,
    isLoading: stationsLoading,
    error: stationsError,
    refetch: refetchStations
  } = useQuery({
    queryKey: [QUERY_KEYS.STATIONS, selectedDate],
    queryFn: async () => {
      const response = await fetch(
        `${apiBaseUrl}/stations/map?end_date=${selectedDate}`
      );
      if (!response.ok) {
        throw new Error(`Station fetch failed: ${response.status}`);
      }
      // API returns DIRECT array (no .data wrapper)
      const data = await response.json();
      return data;
    },
    staleTime: CACHE_TIMES.STATIONS,
    cacheTime: CACHE_TIMES.STATIONS * 2,
    retry: 2,
    enabled: !!selectedDate,  // Fetch immediately, don't wait for map
    onError: (error) => {
      console.error('Failed to fetch station data:', error);
    }
  });

  // Fetch forecast data with caching
  const {
    data: forecastData,
    isLoading: forecastLoading,
    error: forecastError,
    refetch: refetchForecast
  } = useQuery({
    queryKey: [QUERY_KEYS.SEA_FORECAST],
    queryFn: async () => {
      const response = await fetch(`${apiBaseUrl}/sea-forecast`);
      if (!response.ok) {
        throw new Error(`Forecast fetch failed: ${response.status}`);
      }
      // API returns DIRECT object with {metadata, locations}
      const data = await response.json();
      return data.locations || [];
    },
    staleTime: CACHE_TIMES.FORECASTS,
    cacheTime: CACHE_TIMES.FORECASTS * 2,
    retry: 2,
    enabled: true,  // Fetch immediately in parallel
    onError: (error) => {
      console.warn('Failed to fetch forecast data (non-critical):', error);
    }
  });

  // ============================================================================
  // MEMOIZED DATA PROCESSING
  // ============================================================================

  const processedMarkers = useMemo(() => {
    if (!stationsData || !Array.isArray(stationsData) || stationsData.length === 0) {
      return null;
    }

    console.log('Processing markers:', {
      stations: stationsData.length,
      forecasts: forecastData?.length || 0
    });

    return processMarkersData(stationsData, forecastData);
  }, [stationsData, forecastData]);

  // ============================================================================
  // GOVMAP SCRIPT LOADING
  // ============================================================================

  useEffect(() => {
    // Suppress GovMap authentication errors (expected behavior)
    suppressGovMapErrors();

    // Check if GovMap already loaded
    if (window.govmap) {
      console.log('✅ GovMap API already loaded');
      setIsMapReady(true);
      return;
    }

    // Load GovMap script with defer (matching developer's pattern)
    const script = document.createElement('script');
    script.src = 'https://www.govmap.gov.il/govmap/api/govmap.api.js';
    script.defer = true;

    script.onload = () => {
      console.log('✅ GovMap API loaded successfully');
      setIsMapReady(true);
    };

    script.onerror = () => {
      console.error('❌ Failed to load GovMap API');
      setMapError('Failed to load GovMap API. Please check your internet connection and refresh the page.');
    };

    document.head.appendChild(script);

    return () => {
      if (script.parentNode) {
        script.parentNode.removeChild(script);
      }
    };
  }, []);

  // ============================================================================
  // GOVMAP INITIALIZATION
  // ============================================================================

  useEffect(() => {
    if (!isMapReady || !mapRef.current || govmapInstanceRef.current) {
      return;
    }

    try {
      const initStartTime = performance.now();
      console.log('🗺️  Initializing GovMap at:', initStartTime);

      // GovMap requires STRING ID, not DOM element reference
      govmapInstanceRef.current = window.govmap.createMap('govmap-container', {
        ...GOVMAP_CONFIG,
        onLoad: () => {
          const onLoadTime = performance.now();
          console.log('✅ GovMap onLoad callback fired at:', onLoadTime, '(took', Math.round(onLoadTime - initStartTime), 'ms)');
        }
      });

      // Map instance created successfully - set as loaded immediately
      // The onLoad callback may or may not fire depending on GovMap API version
      // We use map instance creation as the reliable signal
      const initEndTime = performance.now();
      console.log('✅ GovMap instance created in', Math.round(initEndTime - initStartTime), 'ms - ready to display markers');
      setIsMapLoaded(true);
    } catch (error) {
      console.error('GovMap initialization error:', error);
      setMapError(`Failed to initialize map: ${error.message}. Please refresh the page.`);
    }

    // Cleanup on unmount
    // NOTE: We don't clear govmapInstanceRef.current on unmount because the component
    // may be unmounted/remounted when toggling fullscreen. The instance should persist
    // across these transitions. The ref will only be cleared when selectedDate changes
    // (which changes the component key in parent).
    return () => {
      // No cleanup needed - instance persists across fullscreen toggles
    };
  }, [isMapReady]);

  // ============================================================================
  // DISPLAY MARKERS
  // ============================================================================

  const displayMarkers = useCallback(() => {
    if (!window.govmap || !processedMarkers || processedMarkers.length === 0) {
      console.log('Cannot display markers - missing requirements:', {
        govmap: !!window.govmap,
        markers: processedMarkers?.length || 0
      });
      return;
    }

    try {
      const startTime = performance.now();
      console.log('📍 Displaying', processedMarkers.length, 'markers on GovMap...');

      const wkts = processedMarkers.map(m => m.wkt);
      const names = processedMarkers.map(m => m.name);
      const symbols = processedMarkers.map(m => m.symbol);
      const tooltips = processedMarkers.map(m => m.tooltip);
      const bubbleHTMLParameters = processedMarkers.map(m => [m.bubbleHTML]);

      // Use GovMap's displayGeometries API
      const displayData = {
        wkts,
        names,
        geometryType: window.govmap.geometryType.POINT,
        symbols,  // Array of symbols instead of defaultSymbol
        clearExisting: true,
        data: {
          tooltips,
          bubbleHTML: '{0}',  // Simple template - actual HTML is in parameters
          bubbleHTMLParameters
        }
      };

      // GovMap displayGeometries doesn't return a standard Promise
      // Call it directly and handle errors with try-catch
      window.govmap.displayGeometries(displayData);

      const endTime = performance.now();
      console.log('✅ Displayed', processedMarkers.length, 'markers in', Math.round(endTime - startTime), 'ms');
    } catch (error) {
      console.error('❌ Error in displayMarkers:', error);
      setMapError('Failed to display markers on map');
    }
  }, [processedMarkers]);

  // ============================================================================
  // HANDLE FULLSCREEN CONTAINER RESIZE AND MARKER PERSISTENCE
  // Only re-display markers when fullscreen state actually changes
  // ============================================================================

  useEffect(() => {
    // Skip if map not ready
    if (!govmapInstanceRef.current || !mapRef.current || !processedMarkers || !isMapLoaded) {
      return;
    }

    console.log('📐 Fullscreen state:', isFullscreen);
    const container = mapRef.current;
    console.log('   Container dimensions:', container.offsetWidth, 'x', container.offsetHeight);
    console.log('   Markers to display:', processedMarkers.length);

    // Wait for container resize, then re-display markers
    const timeoutId = setTimeout(() => {
      try {
        // Force a redraw by panning slightly and back
        if (govmapInstanceRef.current && typeof govmapInstanceRef.current.panBy === 'function') {
          govmapInstanceRef.current.panBy(1, 0);
          setTimeout(() => {
            if (govmapInstanceRef.current && typeof govmapInstanceRef.current.panBy === 'function') {
              govmapInstanceRef.current.panBy(-1, 0);
            }
          }, 50);
        }

        // Re-display markers after map resize
        setTimeout(() => {
          console.log('   🔄 Re-displaying markers after fullscreen change...');
          displayMarkers();
        }, 150);

        console.log('   ✅ Map resized and markers will be re-displayed');
      } catch (error) {
        console.warn('   ⚠️  Error resizing map:', error);
      }
    }, 100);

    return () => {
      clearTimeout(timeoutId);
    };
  }, [isFullscreen, processedMarkers, displayMarkers, isMapLoaded]);

  // Display markers when data changes AND map is loaded
  useEffect(() => {
    if (!govmapInstanceRef.current || !processedMarkers || !isMapLoaded) {
      if (!govmapInstanceRef.current || !processedMarkers) {
        console.log('⏳ Waiting for map instance and markers...', {
          mapInstance: !!govmapInstanceRef.current,
          markers: processedMarkers?.length || 0,
          mapLoaded: isMapLoaded
        });
      }
      return;
    }

    // Map is loaded and markers are ready - display them
    const displayStartTime = performance.now();
    console.log('🎯 Map loaded - displaying markers');
    displayMarkers();
    const displayEndTime = performance.now();
    console.log('✅ Marker display completed in:', Math.round(displayEndTime - displayStartTime), 'ms');
  }, [isMapLoaded, processedMarkers, displayMarkers]);

  // ============================================================================
  // MOBILE POSITIONING SYSTEM
  // ============================================================================

  const setupMobilePositioning = useCallback(() => {
    const debouncedPositioning = debounce(() => {
      if (isMobilePortrait()) {
        applyMobilePortraitPositioning();
      } else if (isMobileLandscape()) {
        resetMobileLandscapePositioning();
      }
    }, 100);

    debouncedPositioning();

    // Set up mutation observer to handle dynamic popup elements
    if (mutationObserverRef.current) {
      mutationObserverRef.current.disconnect();
    }

    mutationObserverRef.current = new MutationObserver(() => {
      if (isMobilePortrait()) {
        debouncedPositioning();
      }
    });

    mutationObserverRef.current.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['style', 'class']
    });

    // Also apply on click events (when popups are opened)
    const handleClick = () => {
      setTimeout(debouncedPositioning, 100);
    };

    document.addEventListener('click', handleClick);

    return () => {
      if (mutationObserverRef.current) {
        mutationObserverRef.current.disconnect();
      }
      document.removeEventListener('click', handleClick);
    };
  }, []);

  useEffect(() => {
    if (!isMapLoaded || !processedMarkers) return;

    const cleanup = setupMobilePositioning();
    return cleanup;
  }, [isMapLoaded, processedMarkers, setupMobilePositioning]);

  // ============================================================================
  // ORIENTATION CHANGE HANDLING
  // ============================================================================

  useEffect(() => {
    const handleOrientationChange = debounce(() => {
      if (isMobilePortrait()) {
        console.log('Switched to portrait - applying positioning');
        applyMobilePortraitPositioning();
      } else if (isMobileLandscape()) {
        console.log('Switched to landscape - resetting positioning');
        resetMobileLandscapePositioning();
      }
    }, 300);

    window.addEventListener('orientationchange', handleOrientationChange);

    // Fallback for browsers that don't fire orientationchange
    let resizeTimer;
    const handleResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(handleOrientationChange, 250);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('orientationchange', handleOrientationChange);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // ============================================================================
  // ERROR HANDLING & RETRY
  // ============================================================================

  const handleRetry = useCallback(() => {
    setMapError(null);
    if (stationsError) {
      refetchStations();
    }
    if (forecastError) {
      refetchForecast();
    }
    if (!isMapReady) {
      window.location.reload();
    }
  }, [stationsError, forecastError, isMapReady, refetchStations, refetchForecast]);

  // ============================================================================
  // RENDER
  // ============================================================================

  const isDataLoading = stationsLoading || forecastLoading;
  const hasError = mapError || (stationsError && !stationsData);

  // Error state
  if (hasError) {
    return (
      <div className={`govmap-error ${className}`} style={style}>
        <div className="govmap-error-content">
          <div className="govmap-error-icon">⚠️</div>
          <h3>GovMap Unavailable</h3>
          <p>
            {mapError ||
             stationsError?.message ||
             'Unable to load map or station data'}
          </p>
          <button
            onClick={handleRetry}
            className="govmap-error-button"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Map view - ALWAYS render the map container so mapRef.current is available
  return (
    <div className={`govmap-wrapper ${className} ${isFullscreen ? 'govmap-fullscreen' : ''} ${isMobile ? 'govmap-mobile' : ''}`} style={style}>
      {/* Loading overlay - ONLY shows while map API is loading, not data */}
      {!isMapReady && (
        <div className="govmap-loading-overlay">
          <div className="govmap-loading-content">
            <div className="govmap-loading-spinner"></div>
            <div className="govmap-loading-text">
              Loading GovMap...
              {stationsLoading && <div style={{fontSize: '12px', marginTop: '5px'}}>Fetching station data...</div>}
            </div>
          </div>
        </div>
      )}

      <div
        ref={mapRef}
        id="govmap-container"
        className="govmap-container"
        style={{
          width: '100%',
          height: '100%',
          minHeight: '500px'
        }}
      />
      {!stationsData && isMapReady && !isDataLoading && (
        <div className="govmap-no-data">
          <p>No station data available for selected date</p>
          <button onClick={refetchStations} className="govmap-retry-button">
            Retry
          </button>
        </div>
      )}
    </div>
  );
};

export default GovMapViewer;
