/**
 * GovMap Helper Utilities
 * Utility functions for GovMap integration including IMS translations,
 * mobile positioning, and coordinate conversion
 */

// ============================================================================
// IMS CODE TRANSLATIONS
// ============================================================================

const seaStateCodes = {
  10: "Calm",
  20: "Rippled",
  30: "Smooth",
  40: "Smooth to slight",
  50: "Slight",
  55: "Slight to moderate",
  60: "Moderate",
  70: "Moderate to rough",
  80: "Rough",
  90: "Rough to very rough",
  110: "Very rough",
  120: "Very rough to high",
  130: "High",
  140: "High to very high",
  150: "Very high",
  160: "Phenomenal"
};

const windDirections = {
  "045": "NE",
  "090": "E",
  "135": "SE",
  "180": "S",
  "225": "SW",
  "270": "W",
  "315": "NW",
  "360": "N"
};

/**
 * Translate IMS wave height codes to readable format
 * @param {string} waveString - Format: "40 / 30-60" or "40"
 * @returns {string} Translated format: "Smooth to slight (30-60 cm)"
 */
export function translateWaveHeight(waveString) {
  if (!waveString || typeof waveString !== 'string') return waveString;

  const parts = waveString.split(' / ');
  if (parts.length !== 2) {
    const code = parseInt(waveString.trim());
    return seaStateCodes[code] || waveString;
  }

  const code = parseInt(parts[0].trim());
  const actualHeight = parts[1].trim();
  const translatedCode = seaStateCodes[code] || parts[0].trim();

  return `${translatedCode} (${actualHeight} cm)`;
}

/**
 * Translate IMS wind direction codes to readable format
 * @param {string} windString - Format: "315-045/15-25" or "315/15-25"
 * @returns {string} Translated format: "NW-NE (15-25 km/h)"
 */
export function translateWindInfo(windString) {
  if (!windString || typeof windString !== 'string') return windString;

  const parts = windString.split('/');
  if (parts.length !== 2) return windString;

  const directions = parts[0];
  const speeds = parts[1];

  let translatedDirections = directions;
  if (directions.includes('-')) {
    const dirParts = directions.split('-');
    const dir1 = dirParts[0].padStart(3, '0');
    const dir2 = dirParts[1].padStart(3, '0');
    const trans1 = windDirections[dir1] || dirParts[0];
    const trans2 = windDirections[dir2] || dirParts[1];
    translatedDirections = `${trans1}-${trans2}`;
  } else {
    const dir = directions.padStart(3, '0');
    translatedDirections = windDirections[dir] || directions;
  }

  return `${translatedDirections} (${speeds.trim()} km/h)`;
}

// ============================================================================
// WEATHER RISK COLOR CODING
// ============================================================================

/**
 * Get risk color for wave conditions
 * @param {string} waveString - Wave height string
 * @returns {string} CSS color code
 */
export function getWaveRiskColor(waveString) {
  if (!waveString) return '#6c757d';
  const code = parseInt(waveString.split(' / ')[0] || waveString);
  if (code >= 80) return '#dc3545';  // red - dangerous
  if (code >= 60) return '#fd7e14';  // orange - rough
  if (code >= 40) return '#ffc107';  // yellow - moderate
  return '#6c757d';                  // grey - calm
}

/**
 * Get risk color for wind conditions
 * @param {string} windString - Wind info string
 * @returns {string} CSS color code
 */
export function getWindRiskColor(windString) {
  if (!windString) return '#6c757d';
  const speedPart = windString.split('/')[1];
  if (!speedPart) return '#6c757d';
  const maxSpeed = Math.max(...speedPart.split('-').map(s => parseInt(s.trim())));
  if (maxSpeed >= 40) return '#dc3545';  // red - very strong
  if (maxSpeed >= 25) return '#fd7e14';  // orange - strong
  if (maxSpeed >= 15) return '#ffc107';  // yellow - moderate
  return '#6c757d';                      // grey - light
}

// ============================================================================
// COORDINATE CONVERSION
// ============================================================================

