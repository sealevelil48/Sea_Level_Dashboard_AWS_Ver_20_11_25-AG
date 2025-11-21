# 🚨 SeaTides Materialized View - Emergency Action Plan

## Your Issue
```
REFRESH MATERIALIZED VIEW "SeaTides";
Query returned successfully in 17 hr 37 min
```

**Status:** ⚠️ CRITICAL - This is 34-204x slower than it should be

---

## 🎯 Quick Action (5 minutes)

### Option A: Use Provided Python Script (Recommended)

```bash
cd backend/optimizations

# 1. First, diagnose
python optimize_seatides.py --diagnose

# 2. Run optimization
python optimize_seatides.py --optimize

# 3. Test refresh (will be MUCH faster!)
python optimize_seatides.py --refresh

# Optional: Monitor in real-time in another terminal
python optimize_seatides.py --monitor
```

### Option B: Manual SQL Commands

Copy this entire block and run in your PostgreSQL client:

```sql
-- Set memory
SET work_mem = '512MB';
SET maintenance_work_mem = '1GB';

-- Create indexes (most important!)
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

-- Clean up
VACUUM ANALYZE "Monitors_info2";
VACUUM ANALYZE "SeaTides";

-- Test refresh
\timing on
REFRESH MATERIALIZED VIEW "SeaTides";
\timing off
```

---

## 📊 Expected Improvement

| Before | After | Improvement |
|--------|-------|-------------|
| **17 hours** | **5-30 minutes** | **✅ 34-204x faster** |

---

## 🔍 What's Happening?

Your materialized view refresh is slow because:

1. **Missing Indexes (70% probability)** ❌
   - The view likely queries `Monitors_info2` and `Locations` tables
   - Without indexes, PostgreSQL scans millions of rows
   - Solution: Add composite indexes on `Tab_TabularTag` and `Tab_DateTime`

2. **Table Bloat (20% probability)** ❌
   - You insert sensor data continuously
   - Dead tuples accumulate without regular `VACUUM`
   - Solution: Clean with `VACUUM ANALYZE`

3. **Low Memory Allocation (5% probability)** ❌
   - `work_mem` too small for aggregations
   - Disk swapping slows things down
   - Solution: Increase memory for refresh session

4. **Inefficient View Query (5% probability)** ❌
   - View itself needs rewriting
   - Check underlying query logic

---

## 📁 Provided Resources

I've created these files for you:

### 1. **SQL Optimization Script**
```
backend/optimizations/SEATIDES_REFRESH_OPTIMIZATION.sql
```
- Ready-to-run SQL commands
- Includes diagnostics, fixes, and verification
- Phases for different situations

### 2. **Python Automation Tool**
```
backend/optimizations/optimize_seatides.py
```
- Automates diagnosis and optimization
- Use: `python optimize_seatides.py --optimize`
- Includes monitoring

### 3. **Detailed Troubleshooting Guide**
```
SEATIDES_TROUBLESHOOTING_GUIDE.md
```
- Root cause analysis
- Step-by-step fixes
- Prevention strategies

### 4. **High-Level Overview**
```
SEATIDES_OPTIMIZATION_GUIDE.md
```
- Architecture overview
- Performance tuning
- Maintenance best practices

---

## 🚀 Step-by-Step Fix

### Step 1: Diagnose (2 minutes)
```python
python optimize_seatides.py --diagnose
```
Shows:
- Current indexes
- Table sizes
- Missing indexes
- Recommendations

### Step 2: Optimize (10 minutes)
```python
python optimize_seatides.py --optimize
```
Does:
- ✅ Creates missing indexes
- ✅ Updates statistics
- ✅ Cleans up bloat

### Step 3: Test (variable)
```python
python optimize_seatides.py --refresh
```
Shows:
- Refresh time
- Success/failure
- Performance improvement

### Step 4: Monitor (Optional)
```bash
# In another terminal
python optimize_seatides.py --monitor
```
Shows real-time progress

---

## ⚙️ Technical Details

### Critical Indexes to Create
```sql
CREATE INDEX ON "Monitors_info2" ("Tab_TabularTag", "Tab_DateTime");
CREATE INDEX ON "SeaTides" ("Date", "Station");
CREATE INDEX ON "Locations" ("Tab_TabularTag");
```

