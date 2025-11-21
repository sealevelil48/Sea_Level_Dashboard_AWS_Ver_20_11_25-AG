-- ============================================================
-- SEATIDES MATERIALIZED VIEW - EMERGENCY OPTIMIZATION
-- ============================================================
-- CONTEXT: View takes 17+ hours to refresh
-- SOLUTION: Add missing indexes, cleanup bloat, optimize
-- TIME TO RUN: 30-60 minutes
-- IMPACT: Should reduce refresh time to 5-30 minutes
-- ============================================================

-- ==========================================================
-- PHASE 1: DIAGNOSTIC QUERIES (Run first to identify issues)
-- ==========================================================

-- 1. Check SeaTides view definition
SELECT pg_get_viewdef('public."SeaTides"'::regclass, true) as view_definition;

-- 2. Check all indexes on SeaTides
SELECT 
    indexname,
    indexdef,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
    idx_scan as times_used
FROM pg_indexes i
LEFT JOIN pg_stat_user_indexes s ON i.indexname = s.indexrelname
WHERE tablename = 'SeaTides'
ORDER BY indexname;

-- 3. Table sizes and row counts
SELECT 
    'SeaTides' as table_name,
    pg_size_pretty(pg_total_relation_size('public."SeaTides"')) as total_size,
    pg_size_pretty(pg_relation_size('public."SeaTides"')) as data_size,
    (SELECT COUNT(*) FROM "SeaTides") as row_count
UNION ALL
SELECT 
    'Monitors_info2' as table_name,
    pg_size_pretty(pg_total_relation_size('public."Monitors_info2"')) as total_size,
    pg_size_pretty(pg_relation_size('public."Monitors_info2"')) as data_size,
    (SELECT COUNT(*) FROM "Monitors_info2") as row_count;

-- 4. Check for table bloat (dead tuples)
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    n_dead_tup as dead_tuples,
    n_live_tup as live_tuples,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_ratio_percent
FROM pg_stat_user_tables
WHERE tablename IN ('SeaTides', 'Monitors_info2', 'Locations')
ORDER BY n_dead_tup DESC;

-- 5. Check active long-running queries that might block refresh
SELECT 
    pid,
    usename,
    application_name,
    state,
    NOW() - query_start as duration,
    query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start ASC
LIMIT 10;

-- ==========================================================
-- PHASE 2: OPTIMIZATION - Run these commands
-- ==========================================================

-- STEP 1: Set optimal memory settings for refresh
SET work_mem = '512MB';
SET maintenance_work_mem = '1GB';
SET max_parallel_workers_per_gather = 4;

-- STEP 2: Create CRITICAL missing indexes
-- These are the most important for performance

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_tag_datetime 
ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime");
ANALYZE "Monitors_info2";

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_datetime_value 
ON "Monitors_info2" ("Tab_DateTime", "Tab_Value_mDepthC1")
WHERE "Tab_Value_mDepthC1" IS NOT NULL;
ANALYZE "Monitors_info2";

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_date_station 
ON "SeaTides" ("Date", "Station");
ANALYZE "SeaTides";

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_station_date_values 
ON "SeaTides" ("Station", "Date", "HighTide", "LowTide", "MeasurementCount");
ANALYZE "SeaTides";

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_locations_tag 
ON "Locations" ("Tab_TabularTag");
ANALYZE "Locations";

