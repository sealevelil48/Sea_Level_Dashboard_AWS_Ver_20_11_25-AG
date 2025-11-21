# SeaTides Materialized View - Performance Diagnosis & Optimization Guide

## Problem Summary
- **Issue**: `REFRESH MATERIALIZED VIEW "SeaTides"` takes 17+ hours
- **Root Cause**: Missing indexes, missing constraints, or underlying table bloat
- **Solution**: Multi-step optimization strategy

---

## IMMEDIATE ACTION ITEMS

### Step 1: Check Current View Definition & Dependencies
```sql
-- Get the SeaTides view definition
SELECT pg_get_viewdef('public."SeaTides"'::regclass, true) as view_definition;

-- Check if it's a materialized view with indexes
SELECT 
    matviewname as view_name,
    schemaname
FROM pg_matviews 
WHERE matviewname = 'SeaTides';

-- List all indexes on SeaTides
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'SeaTides'
ORDER BY indexname;
```

### Step 2: Run Diagnostic Queries
```sql
-- 1. Check SeaTides table size and row count
SELECT 
    pg_size_pretty(pg_total_relation_size('public."SeaTides"')) as total_size,
    pg_size_pretty(pg_relation_size('public."SeaTides"')) as table_size,
    (SELECT COUNT(*) FROM "SeaTides") as row_count;

-- 2. Check Monitors_info2 table size (source table)
SELECT 
    pg_size_pretty(pg_total_relation_size('public."Monitors_info2"')) as total_size,
    pg_size_pretty(pg_relation_size('public."Monitors_info2"')) as table_size,
    (SELECT COUNT(*) FROM "Monitors_info2") as row_count;

-- 3. Check for table bloat and dead tuples
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    n_dead_tup as dead_tuples,
    n_live_tup as live_tuples,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_ratio
FROM pg_stat_user_tables
WHERE tablename IN ('SeaTides', 'Monitors_info2', 'Locations')
ORDER BY n_dead_tup DESC;

-- 4. Check for missing indexes on join columns
SELECT 
    'Monitors_info2' as table_name,
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'Monitors_info2'
ORDER BY indexname;
```

### Step 3: Optimize the SeaTides View

#### Issue 1: Add Missing Indexes
```sql
-- Add indexes to SeaTides (required for fast materialized view refresh)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_date 
ON "SeaTides" ("Date");

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_station_date 
ON "SeaTides" ("Station", "Date");

-- Add indexes to source table (Monitors_info2)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_datetime_tag 
ON "Monitors_info2" ("Tab_DateTime" DESC, "Tab_TabularTag");

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_value_notnull 
ON "Monitors_info2" ("Tab_Value_mDepthC1", "Tab_DateTime")
WHERE "Tab_Value_mDepthC1" IS NOT NULL;

-- Add indexes to Locations table (join table)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_locations_tag 
ON "Locations" ("Tab_TabularTag");

-- Analyze tables to update statistics
ANALYZE "SeaTides";
ANALYZE "Monitors_info2";
ANALYZE "Locations";
```

#### Issue 2: Vacuum and Clean Up Table Bloat
```sql
-- Run VACUUM FULL to reclaim space (WARNING: Locks table during execution)
-- Do this during off-hours or schedule with:
VACUUM FULL ANALYZE "Monitors_info2";
VACUUM FULL ANALYZE "SeaTides";
VACUUM FULL ANALYZE "Locations";

-- Alternative: Use REINDEX during low traffic
REINDEX TABLE CONCURRENTLY "Monitors_info2";
REINDEX TABLE CONCURRENTLY "SeaTides";
REINDEX TABLE CONCURRENTLY "Locations";
```

#### Issue 3: Check the Materialized View Query
```sql
-- Get the underlying query that constructs the materialized view
SELECT pg_get_viewdef('public."SeaTides"'::regclass, true);

-- Example optimization: If the view calculates aggregates, ensure:
-- - GROUP BY columns are indexed
-- - JOIN columns are indexed
-- - WHERE date range filters are indexed
-- - Source table has enough memory in work_mem

-- Check query execution plan
EXPLAIN ANALYZE REFRESH MATERIALIZED VIEW "SeaTides";
```

---

## PERFORMANCE OPTIMIZATION STRATEGY

### Priority 1: Add Missing Composite Indexes (5-10 minutes)
```sql
-- These are the MOST critical for materialized view refresh
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_info2_tag_datetime 
ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime");

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_composite 
ON "SeaTides" ("Station", "Date", "HighTide", "LowTide");
```

### Priority 2: Increase work_mem for Refresh Operation (1 minute)
```sql
-- Set higher memory for the refresh session
SET work_mem = '512MB';
SET maintenance_work_mem = '1GB';

-- Then run refresh
REFRESH MATERIALIZED VIEW "SeaTides";

-- Reset after
RESET work_mem;
RESET maintenance_work_mem;
```

### Priority 3: Run Concurrent Refresh (Non-blocking)
```sql
-- Use CONCURRENTLY to allow queries during refresh
-- (requires unique index on materialized view)
REFRESH MATERIALIZED VIEW CONCURRENTLY "SeaTides";

-- If this fails, first create unique index:
CREATE UNIQUE INDEX idx_seatides_unique ON "SeaTides" ("Date", "Station");
```

