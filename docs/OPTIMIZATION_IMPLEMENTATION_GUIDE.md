# Performance Optimization Implementation Guide

## Quick Reference: Priority Order

| Priority | Optimization | Time to Implement | Impact |
|----------|--------------|-------------------|--------|
| **P1** | Reduce initial debounce | 30 mins | -1.7 seconds |
| **P2** | Parallel initial API calls | 1 hour | -400ms |
| **P3** | Add React.memo to components | 1 hour | -100ms re-render |
| **P4** | Merge outliers with data | 2 hours | -800ms |
| **P5** | Tune aggregation thresholds | 2 hours | -1-2 seconds, -60% payload |

---

## P1: Reduce Initial Debounce Time

### File: `frontend/src/components/Dashboard.js`

**Location:** Line 784-802

**Current Code:**
```javascript
useEffect(() => {
  if (stations.length > 0 && selectedStations.length > 0) {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      if (isMounted.current && !isFetchingRef.current) {
        fetchData();
      }
    }, 2000); // ← 2 second delay on EVERY load
```

**Optimized Code:**
```javascript
// Add state at top of component (around line 51)
const [isInitialLoad, setIsInitialLoad] = useState(true);

// Replace the useEffect (line 784-802)
useEffect(() => {
  if (stations.length > 0 && selectedStations.length > 0) {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Fast initial load, slower for user filter changes
    const debounceTime = isInitialLoad ? 300 : 1500;

    debounceTimerRef.current = setTimeout(() => {
      if (isMounted.current && !isFetchingRef.current) {
        fetchData();
        if (isInitialLoad) {
          setIsInitialLoad(false);
        }
      }
    }, debounceTime);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }
}, [fetchData, stations.length, selectedStations.length, isInitialLoad]);
```

**Expected Result:** Initial data appears 1.7 seconds faster

---

## P2: Parallel Initial API Calls

### File: `frontend/src/components/Dashboard.js`

**Current Pattern (lines 171-218):**
- fetchStations() runs first
- fetchForecastData() runs in separate useEffect
- Data fetch waits for debounce

**Optimized Pattern:**
```javascript
// Replace the two separate useEffects with a single parallel load
useEffect(() => {
  const loadInitialData = async () => {
    if (stationsFetched) return;

    setLoading(true);
    try {
      // Run both in parallel
      const [stationsResult, forecastResult] = await Promise.all([
        apiService.getStations().catch(err => {
          console.error('Stations fetch failed:', err);
          return { stations: ['All Stations', 'Acre', 'Ashdod', 'Ashkelon', 'Eilat', 'Haifa', 'Yafo'] };
        }),
        fetch(`${API_BASE_URL}/api/sea-forecast`)
          .then(r => r.ok ? r.json() : null)
          .catch(() => null)
      ]);

      setStations(stationsResult.stations || []);
      setForecastData(forecastResult);
      setStationsFetched(true);

    } catch (error) {
      console.error('Initial load error:', error);
    } finally {
      setLoading(false);
    }
  };

  loadInitialData();
}, []); // Only run once on mount

// Remove the separate forecastData useEffect (lines 200-218)
```

**Expected Result:** Saves ~400ms by running requests in parallel

---

## P3: Add React.memo to Child Components

### Files to Modify:

**1. StatsCard.js**
```javascript
// At the end of the file, change:
export default StatsCard;

// To:
export default React.memo(StatsCard);
```

**2. WarningsCard.js**
```javascript
export default React.memo(WarningsCard);
```

**3. DateRangePicker.js**
```javascript
export default React.memo(DateRangePicker);
```

**4. CustomDropdown.js**
```javascript
export default React.memo(CustomDropdown);
```

**5. DeltaDisplay.js**
```javascript
export default React.memo(DeltaDisplay);
```

**Why this works:** These components receive props that rarely change. React.memo prevents re-renders when parent re-renders but props are identical.

**Expected Result:** ~100ms faster re-renders on filter changes

---

## P4: Merge Outliers with Data Endpoint

### Backend: `backend/lambdas/get_data/main.py`

**Add parameter handling (in lambda_handler, around line 603):**
```python
def lambda_handler(event, context):
    try:
        params = event.get('queryStringParameters') or {}
        station = params.get('station')
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        data_source = params.get('data_source', 'default')
        show_anomalies = params.get('show_anomalies', 'false').lower() == 'true'
        include_outliers = params.get('include_outliers', 'false').lower() == 'true'  # NEW
```

