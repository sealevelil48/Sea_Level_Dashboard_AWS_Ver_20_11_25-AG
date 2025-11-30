/**
 * React Query Configuration
 * Setup and configuration for @tanstack/react-query
 */

import { QueryClient } from '@tanstack/react-query';

/**
 * Create and configure QueryClient instance
 * Provides global settings for data fetching, caching, and retries
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Caching strategy
      staleTime: 5 * 60 * 1000,        // Data considered fresh for 5 minutes
      cacheTime: 10 * 60 * 1000,       // Cached data kept for 10 minutes

      // Retry strategy
      retry: 2,                        // Retry failed requests up to 2 times
      retryDelay: attemptIndex => Math.min(1000 * 2 ** attemptIndex, 30000),

      // Refetch strategy
      refetchOnWindowFocus: false,     // Don't refetch when window regains focus
      refetchOnReconnect: true,        // Refetch when network reconnects
      refetchOnMount: false,           // Don't refetch on component mount if data is fresh

      // Error handling
      useErrorBoundary: false,         // Handle errors in component, not error boundary

      // Suspense
      suspense: false,                 // Don't use React Suspense
    },
    mutations: {
      // Retry strategy for mutations
      retry: 1,
      retryDelay: 1000,
    },
  },
});

/**
 * Query keys for consistent cache management
 * Use these constants throughout the app for query identification
 */
export const QUERY_KEYS = {
  STATIONS: 'stations',
  SEA_FORECAST: 'sea-forecast',
  MARINERS_FORECAST: 'mariners-forecast',
  IMS_WARNINGS: 'ims-warnings',
};

/**
 * Cache time constants (milliseconds)
 */
export const CACHE_TIMES = {
  STATIONS: 5 * 60 * 1000,        // 5 minutes - frequently updated
  FORECASTS: 30 * 60 * 1000,      // 30 minutes - updated less frequently
  WARNINGS: 15 * 60 * 1000,       // 15 minutes - important but not critical
  STATIC: 60 * 60 * 1000,         // 1 hour - rarely changes
};

/**
 * Prefetch data for better performance
 * Call this function to pre-load data before it's needed
 *
 * @param {string} apiBaseUrl - Base URL for API calls
 * @param {string} date - Date string for station data (YYYY-MM-DD)
 */
export async function prefetchData(apiBaseUrl, date) {
  // Prefetch stations data
  await queryClient.prefetchQuery({
    queryKey: [QUERY_KEYS.STATIONS, date],
    queryFn: async () => {
      const response = await fetch(`${apiBaseUrl}/api/stations/map?end_date=${date}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch stations: ${response.status}`);
      }
      return response.json();
    },
    staleTime: CACHE_TIMES.STATIONS,
  });

  // Prefetch forecast data
  await queryClient.prefetchQuery({
    queryKey: [QUERY_KEYS.SEA_FORECAST],
    queryFn: async () => {
      const response = await fetch(`${apiBaseUrl}/api/sea-forecast`);
      if (!response.ok) {
        throw new Error(`Failed to fetch forecast: ${response.status}`);
      }
      const data = await response.json();
      return data.locations || [];
    },
    staleTime: CACHE_TIMES.FORECASTS,
  });
}

/**
 * Invalidate all queries to force refetch
 * Useful after significant data changes or errors
 */
export function invalidateAllQueries() {
  queryClient.invalidateQueries();
}

/**
 * Clear all cached data
 * Use sparingly - only when absolutely necessary
 */
export function clearAllCache() {
  queryClient.clear();
}

/**
 * Get cached data without triggering a fetch
 * Returns undefined if data is not in cache
 *
 * @param {string} queryKey - Query key to retrieve
 * @param {any} params - Additional query parameters
 * @returns {any} Cached data or undefined
 */
export function getCachedData(queryKey, params) {
  return queryClient.getQueryData([queryKey, params]);
}

/**
 * Set cached data manually
 * Useful for optimistic updates or pre-populating cache
 *
 * @param {string} queryKey - Query key to set
 * @param {any} params - Additional query parameters
 * @param {any} data - Data to cache
 */
export function setCachedData(queryKey, params, data) {
  queryClient.setQueryData([queryKey, params], data);
}
