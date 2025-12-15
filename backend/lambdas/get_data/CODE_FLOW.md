# Code Flow: Always Raw Data Mode

## Request Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway Request                        │
│  GET /data?start_date=2024-01-01&end_date=2024-12-31           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    lambda_handler(event, context)               │
│  - Parse query parameters                                       │
│  - Extract: start_date, end_date, station, show_anomalies      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              load_data_from_db_optimized()                      │
│  - Parse dates with parse_date_parameter()                      │
│  - Call calculate_aggregation_level()  ◄───────────┐           │
└───────────────────────────┬─────────────────────────┼───────────┘
                            │                         │
                            ▼                         │
┌─────────────────────────────────────────────────────┼───────────┐
│        calculate_aggregation_level(start, end)      │           │
│                                                      │           │
│  ╔════════════════════════════════════════════╗    │           │
│  ║  MODIFIED: ALWAYS RETURNS 'raw'            ║    │           │
│  ║  return 'raw', None                        ║    │           │
│  ║  (bypasses all date range logic)           ║    │           │
│  ╚════════════════════════════════════════════╝    │           │
│                                                      │           │
│  Returns: ('raw', None)  ──────────────────────────┘           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              SQL Query Selection (agg_level = 'raw')            │
│                                                                  │
│  if agg_level == 'raw':  ◄──── ALWAYS TRUE NOW                 │
│      sql_query = '''                                            │
│          SELECT                                                 │
│              m."Tab_DateTime",                                  │
│              l."Station",                                       │
│              CAST(m."Tab_Value_mDepthC1" AS FLOAT),            │
│              CAST(m."Tab_Value_monT2m" AS FLOAT)               │
│          FROM "Monitors_info2" m                                │
│          JOIN "Locations" l                                     │
│              ON m."Tab_TabularTag" = l."Tab_TabularTag"        │
│          WHERE DATE(m."Tab_DateTime") >= :start_date           │
│            AND DATE(m."Tab_DateTime") <= :end_date             │
│          ORDER BY "Tab_DateTime" ASC                            │
│      '''                                                        │
│                                                                  │
│  elif agg_level == '5min':   ◄──── NEVER EXECUTED             │
│  elif agg_level == '15min':  ◄──── NEVER EXECUTED             │
│  elif agg_level == 'hourly': ◄──── NEVER EXECUTED             │
│  elif agg_level == 'daily':  ◄──── NEVER EXECUTED             │
│  else: # weekly              ◄──── NEVER EXECUTED             │
│                                                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database Query Execution                     │
│  - Execute raw query (no aggregation)                           │
│  - Fetch ALL 1-minute interval records                          │
│  - No GROUP BY, no DATE_TRUNC                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Data Processing Pipeline                    │
│                                                                  │
│  1. Clean numeric data (clean_numeric_data)                     │
│     - Replace inf/nan values                                    │
│     - Interpolate missing values                                │
│                                                                  │
│  2. Detect anomalies (if show_anomalies=true)                  │
│     - Apply Southern Baseline Rules                             │
│     - Fallback to IQR method                                    │
│                                                                  │
│  3. Clean baseline columns (clean_baseline_columns)             │
│     - Remove internal processing columns                        │
│     - Keep only 'anomaly' field                                 │
│                                                                  │
│  4. Add metadata                                                │
│     - df['aggregation_level'] = 'raw'                          │
│                                                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Cache Storage (Redis)                      │
│  - Generate cache key from parameters                           │
│  - Store processed data                                         │
│  - TTL: 120 seconds for raw data                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Response Formatting                           │
│                                                                  │
│  1. Format datetime columns                                     │
│     - Tab_DateTime: '%Y-%m-%dT%H:%M:%SZ'                       │
│                                                                  │
│  2. Clean numeric columns                                       │
│     - Replace inf/nan with 0                                    │
│                                                                  │
│  3. Convert to JSON                                             │
│     - df.to_dict('records')                                    │
│                                                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      HTTP Response                              │
│                                                                  │
│  Status: 200 OK                                                 │
│  Headers:                                                       │
│    - X-Aggregation-Level: raw                                   │
│    - X-Record-Count: <count>                                    │
│    - Access-Control-Allow-Origin: *                             │
│                                                                  │
│  Body: [                                                        │
│    {                                                            │
│      "Tab_DateTime": "2024-01-01T00:00:00Z",                   │
│      "Station": "Ashdod",                                       │
│      "Tab_Value_mDepthC1": 1.234,                              │
│      "Tab_Value_monT2m": 18.5,                                 │
│      "anomaly": 0                                               │
│    },                                                           │
│    ...                                                          │
│    (thousands of 1-minute records)                              │
│  ]                                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Key Decision Point (MODIFIED)

```
┌──────────────────────────────────────────┐
│  calculate_aggregation_level()           │
│                                           │
│  BEFORE:                                  │
│  ┌────────────────────────────────────┐  │
│  │ if days <= 3:   return 'raw'       │  │
│  │ elif days <= 7: return '5min'      │  │
│  │ elif days <= 14: return '15min'    │  │
│  │ elif days <= 30: return 'hourly'   │  │
│  │ elif days <= 90: return 'hourly'   │  │
│  │ elif days <= 180: return 'daily'   │  │
│  │ else: return 'weekly'              │  │
│  └────────────────────────────────────┘  │
│                                           │
│  AFTER:                                   │
│  ┌────────────────────────────────────┐  │
│  │ return 'raw', None                 │  │
│  │ # Always raw, no conditions        │  │
│  └────────────────────────────────────┘  │
│                                           │
└──────────────────────────────────────────┘
```