**Modify load_data_from_db_optimized (around line 308):**
```python
# After df = detect_anomalies(df) on line 309
if include_outliers and not df.empty:
    # Import and apply Southern Baseline Rules
    try:
        from shared.southern_baseline_rules import detect_southern_baseline_outliers
        df = detect_southern_baseline_outliers(df)
        logger.info(f"[OUTLIERS] Applied Southern Baseline Rules: {sum(df['anomaly'] == -1)} outliers")
    except ImportError:
        logger.warning("Southern Baseline Rules not available")
```

### Frontend: `frontend/src/components/Dashboard.js`

**Modify fetchData (around line 519):**
```javascript
const params = {
  start_date: filterValues.startDate,
  end_date: filterValues.endDate,
  data_source: filterValues.dataType,
  include_outliers: filterValues.showAnomalies ? 'true' : 'false'  // NEW
};

// Then REMOVE the separate outliers fetch block (lines 546-693)
```

**Expected Result:** Eliminates 500-800ms separate outliers request

---

## P5: Tune Aggregation Thresholds

### File: `backend/lambdas/get_data/main.py`

**Current (line 63-87):**
```python
def calculate_aggregation_level(start_date, end_date):
    if days <= 30:
        return 'raw', None      # 43,200 rows per station!
    elif days <= 90:
        return 'hourly', '1 hour'
```

**Optimized:**
```python
def calculate_aggregation_level(start_date, end_date):
    """Determine optimal aggregation level based on date range"""
    if not start_date or not end_date:
        return 'raw', None

    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end_dt - start_dt).days

        # More aggressive aggregation to reduce payload size
        if days <= 3:
            return 'raw', None              # ~4,320 rows/station (manageable)
        elif days <= 7:
            return '5min', '5 minutes'      # ~2,016 rows/station
        elif days <= 14:
            return '15min', '15 minutes'    # ~1,344 rows/station
        elif days <= 30:
            return 'hourly', '1 hour'       # ~720 rows/station
        elif days <= 90:
            return 'hourly', '3 hours'      # ~720 rows/station
        elif days <= 180:
            return 'daily', '1 day'         # ~180 rows/station
        else:
            return 'weekly', '1 week'       # ~52 rows/station
    except Exception as e:
        logger.warning(f"Date calculation error: {e}")
        return 'raw', None
```

**Add 5-minute and 15-minute aggregation queries:**
```python
elif agg_level == '5min':
    sql_query = '''
        SELECT
            DATE_TRUNC('hour', m."Tab_DateTime") +
            INTERVAL '5 minutes' * FLOOR(EXTRACT(MINUTE FROM m."Tab_DateTime")::int / 5) as "Tab_DateTime",
            l."Station",
            AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
            AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
            COUNT(*) as "RecordCount"
        FROM "Monitors_info2" m
        JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
        WHERE 1=1
    '''
elif agg_level == '15min':
    sql_query = '''
        SELECT
            DATE_TRUNC('hour', m."Tab_DateTime") +
            INTERVAL '15 minutes' * FLOOR(EXTRACT(MINUTE FROM m."Tab_DateTime")::int / 15) as "Tab_DateTime",
            l."Station",
            AVG(CAST(m."Tab_Value_mDepthC1" AS FLOAT)) as "Tab_Value_mDepthC1",
            AVG(CAST(m."Tab_Value_monT2m" AS FLOAT)) as "Tab_Value_monT2m",
            COUNT(*) as "RecordCount"
        FROM "Monitors_info2" m
        JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
        WHERE 1=1
    '''
```

**Expected Result:**
- 7-day query: 2MB → 400KB (80% reduction)
- 30-day query: 8MB → 700KB (91% reduction)

---

## Verification Checklist

After implementing each optimization, verify:

- [ ] **P1:** Initial data appears within 1 second of page load
- [ ] **P2:** Network tab shows parallel requests
- [ ] **P3:** React DevTools shows fewer re-renders
- [ ] **P4:** No separate `/api/outliers` request when anomalies enabled
- [ ] **P5:** Network payload reduced (check Response size in DevTools)

---

## Rollback Instructions

If any optimization causes issues:

**P1/P2/P3:** Simply revert the code changes in the affected files

**P4:** Add back the separate outliers fetch in Dashboard.js (lines 546-693)

**P5:** Revert to original `calculate_aggregation_level` function

---

## Monitoring After Deployment

1. Check `/api/metrics` endpoint for:
   - Cache hit rate (should increase)
   - Slow query count (should decrease)

2. Check browser DevTools:
   - Initial load time in Performance tab
   - Payload sizes in Network tab

3. User feedback:
   - Does the dashboard feel faster?
   - Are there any missing features?
