/**
 * React Performance Optimization Utilities
 * =========================================
 *
 * Comprehensive React performance optimizations:
 * 1. Component memoization utilities
 * 2. Debounce and throttle helpers
 * 3. Virtual scrolling for large lists
 * 4. Lazy loading utilities
 * 5. Re-render prevention
 */

import React, { memo, useMemo, useCallback, useEffect, useRef, useState } from 'react';

// ============================================================================
// OPTIMIZATION 1: Smart Component Memoization
// ============================================================================

/**
 * Deep comparison for memoization
 */
export const deepCompare = (prevProps, nextProps) => {
  return JSON.stringify(prevProps) === JSON.stringify(nextProps);
};

/**
 * Shallow comparison for memoization (faster than deep compare)
 */
export const shallowCompare = (prevProps, nextProps) => {
  const prevKeys = Object.keys(prevProps);
  const nextKeys = Object.keys(nextProps);

  if (prevKeys.length !== nextKeys.length) return false;

  for (let key of prevKeys) {
    if (prevProps[key] !== nextProps[key]) return false;
  }

  return true;
};

/**
 * Memoize component with custom comparator
 */
export const memoizeComponent = (Component, comparator = shallowCompare) => {
  return memo(Component, (prev, next) => comparator(prev, next));
};

// ============================================================================
// OPTIMIZATION 2: Debounce and Throttle Hooks
// ============================================================================

/**
 * Debounce hook - delays execution until after delay ms of inactivity
 * Perfect for: Search inputs, resize handlers, scroll handlers
 */
export const useDebounce = (value, delay = 300) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

/**
 * Debounced callback hook
 */
export const useDebouncedCallback = (callback, delay = 300) => {
  const timeoutRef = useRef(null);

  const debouncedCallback = useCallback(
    (...args) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        callback(...args);
      }, delay);
    },
    [callback, delay]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return debouncedCallback;
};

/**
 * Throttle hook - ensures function only executes once per delay period
 * Perfect for: Scroll handlers, mouse move handlers
 */
