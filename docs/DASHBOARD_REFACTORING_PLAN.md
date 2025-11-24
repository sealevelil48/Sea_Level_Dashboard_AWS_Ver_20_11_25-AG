# Dashboard.js Refactoring Plan

## Executive Summary

The current `Dashboard.js` is a **2700+ line monolithic component** that handles:
- Data fetching and caching
- State management (40+ useState hooks)
- Complex UI rendering
- Chart configuration
- Table logic
- Map integration
- Mobile responsiveness
- Point selection and delta calculations

This plan proposes a **modular architecture** that maintains all existing functionality while improving:
- **Maintainability**: Smaller, focused components
- **Performance**: React.memo on pure components, isolated re-renders
- **Testability**: Unit testable hooks and components
- **Developer Experience**: Easier to understand and modify

---

## Current Pain Points

| Issue | Impact | Lines |
|-------|--------|-------|
| 40+ useState hooks in one component | Hard to track state changes | 50-170 |
| 12+ useEffect hooks | Complex side effect management | Throughout |
| fetchData is 200+ lines | Difficult to maintain | 469-693 |
| createPlot is 400+ lines | Complex memoization | 860-1240 |
| Mixed concerns | UI, data, logic all intertwined | All |
| No code splitting opportunity | Can't lazy load parts | All |

---

## Proposed Architecture

```
frontend/src/
├── components/
│   ├── Dashboard/
│   │   ├── index.js                 # Main orchestrator (~300 lines)
│   │   ├── DashboardHeader.js       # Header with logo, time
│   │   ├── DashboardFilters.js      # Filter panel (extracted from current)
│   │   ├── DashboardGraph.js        # Plotly chart + point selection
│   │   ├── DashboardTable.js        # Data table with pagination
│   │   ├── DashboardMap.js          # Map tabs (OSM, GovMap)
│   │   ├── DashboardStats.js        # Stats cards row
│   │   └── DashboardMariners.js     # Mariners forecast tab
│   │
│   └── ... (existing components)
│
├── hooks/
│   ├── useDashboardData.js          # Main data fetching hook
│   ├── usePredictions.js            # Predictions fetching
│   ├── useStations.js               # Station management
│   ├── useFilters.js                # Filter state management
│   └── usePlotConfig.js             # Plotly configuration
│
└── utils/
    ├── plotUtils.js                 # createPlot logic (moved from Dashboard)
    ├── statsUtils.js                # Statistics calculations
    └── ... (existing utils)
```

---

## Detailed Component Breakdown

### 1. Main Dashboard (index.js) - ~300 lines

**Responsibility**: Orchestrate child components, manage high-level state

```jsx
// Dashboard/index.js
import React, { lazy, Suspense } from 'react';
import { useDashboardData } from '../../hooks/useDashboardData';
import { useFilters } from '../../hooks/useFilters';
import { useStations } from '../../hooks/useStations';

// Lazy load heavy components
const DashboardGraph = lazy(() => import('./DashboardGraph'));
const DashboardMap = lazy(() => import('./DashboardMap'));
const DashboardMariners = lazy(() => import('./DashboardMariners'));

const Dashboard = () => {
  const { filters, setFilters, filterValues } = useFilters();
  const { stations, selectedStations, setSelectedStations } = useStations();
  const { graphData, tableData, stats, loading, error } = useDashboardData({
    filters: filterValues,
    selectedStations
  });

  return (
    <div className="dash-container">
      <DashboardHeader />
      <Container fluid>
        <Row>
          <Col lg={3}>
            <DashboardFilters
              filters={filters}
              onChange={setFilters}
              stations={stations}
              selectedStations={selectedStations}
              onStationChange={setSelectedStations}
            />
          </Col>
          <Col lg={9}>
            <DashboardStats stats={stats} />
            <Tabs>
              <Tab eventKey="graph">
                <Suspense fallback={<Spinner />}>
                  <DashboardGraph data={graphData} />
                </Suspense>
              </Tab>
              {/* ... other tabs */}
            </Tabs>
          </Col>
        </Row>
      </Container>
    </div>
  );
};

export default Dashboard;
```