/**
 * Convert WGS84 (lat/lon) to Israel ITM coordinates
 * @param {number} lon - Longitude
 * @param {number} lat - Latitude
 * @returns {{x: number, y: number}} ITM coordinates
 */
export function convertToITM(lon, lat) {
  const x = 219529 + (lon - 35.2045) * 111320 * Math.cos(lat * Math.PI / 180);
  const y = 626907 + (lat - 31.7344) * 111320;
  return { x: Math.round(x), y: Math.round(y) };
}

// ============================================================================
// STATION-FORECAST MAPPING
// ============================================================================

/**
 * Map station names to forecast locations
 */
export const stationForecastMap = {
  'Acre': 'Northern Coast',
  'Yafo': 'Central Coast',
  'Ashkelon': 'Southern Coast',
  'Eilat': 'Gulf of Eilat'
};

// ============================================================================
// MARKER DATA PROCESSING
// ============================================================================

/**
 * Process station and forecast data into GovMap marker format
 * @param {Array} stationsData - Array of station objects
 * @param {Array} forecastData - Array of forecast location objects
 * @returns {Array} Array of marker objects ready for GovMap display
 */
export function processMarkersData(stationsData, forecastData = []) {
  if (!stationsData || !Array.isArray(stationsData)) {
    return [];
  }

  const markers = [];

  // Process station markers with integrated forecast data
  stationsData.forEach((station) => {
    // Use ITM coordinates if available, otherwise convert from lat/lon
    let coords = { x: station.x, y: station.y };
    if (!coords.x || !coords.y) {
      if (station.longitude && station.latitude) {
        coords = convertToITM(station.longitude, station.latitude);
      } else {
        console.warn(`Station ${station.Station} missing coordinates`);
        return;
      }
    }

    // Find matching forecast data
    const forecastLocation = stationForecastMap[station.Station];
    const matchingForecast = forecastData.find(f => f.name_eng === forecastLocation);

    let bubbleHTML = `
      <div class="govmap-bubble" style="font-family: Arial, sans-serif; padding: 15px; min-width: 250px; direction: ltr; text-align: left;">
        <h4 style="margin: 0 0 15px 0; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px;">${station.Station}</h4>
        <div style="margin: 8px 0;"><strong>Sea Level:</strong> ${station.latest_value} m</div>
        <div style="margin: 8px 0;"><strong>Temperature:</strong> ${station.temperature || 'N/A'}°C</div>
        <div style="margin: 8px 0; font-size: 12px; color: #7f8c8d;"><strong>Last Update:</strong> ${station.last_update}</div>
        <div style="font-size: 11px; color: #888; margin-top: 10px;">
          <a href="https://www.gov.il/he/departments/survey_of_israel/govil-landing-page" target="_parent" style="color: #666; text-decoration: none;">© 2025 Survey of Israel. All rights reserved.</a>
        </div>`;

    // Add forecast data if available
    if (matchingForecast && matchingForecast.forecasts && matchingForecast.forecasts[0]) {
      const currentForecast = matchingForecast.forecasts[0];
      const waveHeight = translateWaveHeight(currentForecast?.elements?.wave_height || 'N/A');
      const windInfo = translateWindInfo(currentForecast?.elements?.wind || 'N/A');

      bubbleHTML += `
        <hr style="margin: 15px 0; border: none; border-top: 1px solid #ddd;">
        <h4 style="margin: 0 0 10px 0; color: #ff8c00;">${forecastLocation}</h4>
        <div style="margin: 8px 0;"><strong>Wave Height:</strong> ${waveHeight}</div>
        <div style="margin: 8px 0;"><strong>Sea Temperature:</strong> ${currentForecast?.elements?.sea_temperature || 'N/A'}°C</div>
        <div style="margin: 8px 0;"><strong>Wind:</strong> ${windInfo}</div>
        <div style="font-size: 12px; color: #7f8c8d; margin-top: 10px;">
          <strong>Forecast Period:</strong><br>${currentForecast?.from || 'N/A'} - ${currentForecast?.to || 'N/A'}
        </div>
        <div style="font-size: 11px; color: #888; margin-top: 5px;">
          <a href="https://ims.gov.il/he/coasts" target="_parent" style="color: #666; text-decoration: none;">IMS Forecast ©</a>
        </div>`;
    }

    bubbleHTML += '</div>';

    markers.push({
      wkt: `POINT(${coords.x} ${coords.y})`,
      name: `station_${station.Station}`,
      symbol: {
        url: 'data:image/svg+xml;base64,' + btoa(
          '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="32" height="32">' +
          '<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" fill="#2196F3"/>' +
          '</svg>'
        ),
        width: 32,
        height: 32
      },
      tooltip: matchingForecast
        ? `${station.Station} - Combined Data`
        : `${station.Station} - ${station.latest_value}m`,
      bubbleHTML: bubbleHTML
    });
  });

  // Add Sea of Galilee forecast marker (standalone - no station data)
  const seaOfGalilee = forecastData.find(f => f.name_eng === 'Sea of Galilee');
  if (seaOfGalilee && seaOfGalilee.coordinates) {
    const coords = convertToITM(seaOfGalilee.coordinates.lng, seaOfGalilee.coordinates.lat);
    const currentForecast = seaOfGalilee.forecasts?.[0];

    if (currentForecast) {
      const waveHeight = translateWaveHeight(currentForecast?.elements?.wave_height || 'N/A');
      const windInfo = translateWindInfo(currentForecast?.elements?.wind || 'N/A');

      const bubbleHTML = `
        <div class="govmap-bubble" style="font-family: Arial, sans-serif; padding: 15px; min-width: 250px; direction: ltr; text-align: left;">
          <h4 style="margin: 0 0 15px 0; color: #ff8c00; border-bottom: 2px solid #ff8c00; padding-bottom: 5px;">${seaOfGalilee.name_eng}</h4>
          <div style="margin: 8px 0;"><strong>Wave Height:</strong> ${waveHeight}</div>
          <div style="margin: 8px 0;"><strong>Sea Temperature:</strong> ${currentForecast?.elements?.sea_temperature || 'N/A'}°C</div>
          <div style="margin: 8px 0;"><strong>Wind:</strong> ${windInfo}</div>
          <div style="font-size: 12px; color: #7f8c8d; margin-top: 10px;">
            <strong>Forecast Period:</strong><br>${currentForecast?.from || 'N/A'} - ${currentForecast?.to || 'N/A'}
          </div>
          <div style="font-size: 11px; color: #888; margin-top: 10px;">
            <a href="https://ims.gov.il/he/coasts" target="_parent" style="color: #666; text-decoration: none;">IMS Forecast ©</a>
          </div>
        </div>`;

      markers.push({
        wkt: `POINT(${coords.x} ${coords.y})`,
        name: 'forecast_sea_of_galilee',
        symbol: {
          url: 'data:image/svg+xml;base64,' + btoa(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="32" height="32">' +
            '<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" fill="#2196F3"/>' +
            '</svg>'
          ),
          width: 32,
          height: 32
        },
        tooltip: `${seaOfGalilee.name_eng} - Wave Forecast`,
        bubbleHTML: bubbleHTML
      });
    }
  }

  return markers;
}