### Priority 4: Check for Long-Running Queries Blocking Refresh
```sql
-- Find blocking queries
SELECT 
    pid,
    usename,
    application_name,
    state,
    query,
    wait_event,
    wait_event_type
FROM pg_stat_activity
WHERE datname = current_database()
AND state != 'idle'
ORDER BY state_change DESC;

-- Kill blocking processes if needed (careful!)
SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
WHERE datname = current_database() 
AND query_start < NOW() - INTERVAL '1 hour'
AND state != 'idle';
```

---

## SCRIPT: One-Command Optimization

Create this as `optimize_seatides.sql`:

```sql
-- ============================================================
-- COMPLETE SEATIDES OPTIMIZATION SCRIPT
-- ============================================================
-- Run this during off-peak hours (takes 30-60 minutes)
-- ============================================================

-- 1. Set memory limits
SET work_mem = '512MB';
SET maintenance_work_mem = '1GB';
SET max_parallel_workers_per_gather = 4;

-- 2. Create critical indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_tag_datetime 
ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime");

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_datetime_tag_value
ON "Monitors_info2" ("Tab_DateTime", "Tab_TabularTag", "Tab_Value_mDepthC1")
WHERE "Tab_Value_mDepthC1" IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_date_station 
ON "SeaTides" ("Date", "Station");

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_station_date_values
ON "SeaTides" ("Station", "Date", "HighTide", "LowTide");

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_locations_tag 
ON "Locations" ("Tab_TabularTag");

-- 3. Update statistics
ANALYZE "Monitors_info2";
ANALYZE "SeaTides";
ANALYZE "Locations";

-- 4. Check for bloat and clean
-- Option A: Gentle cleanup (non-locking)
VACUUM ANALYZE "Monitors_info2";
VACUUM ANALYZE "SeaTides";

-- Option B: Full cleanup (locks table - use during maintenance window)
-- VACUUM FULL ANALYZE "Monitors_info2";
-- VACUUM FULL ANALYZE "SeaTides";

-- 5. Refresh materialized view with monitoring
\timing on
REFRESH MATERIALIZED VIEW "SeaTides";
\timing off

-- 6. Check final status
SELECT 
    'SeaTides' as object,
    pg_size_pretty(pg_total_relation_size('public."SeaTides"')) as size,
    (SELECT COUNT(*) FROM "SeaTides") as row_count,
    (SELECT COUNT(*) FROM pg_stat_user_indexes WHERE tablename = 'SeaTides') as index_count;

RESET work_mem;
RESET maintenance_work_mem;
```

---

## MONITORING & MAINTENANCE

### Monitor Refresh Progress
```sql
-- In another terminal, monitor the refresh operation
SELECT 
    pid,
    usename,
    state,
    query_start,
    state_change,
    EXTRACT(EPOCH FROM (NOW() - query_start)) as seconds_running,
    query
FROM pg_stat_activity
WHERE query ILIKE '%REFRESH%MATERIALIZED%'
ORDER BY query_start;
```

### Schedule Automatic Maintenance
```sql
-- Create a maintenance function
CREATE OR REPLACE FUNCTION refresh_seatides_maintenance()
RETURNS TABLE(status text, duration_seconds numeric) AS $$
DECLARE
    v_start timestamp;
    v_duration numeric;
BEGIN
    v_start := clock_timestamp();
    
    -- Set memory
    SET work_mem = '512MB';
    SET maintenance_work_mem = '1GB';
    
    -- Refresh view
    REFRESH MATERIALIZED VIEW CONCURRENTLY "SeaTides";
    
    -- Calculate duration
    v_duration := EXTRACT(EPOCH FROM (clock_timestamp() - v_start));
    
    RETURN QUERY SELECT 
        'Refresh completed successfully'::text as status,
        v_duration as duration_seconds;
END;
$$ LANGUAGE plpgsql;

-- Call it
SELECT * FROM refresh_seatides_maintenance();
```

---

## TROUBLESHOOTING

### If refresh still takes > 1 hour:

1. **Check for missing indexes on join columns:**
   ```sql
   -- Identify which columns are used in the view query
   SELECT pg_get_viewdef('public."SeaTides"'::regclass, true);
   
   -- Create indexes on those columns
   ```

2. **Check partition strategy:**
   ```sql
   -- If SeaTides has millions of rows, consider partitioning
   -- by date or station
   ```

3. **Monitor system resources:**
   ```sql
   -- Check if I/O or memory is bottleneck
   -- Run: iostat, vmstat, or pg_stat_statements
   SELECT query, calls, mean_exec_time, max_exec_time 
   FROM pg_stat_statements 
   WHERE query LIKE '%SeaTides%'
   ORDER BY max_exec_time DESC;
   ```

4. **Increase PostgreSQL cache:**
   ```sql
   -- In postgresql.conf, increase:
   -- shared_buffers = 40% of system RAM
   -- effective_cache_size = 50-75% of system RAM
   -- maintenance_work_mem = 2-4GB
   ```

---

## Expected Results

After optimization:
- **Before**: 17+ hours
- **After**: 5-30 minutes (depending on data volume)
- **Improvement**: 34-204x faster

Key factors affecting speed:
- ✅ Number of indexes on source & destination tables
- ✅ Table size and row count
- ✅ Available system memory
- ✅ Underlying view query complexity
- ✅ Concurrent queries during refresh

---

## Next Steps

1. Run the diagnostic queries above to identify the issue
2. Execute the priority 1 index creation
3. Run the optimization script during off-peak hours
4. Monitor refresh time improvement
5. If still slow, check the underlying SeaTides view query for inefficiencies