## Data Flow Comparison

### BEFORE (Smart Aggregation)

```
Date Range: 365 days (1 year)
    │
    ├─► calculate_aggregation_level()
    │       └─► Returns: 'weekly'
    │
    ├─► SQL Query with DATE_TRUNC('week', ...)
    │       └─► GROUP BY week, station
    │       └─► AVG(Tab_Value_mDepthC1)
    │       └─► COUNT(*) as RecordCount
    │
    └─► Result: ~52 records per station
            └─► Small payload
            └─► Fast response
            └─► Loss of granularity
```

### AFTER (Always Raw)

```
Date Range: 365 days (1 year)
    │
    ├─► calculate_aggregation_level()
    │       └─► Returns: 'raw' ✅
    │
    ├─► SQL Query (no aggregation)
    │       └─► No GROUP BY
    │       └─► Raw Tab_Value_mDepthC1
    │       └─► No RecordCount
    │
    └─► Result: ~525,600 records per station
            └─► Large payload
            └─► Slower response
            └─► Full granularity ✅
```

## Code Execution Paths

### Single Station Request

```
lambda_handler()
    │
    ├─► parse_date_parameter(start_date)
    ├─► parse_date_parameter(end_date)
    │
    └─► load_data_from_db_optimized()
            │
            ├─► calculate_aggregation_level() → 'raw' ✅
            │
            ├─► Build raw SQL query
            │
            ├─► Execute query (all 1-min records)
            │
            ├─► clean_numeric_data()
            │
            ├─► detect_anomalies() [if requested]
            │
            ├─► clean_baseline_columns()
            │
            └─► Return DataFrame
```

### Batch Request (Multiple Stations)

```
lambda_handler_batch()
    │
    ├─► Parse stations list
    ├─► parse_date_parameter(start_date)
    ├─► parse_date_parameter(end_date)
    │
    └─► load_data_batch_optimized()
            │
            ├─► calculate_aggregation_level() → 'raw' ✅
            │
            ├─► Build raw SQL query with "Station = ANY(:stations)"
            │
            ├─► Execute query (all 1-min records for all stations)
            │
            ├─► clean_numeric_data()
            │
            ├─► detect_anomalies() [if requested]
            │
            ├─► clean_baseline_columns()
            │
            └─► Return DataFrame
```

## Cache Flow

```
Request arrives
    │
    ├─► Generate cache key (includes 'raw' aggregation)
    │
    ├─► Check Redis cache
    │       │
    │       ├─► CACHE HIT ✅
    │       │       └─► Return cached data (120s TTL)
    │       │
    │       └─► CACHE MISS
    │               │
    │               ├─► Query database
    │               ├─► Process data
    │               ├─► Store in cache (TTL: 120s)
    │               └─► Return data
    │
    └─► Format and return response
```

## Error Handling Flow

```
Request
    │
    ├─► Try: Parse parameters
    │       └─► Except: Return 500 error
    │
    ├─► Try: Connect to database
    │       └─► Except: Return empty DataFrame → 404
    │
    ├─► Try: Execute SQL query
    │       └─► Except: Log error → Return empty DataFrame → 404
    │
    ├─► Try: Apply anomaly detection
    │       └─► Except: Log warning → Set anomaly=0 (continue)
    │
    └─► Try: Format response
            └─► Except: Return 500 error
```

## Performance Characteristics

### Query Performance
- **Database**: Index on Tab_DateTime → Fast ✅
- **Network**: More data transfer → Slower ⚠️
- **Memory**: Larger DataFrames → Higher usage ⚠️

### Response Time Breakdown

```
Total Response Time = Query + Processing + Serialization + Network

BEFORE (365 days, weekly aggregation):
    Query:         100ms  (52 records)
    Processing:     50ms
    Serialization:  10ms
    Network:        20ms
    ─────────────────────
    TOTAL:        ~180ms  ✅

AFTER (365 days, raw data):
    Query:         500ms  (525,600 records)
    Processing:    300ms
    Serialization: 800ms
    Network:      2000ms
    ─────────────────────
    TOTAL:      ~3,600ms  ⚠️
```

## Data Volume Examples

| Days | Records/Station | JSON Size | Typical Response Time |
|------|----------------|-----------|----------------------|
| 1    | ~1,440         | ~150 KB   | ~200ms              |
| 7    | ~10,080        | ~1 MB     | ~500ms              |
| 30   | ~43,200        | ~4 MB     | ~1,500ms            |
| 90   | ~129,600       | ~12 MB    | ~4,000ms            |
| 365  | ~525,600       | ~50 MB    | ~15,000ms           |

**Note:** Times are approximate and depend on database load, network conditions, and Lambda performance.

---

**Last Updated:** 2025-12-08