// ============================================================================
// MOBILE POSITIONING UTILITIES
// ============================================================================

/**
 * Detect if device is in mobile portrait orientation
 * @returns {boolean}
 */
export function isMobilePortrait() {
  return window.innerWidth <= 768 && window.innerHeight > window.innerWidth;
}

/**
 * Detect if device is in mobile landscape orientation
 * @returns {boolean}
 */
export function isMobileLandscape() {
  return window.innerWidth <= 992 && window.innerWidth >= window.innerHeight;
}

/**
 * Apply mobile portrait positioning to GovMap popups
 * Forces popups to appear on the right side of the screen in portrait mode
 */
export function applyMobilePortraitPositioning() {
  if (!isMobilePortrait()) return;

  const forcePortraitPosition = (element) => {
    if (!element) return;
    element.style.setProperty('position', 'fixed', 'important');
    element.style.setProperty('right', '5px', 'important');
    element.style.setProperty('top', '50%', 'important');
    element.style.setProperty('transform', 'translateY(-50%)', 'important');
    element.style.setProperty('left', 'auto', 'important');
    element.style.setProperty('bottom', 'auto', 'important');
    element.style.setProperty('width', 'auto', 'important');
    element.style.setProperty('max-width', '250px', 'important');
    element.style.setProperty('max-height', '80vh', 'important');
    element.style.setProperty('z-index', '99999', 'important');
    element.style.setProperty('box-shadow', '0 4px 12px rgba(0,0,0,0.3)', 'important');
    element.style.setProperty('border-radius', '8px', 'important');
    element.style.setProperty('overflow-y', 'auto', 'important');
  };

  // Target all possible popup selectors
  const selectors = [
    '.govmap-bubble',
    'div[style*="position: absolute"]',
    'div[style*="position: fixed"]',
    'div[class*="bubble"]',
    'div[class*="popup"]',
    'div[class*="tooltip"]',
    '#govmap-container > div > div',
    '#govmap-container div[style]'
  ];

  selectors.forEach(selector => {
    const elements = document.querySelectorAll(selector);
    elements.forEach(element => {
      // Check if element contains popup-like content
      if (element.innerHTML && (
        element.innerHTML.includes('Sea Level') ||
        element.innerHTML.includes('Wave Height') ||
        element.innerHTML.includes('Temperature')
      )) {
        forcePortraitPosition(element);

        // Also position parent containers (up to 3 levels)
        let parent = element.parentElement;
        let depth = 0;
        while (parent && parent !== document.body && depth < 3) {
          if (parent.style.position) {
            forcePortraitPosition(parent);
          }
          parent = parent.parentElement;
          depth++;
        }
      }
    });
  });
}

