# Quick Reference: Always Raw Data Mode

## What Changed?

The backend Lambda function now **ALWAYS returns 1-minute interval raw data**, regardless of the date range requested.

## Before vs After

| Date Range | Before (Smart Aggregation) | After (Always Raw) |
|------------|---------------------------|-------------------|
| 1-3 days   | Raw (1-minute)           | Raw (1-minute) ✅ |
| 4-7 days   | 5-minute aggregation     | Raw (1-minute) ✅ |
| 8-14 days  | 15-minute aggregation    | Raw (1-minute) ✅ |
| 15-30 days | Hourly aggregation       | Raw (1-minute) ✅ |
| 31-90 days | 3-hour aggregation       | Raw (1-minute) ✅ |
| 91-180 days| Daily aggregation        | Raw (1-minute) ✅ |
| 180+ days  | Weekly aggregation       | Raw (1-minute) ✅ |

## Key Function Modified

**File:** `backend/lambdas/get_data/main.py`

**Function:** `calculate_aggregation_level(start_date, end_date)`

**Before:**
```python
def calculate_aggregation_level(start_date, end_date):
    # Complex logic to determine aggregation based on date range
    if days <= 3:
        return 'raw', None
    elif days <= 7:
        return '5min', '5 minutes'
    # ... more conditions
```

**After:**
```python
def calculate_aggregation_level(start_date, end_date):
    # Always return raw data - no aggregation
    return 'raw', None
```

## SQL Query Always Used

```sql
-- Sea Level Data (Raw Query)
SELECT
    m."Tab_DateTime",
    l."Station",
    CAST(m."Tab_Value_mDepthC1" AS FLOAT) as "Tab_Value_mDepthC1",
    CAST(m."Tab_Value_monT2m" AS FLOAT) as "Tab_Value_monT2m"
FROM "Monitors_info2" m
JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
WHERE DATE(m."Tab_DateTime") >= :start_date
  AND DATE(m."Tab_DateTime") <= :end_date
ORDER BY "Tab_DateTime" ASC
```

- No GROUP BY
- No DATE_TRUNC
- No RecordCount
- No aggregation functions (AVG, MIN, MAX)

## Expected Data Volume

| Date Range | Approximate Records per Station |
|------------|--------------------------------|
| 1 day      | ~1,440 records                |
| 7 days     | ~10,080 records               |
| 30 days    | ~43,200 records               |
| 90 days    | ~129,600 records              |
| 365 days   | ~525,600 records              |

**Note:** Actual records depend on data availability and missing values.

## API Response Headers

The response will always include:
```
X-Aggregation-Level: raw
X-Record-Count: <number_of_records>
```

## What Still Works

✅ All existing functionality is preserved:
- Anomaly detection (Southern Baseline Rules)
- Caching (Redis)
- Date filtering
- Station filtering
- Batch queries
- Error handling
- Data cleaning

## Performance Impact

### Increased:
- Network payload size
- Frontend rendering time (more data points)
- JSON parsing time

### Unchanged:
- Database query performance (still indexed)
- Lambda execution speed
- Cache efficiency for same queries

## Rollback Instructions

To restore smart aggregation:

1. Open `backend/lambdas/get_data/main.py`
2. Find `calculate_aggregation_level()` function (lines 74-81)
3. Replace with the original implementation (see git history)
4. Update file header comments
5. Redeploy Lambda

## Testing

Run this test to verify always-raw behavior:
```python
cd backend/lambdas/get_data
python -c "
from main import calculate_aggregation_level

# Test various date ranges
test_cases = [
    ('2024-01-01', '2024-01-02', '1 day'),
    ('2024-01-01', '2024-01-31', '30 days'),
    ('2024-01-01', '2024-12-31', '365 days'),
]

for start, end, label in test_cases:
    agg_level, _ = calculate_aggregation_level(start, end)
    assert agg_level == 'raw', f'Expected raw, got {agg_level}'
    print(f'{label}: {agg_level} ✅')
"
```

## Recommendations

### Frontend:
- Implement data decimation for chart rendering
- Show loading indicators for large date ranges
- Consider limiting max date range to 90 days
- Use chart libraries with built-in downsampling (e.g., Plotly, Chart.js with decimation)

### Backend:
- Monitor Lambda memory usage
- Watch API Gateway timeouts
- Consider implementing pagination for very large ranges
- Monitor database load

### Monitoring:
- Track API response times
- Monitor payload sizes in CloudWatch
- Watch for timeout errors
- Check Redis cache hit rates

## Contact

For questions or issues with this modification, refer to:
- Full report: `MODIFICATION_REPORT.md`
- Git commit history
- CloudWatch logs for runtime behavior

---

**Last Updated:** 2025-12-08