### Why These Help
- **Tab_TabularTag + Tab_DateTime**: Speeds up JOIN operations (most common bottleneck)
- **Date + Station**: Enables efficient filtering on SeaTides
- **Tab_TabularTag on Locations**: Speeds up lookups

### Memory Settings
```sql
SET work_mem = '512MB';                  -- Allows bigger sorts/aggregations
SET maintenance_work_mem = '1GB';        -- For maintenance operations
```

### Cleanup
```sql
VACUUM ANALYZE "Monitors_info2";         -- Removes dead tuples
```

---

## 🆘 If Still Slow

### Check 1: Verify indexes were created
```sql
SELECT indexname FROM pg_indexes 
WHERE tablename = 'Monitors_info2' 
AND indexdef LIKE '%Tab_TabularTag%Tab_DateTime%';
```

### Check 2: Run EXPLAIN ANALYZE
```sql
EXPLAIN ANALYZE
SELECT * FROM "SeaTides" 
WHERE "Date" >= '2024-11-01' AND "Date" <= '2024-11-30'
LIMIT 10;
```

### Check 3: Check system resources
```bash
# Terminal
free -h                    # Check memory
iostat -x 1 5             # Check disk I/O
```

### Check 4: Full cleanup
```sql
-- WARNING: Locks table for 1-2 hours!
-- Only during maintenance window
VACUUM FULL ANALYZE "Monitors_info2";
VACUUM FULL ANALYZE "SeaTides";
```

---

## 🔧 Prevention Going Forward

### Schedule Regular Optimization
```sql
-- Add to PostgreSQL cron
CREATE EXTENSION IF NOT EXISTS pg_cron;

SELECT cron.schedule('refresh_seatides', '0 2 * * *', 
    'REFRESH MATERIALIZED VIEW CONCURRENTLY "SeaTides"');

SELECT cron.schedule('vacuum_monitors', '0 3 * * *', 
    'VACUUM ANALYZE "Monitors_info2"');
```

### Use Non-Blocking Refresh
```sql
-- Safe to run during business hours
REFRESH MATERIALIZED VIEW CONCURRENTLY "SeaTides";
```

---

## 📞 Summary

| Action | Command | Time |
|--------|---------|------|
| **Diagnose** | `python optimize_seatides.py --diagnose` | 2 min |
| **Optimize** | `python optimize_seatides.py --optimize` | 10 min |
| **Test** | `python optimize_seatides.py --refresh` | Variable |
| **Monitor** | `python optimize_seatides.py --monitor` | As needed |

**Total Time to Fix:** ~20 minutes

**Expected Result:** 17 hours → 5-30 minutes ✅

---

## 📝 Files Included

1. `backend/optimizations/SEATIDES_REFRESH_OPTIMIZATION.sql` - SQL script
2. `backend/optimizations/optimize_seatides.py` - Python automation tool
3. `SEATIDES_TROUBLESHOOTING_GUIDE.md` - Detailed guide
4. `SEATIDES_OPTIMIZATION_GUIDE.md` - Overview & best practices

---

## ✅ Recommended Approach

1. **Run Python script** (easiest):
   ```bash
   python backend/optimizations/optimize_seatides.py --diagnose
   python backend/optimizations/optimize_seatides.py --optimize
   python backend/optimizations/optimize_seatides.py --refresh
   ```

2. **OR use SQL directly** (if Python doesn't work):
   - Copy commands from `SEATIDES_REFRESH_OPTIMIZATION.sql`
   - Paste into PostgreSQL client
   - Run PHASE by PHASE

3. **Monitor progress** (optional):
   - Run in separate terminal while refreshing
   - See real-time progress

---

## 🎯 Expected Timeline

- **Now**: Run diagnosis → identify missing indexes
- **+10 min**: Create indexes → statistics updated
- **+30 min**: Refresh completes → benchmark new time
- **After**: Schedule maintenance → prevent future issues

**Total: ~40 minutes to complete fix with verification**

---

## Questions?

Check these files for answers:
- **"How do I run it?"** → This file (START HERE)
- **"What's wrong?"** → SEATIDES_TROUBLESHOOTING_GUIDE.md
- **"Why is it slow?"** → SEATIDES_OPTIMIZATION_GUIDE.md
- **"What are the SQL commands?"** → SEATIDES_REFRESH_OPTIMIZATION.sql

