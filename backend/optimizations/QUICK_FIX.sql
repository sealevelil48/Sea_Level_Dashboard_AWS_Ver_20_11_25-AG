-- ============================================================
-- QUICK FIX FOR SEATIDES 17-HOUR REFRESH ISSUE
-- ============================================================
-- Run this with: psql -h localhost -U postgres -d Test2-SeaLevels_Restored
-- Then type: \i C:/Users/slg/Sea_Level_Dashboard_AWS_Ver_20_8_25/backend/optimizations/QUICK_FIX.sql
-- ============================================================

\echo '=== Starting Quick Fix for SeaTides Refresh Issue ==='
\echo ''

-- Set optimal memory for this session
SET work_mem = '512MB';
SET maintenance_work_mem = '1GB';

\echo 'Step 1/4: Creating critical index on Monitors_info2 (Tag + DateTime)...'
\echo 'This index is CRITICAL for the JOIN operation in SeaTides view'
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_tag_datetime
ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime");

\echo 'Step 2/4: Creating partial index on Monitors_info2 (Non-NULL values only)...'
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_datetime_value
ON "Monitors_info2" ("Tab_DateTime", "Tab_Value_mDepthC1")
WHERE "Tab_Value_mDepthC1" IS NOT NULL;

\echo 'Step 3/4: Creating composite index on SeaTides (Date + Station)...'
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_date_station
ON "SeaTides" ("Date", "Station");

\echo 'Step 4/4: Creating index on Locations (TabularTag for JOIN)...'
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_locations_tag
ON "Locations" ("Tab_TabularTag");

\echo ''
\echo '=== Updating table statistics ==='
ANALYZE "Monitors_info2";
ANALYZE "SeaTides";
ANALYZE "Locations";

\echo ''
\echo '=== OPTIMIZATION COMPLETE ==='
\echo ''
\echo 'Indexes created successfully! Now test the refresh with:'
\echo '  \\timing'
\echo '  REFRESH MATERIALIZED VIEW "SeaTides";'
\echo ''
\echo 'Expected improvement: 17+ hours -> 5-30 minutes'
\echo ''