---

### 2. useDashboardData Hook - ~200 lines

**Responsibility**: All data fetching logic extracted from Dashboard

```jsx
// hooks/useDashboardData.js
import { useState, useCallback, useEffect, useRef } from 'react';
import apiService from '../services/apiService';

export const useDashboardData = ({ filters, selectedStations }) => {
  const [graphData, setGraphData] = useState([]);
  const [tableData, setTableData] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const abortControllerRef = useRef(null);
  const isFetchingRef = useRef(false);
  const debounceTimerRef = useRef(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);

  const fetchData = useCallback(async () => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      setLoading(true);
      setError(null);

      const params = {
        start_date: filters.startDate,
        end_date: filters.endDate,
        data_source: filters.dataType,
        include_outliers: filters.showAnomalies ? 'true' : 'false'
      };

      const stationsToFetch = selectedStations.includes('All Stations')
        ? stations.filter(s => s !== 'All Stations')
        : selectedStations;

      const data = await apiService.getDataBatch(stationsToFetch, params);

      setGraphData(data);
      setTableData(sortData(data, 'desc'));
      setStats(calculateStats(data));

    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message);
      }
    } finally {
      setLoading(false);
      isFetchingRef.current = false;
    }
  }, [filters, selectedStations]);

  // Debounced fetch
  useEffect(() => {
    if (selectedStations.length === 0) return;

    clearTimeout(debounceTimerRef.current);
    const debounceTime = isInitialLoad ? 300 : 1500;

    debounceTimerRef.current = setTimeout(() => {
      fetchData();
      if (isInitialLoad) setIsInitialLoad(false);
    }, debounceTime);

    return () => clearTimeout(debounceTimerRef.current);
  }, [fetchData, selectedStations, isInitialLoad]);

  return { graphData, tableData, stats, loading, error, refetch: fetchData };
};
```

---

### 3. DashboardGraph Component - ~300 lines

**Responsibility**: Plotly chart rendering, point selection, fullscreen

```jsx
// Dashboard/DashboardGraph.js
import React, { useMemo, useCallback, useState, useRef, memo } from 'react';
import { usePlotConfig } from '../../hooks/usePlotConfig';

const Plot = lazy(() => import('react-plotly.js'));

const DashboardGraph = memo(({
  data,
  predictions,
  filters,
  selectedStations,
  onPointSelect
}) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedPoints, setSelectedPoints] = useState([]);
  const plotRef = useRef(null);

  const { traces, layout, config } = usePlotConfig({
    data,
    predictions,
    filters,
    selectedStations,
    selectedPoints,
    isFullscreen
  });

  const handlePlotClick = useCallback((event) => {
    if (!event.points?.[0]) return;

    const point = event.points[0];
    const pointData = {
      x: point.x,
      y: point.y,
      station: point.data.name,
      timestamp: point.x
    };

    setSelectedPoints(prev => {
      if (prev.length >= 2) {
        return [prev[1], pointData];
      }
      return [...prev, pointData];
    });

    onPointSelect?.(pointData);
  }, [onPointSelect]);

  return (
    <div className={isFullscreen ? 'fullscreen-graph' : ''}>
      <div className="graph-toolbar">
        <Button onClick={() => setIsFullscreen(!isFullscreen)}>
          {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
        </Button>
        <Button onClick={exportGraph}>Export</Button>
      </div>

      <Suspense fallback={<Spinner />}>
        <Plot
          ref={plotRef}
          data={traces}
          layout={layout}
          config={config}
          onClick={handlePlotClick}
          useResizeHandler
        />
      </Suspense>

      {selectedPoints.length === 2 && (
        <DeltaDisplay points={selectedPoints} />
      )}
    </div>
  );
});

export default DashboardGraph;
```

---

### 4. usePlotConfig Hook - ~250 lines

**Responsibility**: All Plotly configuration logic (extracted createPlot)

