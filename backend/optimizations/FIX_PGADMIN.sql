-- ============================================================
-- SEATIDES FIX - FOR PGADMIN (Run each statement separately!)
-- ============================================================
-- INSTRUCTIONS:
-- 1. Select ONLY the first CREATE INDEX statement
-- 2. Press F5 or click Execute
-- 3. Wait for it to complete (may take 5-10 minutes)
-- 4. Move to the next CREATE INDEX statement
-- 5. Repeat until all are done
-- ============================================================

-- Configure memory (run this first)
SET work_mem = '512MB';
SET maintenance_work_mem = '1GB';

-- ============================================================
-- INDEX 1/4: JOIN performance (MOST CRITICAL!)
-- ============================================================
-- SELECT THIS LINE AND THE LINE BELOW, THEN EXECUTE (F5)
CREATE INDEX CONCURRENTLY idx_monitors_tag_datetime
ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime");

-- Wait for completion, then continue...

-- ============================================================
-- INDEX 2/4: Filter non-NULL values
-- ============================================================
-- SELECT THIS LINE AND THE LINE BELOW, THEN EXECUTE (F5)
CREATE INDEX CONCURRENTLY idx_monitors_datetime_value
ON "Monitors_info2" ("Tab_DateTime", "Tab_Value_mDepthC1")
WHERE "Tab_Value_mDepthC1" IS NOT NULL;

-- Wait for completion, then continue...

-- ============================================================
-- INDEX 3/4: SeaTides query performance
-- ============================================================
-- SELECT THIS LINE AND THE LINE BELOW, THEN EXECUTE (F5)
CREATE INDEX CONCURRENTLY idx_seatides_date_station
ON "SeaTides" ("Date", "Station");

-- Wait for completion, then continue...

-- ============================================================
-- INDEX 4/4: Locations JOIN
-- ============================================================
-- SELECT THIS LINE AND THE LINE BELOW, THEN EXECUTE (F5)
CREATE INDEX CONCURRENTLY idx_locations_tag
ON "Locations" ("Tab_TabularTag");

-- Wait for completion, then continue...

-- ============================================================
-- FINAL STEP: Update statistics
-- ============================================================
-- You CAN run all three of these together
ANALYZE "Monitors_info2";
ANALYZE "SeaTides";
ANALYZE "Locations";

-- ============================================================
-- DONE! Now test the refresh time
-- ============================================================
-- Run this to test:
-- \timing
-- REFRESH MATERIALIZED VIEW "SeaTides";
-- ============================================================