/**
 * Reset mobile landscape positioning to GovMap defaults
 * Removes forced positioning and allows natural popup placement
 */
export function resetMobileLandscapePositioning() {
  if (!isMobileLandscape()) return;

  const selectors = [
    '.govmap-bubble',
    'div[class*="bubble"]',
    'div[class*="popup"]'
  ];

  selectors.forEach(selector => {
    const elements = document.querySelectorAll(selector);
    elements.forEach(element => {
      // Reset to GovMap's default positioning
      element.style.removeProperty('position');
      element.style.removeProperty('right');
      element.style.removeProperty('top');
      element.style.removeProperty('transform');
      element.style.removeProperty('left');
      element.style.removeProperty('bottom');
      element.style.removeProperty('width');

      // Set reasonable landscape constraints
      element.style.setProperty('max-width', '300px', 'important');
      element.style.setProperty('max-height', '60vh', 'important');
    });
  });
}

// ============================================================================
// ERROR SUPPRESSION
// ============================================================================

/**
 * Suppress GovMap authentication errors from console
 * These errors are expected when using GovMap without full authentication
 */
export function suppressGovMapErrors() {
  const originalConsoleError = console.error;
  console.error = function(...args) {
    const message = args.join(' ');
    if (
      message.includes('API token authentication failed') ||
      message.includes('401') ||
      message.includes('govmap.gov.il/api/users-management') ||
      message.includes('govmap.gov.il/api/layers-catalog')
    ) {
      return; // Suppress these specific errors
    }
    originalConsoleError.apply(console, args);
  };

  // Also suppress fetch errors for auth endpoints
  const originalFetch = window.fetch;
  window.fetch = function(url, options) {
    return originalFetch(url, options).catch(error => {
      if (
        url.includes('govmap.gov.il/api/users-management') ||
        url.includes('govmap.gov.il/api/layers-catalog')
      ) {
        // Return a fake successful response for auth endpoints
        return Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({})
        });
      }
      throw error;
    });
  };
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Debounce function to limit execution rate
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
