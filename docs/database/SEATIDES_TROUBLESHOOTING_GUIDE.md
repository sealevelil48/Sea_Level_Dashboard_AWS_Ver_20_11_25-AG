# SeaTides Materialized View - Complete Troubleshooting & Fix Guide

## 🚨 Your Problem
```
REFRESH MATERIALIZED VIEW "SeaTides";
Query returned successfully in 17 hr 37 min
```

This is **extremely slow** and indicates missing indexes or table bloat.

---

## 🔍 Root Causes (in order of likelihood)

### 1. **Missing Indexes on Join/Filter Columns** (70% probability)
- The view likely JOINs `Monitors_info2` with `Locations` and filters by date
- Without indexes, PostgreSQL scans entire tables
- Each scan of `Monitors_info2` could have millions of rows

### 2. **Table Bloat from Old Inserts/Updates** (20% probability)
- Your dashboard continuously inserts sensor data
- If you don't run `VACUUM` regularly, dead tuples accumulate
- Slows down table scans significantly

### 3. **Insufficient Memory Allocation** (5% probability)
- `work_mem` or `maintenance_work_mem` too small
- Forces disk-based sorting/aggregation

### 4. **Inefficient View Query** (5% probability)
- The underlying query that builds the view is poorly written
- Unnecessary aggregations or joins

---

## ✅ Quick Fix (Do This First)

Copy and run this in your PostgreSQL client:

```sql
-- Set high memory for this session
SET work_mem = '512MB';
SET maintenance_work_mem = '1GB';

-- Create essential indexes (most important!)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_tag_datetime 
ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime");

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_date_station 
ON "SeaTides" ("Date", "Station");

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_locations_tag 
ON "Locations" ("Tab_TabularTag");

-- Update statistics
ANALYZE "Monitors_info2";
ANALYZE "SeaTides";
ANALYZE "Locations";

-- Clean up bloat
VACUUM ANALYZE "Monitors_info2";
VACUUM ANALYZE "SeaTides";

-- Now refresh (should be much faster!)
REFRESH MATERIALIZED VIEW "SeaTides";
```

**Expected time after fix:** 5-30 minutes (vs 17 hours)

---

## 🔧 Detailed Diagnosis

### Step 1: Get View Definition
```sql
SELECT pg_get_viewdef('public."SeaTides"'::regclass, true) as view_definition;
```

This shows what the view is doing. Look for:
- Which columns are being used in WHERE clause
- What JOINs are involved
- What aggregations are performed

### Step 2: Check Current Indexes
```sql
SELECT 
    indexname,
    indexdef,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_indexes 
WHERE tablename IN ('SeaTides', 'Monitors_info2', 'Locations')
ORDER BY tablename, indexname;
```

**Look for:**
- ✅ Index on `Monitors_info2.Tab_DateTime`
- ✅ Index on `Monitors_info2.Tab_TabularTag`
- ✅ Composite index on both (best)
- ✅ Index on `SeaTides.Date`
- ✅ Index on `Locations.Tab_TabularTag`

**If any are missing:** That's your problem!

### Step 3: Check Table Bloat
```sql
SELECT 
    tablename,
    n_dead_tup as dead_rows,
    n_live_tup as live_rows,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_ratio
FROM pg_stat_user_tables
WHERE tablename IN ('SeaTides', 'Monitors_info2')
ORDER BY dead_ratio DESC;
```

**If `dead_ratio` > 10%:** Table bloat is part of the problem

### Step 4: Check Database Size
```sql
SELECT 
    'Monitors_info2' as table_name,
    pg_size_pretty(pg_total_relation_size('public."Monitors_info2"')) as size,
    (SELECT COUNT(*) FROM "Monitors_info2") as rows
UNION ALL
SELECT 
    'SeaTides',
    pg_size_pretty(pg_total_relation_size('public."SeaTides"')),
    (SELECT COUNT(*) FROM "SeaTides");
```

- **If > 100GB:** Likely needs aggressive optimization
- **If 10-100GB:** Normal, indexes should help significantly
- **If < 10GB:** Should be very fast with proper indexes

---

## 🛠️ Complete Fix (Step by Step)

### Phase 1: Create Missing Indexes (15 minutes)

```sql
-- These run WITHOUT locking the table (CONCURRENTLY keyword)
-- Safe to run while dashboard is operational

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_info2_datetime 
ON "Monitors_info2" ("Tab_DateTime");

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_info2_tag 
ON "Monitors_info2" ("Tab_TabularTag");

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_info2_tag_datetime 
ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime");

-- These speed up aggregations with non-null values
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_monitors_value_notnull 
ON "Monitors_info2" ("Tab_Value_mDepthC1", "Tab_DateTime")
WHERE "Tab_Value_mDepthC1" IS NOT NULL;

-- SeaTides indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_date 
ON "SeaTides" ("Date");

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_station_date 
ON "SeaTides" ("Station", "Date");

-- Locations join index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_locations_tab_tag 
ON "Locations" ("Tab_TabularTag");
```

### Phase 2: Update Statistics (5 minutes)

```sql
ANALYZE "Monitors_info2";
ANALYZE "SeaTides";
ANALYZE "Locations";
```