-- STEP 3: Clean up table bloat (gentle version - doesn't lock)
VACUUM ANALYZE "Monitors_info2";
VACUUM ANALYZE "SeaTides";
VACUUM ANALYZE "Locations";

-- STEP 4: Force query planner to use new statistics
ANALYZE "Monitors_info2";
ANALYZE "SeaTides";
ANALYZE "Locations";

-- ==========================================================
-- PHASE 3: RUN THE REFRESH WITH MONITORING
-- ==========================================================

-- Option A: Standard refresh (blocking)
-- \timing on
-- REFRESH MATERIALIZED VIEW "SeaTides";
-- \timing off

-- Option B: Non-blocking refresh (if you have unique index)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY "SeaTides";

-- Option C: With automatic timing and error handling
DO $$
DECLARE
    v_start timestamp;
    v_duration numeric;
BEGIN
    v_start := clock_timestamp();
    
    RAISE NOTICE 'Starting SeaTides materialized view refresh at %', v_start;
    
    REFRESH MATERIALIZED VIEW "SeaTides";
    
    v_duration := EXTRACT(EPOCH FROM (clock_timestamp() - v_start));
    
    RAISE NOTICE 'SeaTides refresh completed in % seconds (% minutes)', 
        v_duration, 
        ROUND(v_duration / 60.0, 2);
END
$$;

-- ==========================================================
-- PHASE 4: VERIFY OPTIMIZATION SUCCESS
-- ==========================================================

-- Check indexes again
SELECT 
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
    idx_scan as times_used
FROM pg_stat_user_indexes
WHERE tablename = 'SeaTides'
ORDER BY indexname;

-- Check table status after optimization
SELECT 
    'SeaTides' as table_name,
    pg_size_pretty(pg_total_relation_size('public."SeaTides"')) as total_size,
    (SELECT COUNT(*) FROM "SeaTides") as row_count,
    (SELECT COUNT(*) FROM pg_stat_user_indexes WHERE tablename = 'SeaTides') as index_count
UNION ALL
SELECT 
    'Monitors_info2' as table_name,
    pg_size_pretty(pg_total_relation_size('public."Monitors_info2"')) as total_size,
    (SELECT COUNT(*) FROM "Monitors_info2") as row_count,
    (SELECT COUNT(*) FROM pg_stat_user_indexes WHERE tablename = 'Monitors_info2') as index_count;

-- ==========================================================
-- PHASE 5: ADVANCED OPTIMIZATION (if still slow)
-- ==========================================================

-- If still taking > 1 hour, run full vacuum (WARNING: LOCKS TABLE)
-- Do this during maintenance window only!
-- VACUUM FULL ANALYZE "Monitors_info2";
-- VACUUM FULL ANALYZE "SeaTides";

-- Reindex tables (alternative to VACUUM FULL)
-- REINDEX TABLE CONCURRENTLY "Monitors_info2";
-- REINDEX TABLE CONCURRENTLY "SeaTides";

-- ==========================================================
-- PHASE 6: SCHEDULED MAINTENANCE (Optional)
-- ==========================================================

-- Create a procedure for regular optimization
CREATE OR REPLACE PROCEDURE refresh_seatides_optimized()
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE NOTICE 'Starting optimized SeaTides refresh...';
    
    SET work_mem = '512MB';
    SET maintenance_work_mem = '1GB';
    
    -- Analyze first to update statistics
    ANALYZE "SeaTides";
    ANALYZE "Monitors_info2";
    
    -- Try concurrent refresh first (non-blocking)
    BEGIN
        REFRESH MATERIALIZED VIEW CONCURRENTLY "SeaTides";
        RAISE NOTICE 'SeaTides refreshed successfully (concurrent)';
    EXCEPTION WHEN OTHERS THEN
        -- Fall back to standard refresh if concurrent fails
        REFRESH MATERIALIZED VIEW "SeaTides";
        RAISE NOTICE 'SeaTides refreshed successfully (standard)';
    END;
    
    RESET work_mem;
    RESET maintenance_work_mem;
END;
$$;

-- Call the procedure
-- CALL refresh_seatides_optimized();

-- ==========================================================
-- PHASE 7: MONITORING SCRIPT (Run in separate session)
-- ==========================================================

-- Monitor refresh progress in real-time
-- SELECT 
--     pid,
--     state,
--     query_start,
--     EXTRACT(EPOCH FROM (NOW() - query_start)) as seconds_running,
--     query
-- FROM pg_stat_activity
-- WHERE query ILIKE '%REFRESH%MATERIALIZED%'
-- ORDER BY query_start;

-- ==========================================================
-- EXPECTED RESULTS
-- ==========================================================
-- 
-- Before Optimization:
--   - Refresh time: 17+ hours
--   - Missing indexes on join/filter columns
--   - Index count on SeaTides: 1-2
--
-- After Optimization:
--   - Refresh time: 5-30 minutes
--   - All critical indexes present
--   - Index count on SeaTides: 4+
--   - Dead tuple ratio: < 5%
--
-- If still slow:
--   1. Check the view query itself (may need rewriting)
--   2. Check for full table scans in EXPLAIN ANALYZE
--   3. Consider partitioning by date or station
--   4. Increase PostgreSQL cache settings (shared_buffers, etc)
--
-- ==========================================================