```jsx
// hooks/usePlotConfig.js
import { useMemo } from 'react';
import { generateConnectionShapes } from '../utils/lineDrawingUtils';

export const usePlotConfig = ({
  data,
  predictions,
  filters,
  selectedStations,
  selectedPoints,
  isFullscreen
}) => {
  const traces = useMemo(() => {
    if (!data?.length) return [];

    const result = [];

    // Main data traces
    if (selectedStations.includes('All Stations')) {
      const groups = groupByStation(data);
      Object.entries(groups).forEach(([station, stationData]) => {
        result.push(createSeaLevelTrace(station, stationData));
      });
    } else {
      selectedStations.forEach(station => {
        const stationData = data.filter(d => d.Station === station);
        if (stationData.length) {
          result.push(createSeaLevelTrace(station, stationData));
        }
      });
    }

    // Anomalies
    if (filters.showAnomalies) {
      const anomalies = data.filter(d => d.anomaly === -1);
      if (anomalies.length) {
        result.push(createAnomalyTrace(anomalies));
      }
    }

    // Predictions
    if (predictions) {
      Object.entries(predictions).forEach(([station, pred]) => {
        if (pred.kalman?.length) {
          result.push(createPredictionTrace(station, pred.kalman, 'Kalman'));
        }
        // ... ensemble, arima traces
      });
    }

    // Selected points
    if (selectedPoints.length) {
      result.push(createSelectedPointsTrace(selectedPoints));
    }

    return result;
  }, [data, predictions, filters, selectedStations, selectedPoints]);

  const layout = useMemo(() => ({
    title: { text: 'Sea Level Over Time', font: { color: 'white' } },
    plot_bgcolor: '#142950',
    paper_bgcolor: '#142950',
    xaxis: { title: 'Date/Time', color: 'white', gridcolor: '#1e3c72' },
    yaxis: { title: 'Sea Level (m)', color: 'white', gridcolor: '#1e3c72' },
    shapes: generateConnectionShapes(selectedPoints),
    showlegend: true,
    uirevision: 'constant'
  }), [selectedPoints, isFullscreen]);

  const config = useMemo(() => ({
    displayModeBar: true,
    displaylogo: false,
    responsive: true
  }), []);

  return { traces, layout, config };
};

// Helper functions
const createSeaLevelTrace = (station, data) => ({
  x: data.map(d => d.Tab_DateTime),
  y: data.map(d => d.Tab_Value_mDepthC1),
  type: 'scattergl',
  mode: 'lines',
  name: station,
  line: { width: 2, shape: 'spline', smoothing: 1.3 }
});
```

---

### 5. useFilters Hook - ~80 lines

**Responsibility**: Filter state management

```jsx
// hooks/useFilters.js
import { useState, useMemo, useCallback } from 'react';

const defaultFilters = {
  startDate: (() => {
    const d = new Date();
    d.setDate(d.getDate() - 3);
    return d;
  })(),
  endDate: new Date(),
  dataType: 'default',
  showAnomalies: false,
  trendline: 'none',
  analysisType: 'none',
  predictionModels: [],
  forecastHours: 240
};

export const useFilters = () => {
  const [filters, setFilters] = useState(defaultFilters);

  const filterValues = useMemo(() => ({
    startDate: filters.startDate.toISOString().split('T')[0],
    endDate: filters.endDate.toISOString().split('T')[0],
    dataType: filters.dataType,
    showAnomalies: filters.showAnomalies
  }), [filters]);

  const updateFilter = useCallback((key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  }, []);

  const updateDateRange = useCallback((start, end) => {
    setFilters(prev => ({ ...prev, startDate: start, endDate: end }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(defaultFilters);
  }, []);

  return {
    filters,
    filterValues,
    setFilters,
    updateFilter,
    updateDateRange,
    resetFilters
  };
};
```

---

## Migration Strategy

### Phase 1: Extract Hooks (Low Risk)
1. Create `useFilters.js` - extract filter state
2. Create `useDashboardData.js` - extract data fetching
3. Create `usePlotConfig.js` - extract createPlot logic
4. Test: Verify Dashboard still works with new hooks