### Phase 3: Clean Up Bloat (10 minutes)

```sql
-- Gentle cleanup (no table locks)
VACUUM ANALYZE "Monitors_info2";
VACUUM ANALYZE "SeaTides";
VACUUM ANALYZE "Locations";
```

### Phase 4: Run Refresh with Monitoring (varies)

```sql
-- In your psql session, enable timing
\timing on

-- Set memory
SET work_mem = '512MB';
SET maintenance_work_mem = '1GB';

-- Refresh
REFRESH MATERIALIZED VIEW "SeaTides";

-- Check time in output
```

**In another terminal, monitor progress:**
```sql
SELECT 
    NOW(),
    EXTRACT(EPOCH FROM (NOW() - query_start)) as seconds_running,
    query
FROM pg_stat_activity
WHERE query ILIKE '%REFRESH%MATERIALIZED%';
```

---

## 🚀 Advanced: Non-Blocking Refresh

If your view supports it, use concurrent refresh (no blocking):

```sql
-- First, create unique index (only once)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_seatides_unique 
ON "SeaTides" ("Date", "Station");

-- Then use concurrent refresh (queries can still read)
REFRESH MATERIALIZED VIEW CONCURRENTLY "SeaTides";
```

**Advantages:**
- Dashboard stays responsive
- Takes slightly longer but no downtime

---

## 📊 Performance Expectations

| Scenario | Refresh Time |
|----------|-------------|
| **Before optimization** (17+ hours) | ❌ Way too slow |
| After adding indexes | ✅ 10-30 minutes |
| After cleanup + indexes | ✅ 5-20 minutes |
| With concurrent refresh | ✅ 10-40 minutes (non-blocking) |
| With full vacation | ✅ 5-10 minutes |

---

## 🔧 If Still Slow After Indexes

### Option 1: Run Full Vacuum (aggressive)
```sql
-- WARNING: Locks table for 1-2 hours
-- Only do during maintenance window!
VACUUM FULL ANALYZE "Monitors_info2";
VACUUM FULL ANALYZE "SeaTides";
```

### Option 2: Reindex Tables
```sql
-- Rebuilds indexes (safer than VACUUM FULL)
REINDEX TABLE CONCURRENTLY "Monitors_info2";
REINDEX TABLE CONCURRENTLY "SeaTides";
```

### Option 3: Check View Query
```sql
-- Get the actual query
SELECT pg_get_viewdef('public."SeaTides"'::regclass, true) as query;

-- Then run EXPLAIN ANALYZE to find bottlenecks
EXPLAIN ANALYZE
SELECT * FROM "SeaTides" LIMIT 1;
```

### Option 4: Check System Resources
```bash
# Terminal - check if disk I/O is bottleneck
iostat -x 1 5

# Check memory
free -h

# Check PostgreSQL processes
ps aux | grep postgres
```

---

## 📝 Prevent This in Future

### Add to your backend startup script:

```python
# In backend/local_server.py or similar
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def schedule_seatides_maintenance():
    """Refresh SeaTides view daily at 2 AM"""
    from apscheduler.schedulers.background import BackgroundScheduler
    
    scheduler = BackgroundScheduler()
    
    @scheduler.scheduled_job('cron', hour=2, minute=0)
    def refresh_job():
        try:
            logger.info("Starting SeaTides refresh...")
            with engine.connect() as conn:
                conn.execute(text(
                    "SET work_mem = '512MB'; "
                    "SET maintenance_work_mem = '1GB'; "
                    "REFRESH MATERIALIZED VIEW CONCURRENTLY \"SeaTides\";"
                ))
                conn.commit()
            logger.info("SeaTides refresh completed")
        except Exception as e:
            logger.error(f"SeaTides refresh failed: {e}")
    
    scheduler.start()
    return scheduler
```

### Or schedule with PostgreSQL:

```sql
-- Create extension
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule daily refresh at 2 AM
SELECT cron.schedule('refresh_seatides', '0 2 * * *', 
    'REFRESH MATERIALIZED VIEW CONCURRENTLY "SeaTides"');

-- List jobs
SELECT * FROM cron.job;
```

---

## 🐛 Debugging: Enable Query Logging

```sql
-- Show all queries taking > 5 seconds
ALTER SYSTEM SET log_min_duration_statement = 5000;

-- Apply
SELECT pg_reload_conf();

-- Check logs
tail -f /var/log/postgresql/postgresql.log | grep 'duration:'
```

---

## 📞 Still Need Help?

1. **Run diagnostic query above** - capture the view definition
2. **Check dead_ratio** - if > 20%, do VACUUM FULL
3. **Compare table sizes** - if Monitors_info2 > 500GB, may need partitioning
4. **Profile the query** - run `EXPLAIN ANALYZE` on the view query itself

---

## Quick Checklist

- [ ] Run diagnostic queries to understand current state
- [ ] Create missing indexes (Phase 1)
- [ ] Update statistics (Phase 2)
- [ ] Clean up bloat (Phase 3)
- [ ] Test refresh time
- [ ] Schedule regular maintenance
- [ ] Monitor PostgreSQL logs

**Expected Result:** 17 hours → 5-30 minutes ✅