export const useThrottle = (value, delay = 300) => {
  const [throttledValue, setThrottledValue] = useState(value);
  const lastRan = useRef(Date.now());

  useEffect(() => {
    const handler = setTimeout(() => {
      if (Date.now() - lastRan.current >= delay) {
        setThrottledValue(value);
        lastRan.current = Date.now();
      }
    }, delay - (Date.now() - lastRan.current));

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return throttledValue;
};

/**
 * Throttled callback hook
 */
export const useThrottledCallback = (callback, delay = 300) => {
  const lastRan = useRef(Date.now());

  return useCallback(
    (...args) => {
      if (Date.now() - lastRan.current >= delay) {
        callback(...args);
        lastRan.current = Date.now();
      }
    },
    [callback, delay]
  );
};

// ============================================================================
// OPTIMIZATION 3: Virtual Scrolling for Large Lists
// ============================================================================

/**
 * Virtual scrolling hook for large datasets
 * Only renders visible items + buffer
 */
export const useVirtualScroll = ({
  itemCount,
  itemHeight,
  windowHeight = 600,
  overscan = 3
}) => {
  const [scrollTop, setScrollTop] = useState(0);

  const visibleRange = useMemo(() => {
    const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const endIndex = Math.min(
      itemCount - 1,
      Math.ceil((scrollTop + windowHeight) / itemHeight) + overscan
    );

    return { startIndex, endIndex };
  }, [scrollTop, itemHeight, windowHeight, itemCount, overscan]);

  const totalHeight = itemCount * itemHeight;
  const offsetY = visibleRange.startIndex * itemHeight;

  const handleScroll = useThrottledCallback((e) => {
    setScrollTop(e.target.scrollTop);
  }, 16); // ~60fps

  return {
    visibleRange,
    totalHeight,
    offsetY,
    handleScroll
  };
};

/**
 * Virtual List Component
 */
export const VirtualList = ({ items, renderItem, itemHeight = 50, windowHeight = 600 }) => {
  const { visibleRange, totalHeight, offsetY, handleScroll } = useVirtualScroll({
    itemCount: items.length,
    itemHeight,
    windowHeight
  });

  const visibleItems = items.slice(visibleRange.startIndex, visibleRange.endIndex + 1);

  return (
    <div
      style={{
        height: windowHeight,
        overflow: 'auto',
        position: 'relative'
      }}
      onScroll={handleScroll}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        <div style={{ transform: `translateY(${offsetY}px)` }}>
          {visibleItems.map((item, index) =>
            renderItem(item, visibleRange.startIndex + index)
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// OPTIMIZATION 4: Lazy Component Loading
// ============================================================================

/**
 * Lazy load component with suspense fallback
 */
export const lazyLoadComponent = (importFunc, fallback = <div>Loading...</div>) => {
  const LazyComponent = React.lazy(importFunc);

  return (props) => (
    <React.Suspense fallback={fallback}>
      <LazyComponent {...props} />
    </React.Suspense>
  );
};

/**
 * Intersection Observer hook for lazy loading on scroll
 */
export const useIntersectionObserver = (ref, options = {}) => {
  const [isIntersecting, setIsIntersecting] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(([entry]) => {
      setIsIntersecting(entry.isIntersecting);
    }, options);

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [ref, options]);

  return isIntersecting;
};

// ============================================================================
// OPTIMIZATION 5: Prevent Unnecessary Re-renders
// ============================================================================

/**
 * Stable reference hook - prevents re-renders from callback changes
 */
export const useStableCallback = (callback) => {
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  });

  return useCallback((...args) => callbackRef.current(...args), []);
};

/**
 * Previous value hook - compare with previous render
 */
export const usePrevious = (value) => {
  const ref = useRef();

  useEffect(() => {
    ref.current = value;
  });

  return ref.current;
};

/**
 * Detect unnecessary re-renders (development only)
 */
export const useWhyDidYouUpdate = (name, props) => {
  const previousProps = useRef();

  useEffect(() => {
    if (previousProps.current) {
      const allKeys = Object.keys({ ...previousProps.current, ...props });
      const changedProps = {};

      allKeys.forEach((key) => {
        if (previousProps.current[key] !== props[key]) {
          changedProps[key] = {
            from: previousProps.current[key],
            to: props[key]
          };
        }
      });

      if (Object.keys(changedProps).length > 0) {
        console.log('[Why-Did-You-Update]', name, changedProps);
      }
    }

    previousProps.current = props;
  });
};

// ============================================================================
// OPTIMIZATION 6: Data Processing Optimization
// ============================================================================

/**
 * Memoize expensive calculations
 */
export const useMemoizedCalculation = (data, calculationFn) => {
  return useMemo(() => {
    if (!data || data.length === 0) return null;
    return calculationFn(data);
  }, [data, calculationFn]);
};

/**
 * Batch state updates to prevent multiple re-renders
 */
export const useBatchedState = (initialState) => {
  const [state, setState] = useState(initialState);
  const pendingUpdates = useRef([]);
  const batchTimeout = useRef(null);

  const batchSetState = useCallback((update) => {
    pendingUpdates.current.push(update);

    if (batchTimeout.current) {
      clearTimeout(batchTimeout.current);
    }

    batchTimeout.current = setTimeout(() => {
      setState((prevState) => {
        let newState = prevState;
        pendingUpdates.current.forEach((updateFn) => {
          newState = typeof updateFn === 'function' ? updateFn(newState) : updateFn;
        });
        pendingUpdates.current = [];
        return newState;
      });
    }, 0);
  }, []);

  return [state, batchSetState];
};

// ============================================================================
// OPTIMIZATION 7: Request Management
// ============================================================================

/**
 * Abort controller hook for canceling requests
 */
export const useAbortController = () => {
  const abortControllerRef = useRef(null);

  const getController = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    return abortControllerRef.current;
  }, []);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return getController;
};

/**
 * Request deduplication - prevent duplicate concurrent requests
 */
export const useRequestDeduplication = () => {
  const pendingRequests = useRef(new Map());

  const makeRequest = useCallback(async (key, requestFn) => {
    // If request is already pending, return existing promise
    if (pendingRequests.current.has(key)) {
      return pendingRequests.current.get(key);
    }

    // Create new request
    const request = requestFn().finally(() => {
      pendingRequests.current.delete(key);
    });

    pendingRequests.current.set(key, request);
    return request;
  }, []);

  return makeRequest;
};

// ============================================================================
// OPTIMIZATION 8: Performance Monitoring
// ============================================================================

/**
 * Measure component render performance
 */
export const useRenderCount = (componentName) => {
  const renderCount = useRef(0);

  useEffect(() => {
    renderCount.current += 1;
    if (process.env.NODE_ENV === 'development') {
      console.log(`[Render Count] ${componentName}: ${renderCount.current}`);
    }
  });

  return renderCount.current;
};

/**
 * Performance profiler hook
 */
export const usePerformanceProfiler = (componentName) => {
  useEffect(() => {
    const startTime = performance.now();

    return () => {
      const endTime = performance.now();
      const duration = endTime - startTime;

      if (process.env.NODE_ENV === 'development' && duration > 16) {
        console.warn(
          `[Performance] ${componentName} mounted/updated in ${duration.toFixed(2)}ms ` +
          `(>16ms may cause frame drops)`
        );
      }
    };
  });
};

// ============================================================================
// Example Usage
// ============================================================================

/**
 * Optimized Table Component Example
 */
export const OptimizedTable = memo(({ data, columns, onRowClick }) => {
  // Prevent re-renders from callback changes
  const stableOnRowClick = useStableCallback(onRowClick);

  // Memoize column configuration
  const memoizedColumns = useMemo(() => columns, [columns]);

  // Virtual scrolling for large datasets
  const { visibleRange, totalHeight, offsetY, handleScroll } = useVirtualScroll({
    itemCount: data.length,
    itemHeight: 50,
    windowHeight: 600
  });

  const visibleData = useMemo(
    () => data.slice(visibleRange.startIndex, visibleRange.endIndex + 1),
    [data, visibleRange]
  );

  return (
    <div style={{ height: 600, overflow: 'auto' }} onScroll={handleScroll}>
      <div style={{ height: totalHeight, position: 'relative' }}>
        <div style={{ transform: `translateY(${offsetY}px)` }}>
          {visibleData.map((row, index) => (
            <div key={index} onClick={() => stableOnRowClick(row)}>
              {memoizedColumns.map(col => (
                <span key={col.key}>{row[col.key]}</span>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}, shallowCompare);

/**
 * Optimized Search Component Example
 */
export const OptimizedSearch = ({ onSearch }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearchTerm = useDebounce(searchTerm, 500);

  useEffect(() => {
    if (debouncedSearchTerm) {
      onSearch(debouncedSearchTerm);
    }
  }, [debouncedSearchTerm, onSearch]);

  return (
    <input
      type="text"
      value={searchTerm}
      onChange={(e) => setSearchTerm(e.target.value)}
      placeholder="Search..."
    />
  );
};

export default {
  // Memoization
  memoizeComponent,
  deepCompare,
  shallowCompare,

  // Debounce/Throttle
  useDebounce,
  useDebouncedCallback,
  useThrottle,
  useThrottledCallback,

  // Virtual Scrolling
  useVirtualScroll,
  VirtualList,

  // Lazy Loading
  lazyLoadComponent,
  useIntersectionObserver,

  // Re-render Prevention
  useStableCallback,
  usePrevious,
  useWhyDidYouUpdate,

  // Data Processing
  useMemoizedCalculation,
  useBatchedState,

  // Request Management
  useAbortController,
  useRequestDeduplication,

  // Performance Monitoring
  useRenderCount,
  usePerformanceProfiler
};