### Phase 2: Extract Components (Medium Risk)
5. Create `DashboardHeader.js`
6. Create `DashboardStats.js`
7. Create `DashboardFilters.js`
8. Test each extraction individually

### Phase 3: Heavy Components (Higher Risk)
9. Create `DashboardGraph.js` with point selection
10. Create `DashboardTable.js` with pagination
11. Create `DashboardMap.js` with tab logic
12. Final testing and cleanup

---

## State Management Decision

### Option A: Keep useState (Recommended)
**Pros:**
- Minimal changes to existing logic
- No new dependencies
- React's built-in solution

**Cons:**
- Props drilling for deep components

### Option B: React Context
**Pros:**
- Avoid props drilling
- Centralized state

**Cons:**
- Can cause unnecessary re-renders
- More boilerplate

### Option C: Zustand/Jotai
**Pros:**
- Simple API
- Good performance
- Selective re-renders

**Cons:**
- New dependency
- Team learning curve

**Recommendation:** Start with Option A (useState + custom hooks). Only add Context or Zustand if props drilling becomes problematic.

---

## Performance Considerations

### Before Refactoring
```
Dashboard.js renders → All 2700 lines re-evaluated
Any state change → Entire component re-renders
useMemo helps but still complex
```

### After Refactoring
```
Parent change → Only parent re-renders
Child with React.memo → Skipped if props same
Each hook → Isolated state management
```

### Expected Improvements
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Re-render scope | Full component | Targeted components | 60-70% less work |
| Bundle splitting | Not possible | Lazy load tabs | 30% smaller initial |
| Time to fix bugs | High (find in 2700 lines) | Low (focused files) | 80% faster |

---

## File Size Estimates

| File | Lines | Responsibility |
|------|-------|----------------|
| Dashboard/index.js | 300 | Orchestration |
| DashboardGraph.js | 300 | Chart + point selection |
| DashboardTable.js | 150 | Table + pagination |
| DashboardFilters.js | 200 | Filter panel |
| DashboardMap.js | 150 | Map tabs |
| DashboardStats.js | 80 | Stats cards |
| DashboardHeader.js | 50 | Header |
| useDashboardData.js | 200 | Data fetching |
| usePlotConfig.js | 250 | Plot configuration |
| useFilters.js | 80 | Filter state |
| useStations.js | 60 | Station state |
| **Total** | **1820** | vs 2700 original |

---

## Testing Plan

### Unit Tests (New)
```javascript
// hooks/useDashboardData.test.js
describe('useDashboardData', () => {
  it('fetches data on mount', async () => {...});
  it('debounces rapid filter changes', () => {...});
  it('cancels previous requests', () => {...});
  it('handles errors gracefully', () => {...});
});
```

### Integration Tests
```javascript
// Dashboard.test.js
describe('Dashboard', () => {
  it('renders all components', () => {...});
  it('updates graph when filters change', () => {...});
  it('shows loading state', () => {...});
});
```

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing features | Medium | High | Incremental migration, thorough testing |
| Performance regression | Low | Medium | Benchmark before/after each phase |
| Merge conflicts | Medium | Low | Refactor in feature branch |
| Incomplete migration | Low | Medium | Clear milestones, can pause at any phase |

---

## Timeline Estimate

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Phase 1 | Extract hooks | 4-6 hours |
| Phase 2 | Extract simple components | 3-4 hours |
| Phase 3 | Extract heavy components | 6-8 hours |
| Testing | Comprehensive testing | 4 hours |
| **Total** | | **17-22 hours** |

---

## Conclusion

This refactoring plan transforms a 2700-line monolithic component into a modular, maintainable architecture while:

1. **Preserving all existing functionality** - No features removed
2. **Maintaining data accuracy** - Same data flows, just organized differently
3. **Following low-risk approach** - Incremental migration with testing at each step

The recommended approach is to **start with Phase 1 (hooks extraction)** which provides immediate benefits with minimal risk, then proceed to component extraction based on available time and priorities.

---

*Document created: November 23, 2025*
*Status: READY FOR REVIEW - Do not implement without approval*
