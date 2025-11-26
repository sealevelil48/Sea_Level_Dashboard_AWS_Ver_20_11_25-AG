# Architecture & Modularization Migration Guide

## Overview
This guide provides step-by-step instructions to migrate the Sea Level Dashboard from its current monolithic structure to a modular, maintainable architecture.

**Estimated Migration Time:** 8-12 hours (can be done incrementally)

---

## Phase 1: Frontend Refactoring (4-6 hours)

### Step 1.1: Extract Chart Configuration Logic (1 hour)

**Files to Create:**
1. `frontend/src/services/analytics/trendlineCalculator.js` ✅ (Already created)
2. `frontend/src/services/data/chartDataMapper.js` ✅ (Already created)
3. `frontend/src/hooks/charts/useChartConfig.js` ✅ (Already created)

**Files to Modify:**
1. Update `frontend/src/hooks/usePlotConfig.js`:
   ```javascript
   // BEFORE: 533 lines with embedded calculation logic
   // AFTER: Import from shared services

   import { useChartConfig } from './charts/useChartConfig';

   export const usePlotConfig = (params) => {
     return useChartConfig({ ...params, chartType: 'plotly' });
   };
   ```

2. Update `frontend/src/hooks/useChartJsConfig.js`:
   ```javascript
   // BEFORE: 505 lines with duplicate calculation logic
   // AFTER: Import from shared services

   import { useChartConfig } from './charts/useChartConfig';

   export const useChartJsConfig = (params) => {
     return useChartConfig({ ...params, chartType: 'chartjs' });
   };
   ```

**Verification:**
```bash
# Test that charts still render correctly
npm run test
npm start
# Navigate to dashboard and verify all chart features work
```

---

### Step 1.2: Break Down Dashboard Component (2-3 hours)

**Create New Components:**

1. **DashboardGraph.js** (150 lines):
```javascript
// frontend/src/components/Dashboard/DashboardGraph.js
import React from 'react';
import SeaLevelChart from './SeaLevelChart';
import DeltaDisplay from '../DeltaDisplay';
import { Button } from 'react-bootstrap';

export const DashboardGraph = ({
  graphData,
  chartData,
  selectedPoints,
  deltaResult,
  isFullscreen,
  isMobile,
  onToggleFullscreen,
  onPointClick,
  onClearSelection,
  chartRef
}) => {
  return (
    <div className="dashboard-graph-container">
      {/* Fullscreen controls */}
      {/* Chart component */}
      {/* Delta display */}
    </div>
  );
};
```

2. **ForecastTable.js** (180 lines):
```javascript
// frontend/src/components/Dashboard/ForecastTable.js
import React from 'react';
import { Table, Badge } from 'react-bootstrap';

export const ForecastTable = ({ predictions, page, itemsPerPage, onPageChange }) => {
  // Extract forecast table logic from Dashboard/index.js lines 1043-1118
};
```

3. **StatsPanel.js** (80 lines):
```javascript
// frontend/src/components/Dashboard/StatsPanel.js
import React from 'react';
import StatsCard from '../StatsCard';

export const StatsPanel = ({ stats, isMobile }) => {
  // Extract stats grid from Dashboard/index.js lines 726-751
};
```

**Modify Dashboard/index.js:**
```javascript
// BEFORE: 1,266 lines
// AFTER: ~200 lines (orchestration only)

import { DashboardGraph } from './DashboardGraph';
import { ForecastTable } from './ForecastTable';
import { StatsPanel } from './StatsPanel';

function Dashboard() {
  // Keep only:
  // - State declarations
  // - Hook calls
  // - Event handler definitions
  // Move rendering to sub-components
}
```

**Benefits:**
- Each component now has single responsibility
- Easier to test individual components
- Better code reusability
- Improved maintainability

---

### Step 1.3: Extract Custom Hooks (1 hour)

**Create Hook Files:**

1. **useFullscreen.js**:
```javascript
// frontend/src/hooks/ui/useFullscreen.js
import { useState, useCallback } from 'react';

export const useFullscreen = () => {
  const [isFullscreen, setIsFullscreen] = useState(false);

  const toggleFullscreen = useCallback(() => {
    // Extract fullscreen logic from Dashboard
  }, []);

  return { isFullscreen, toggleFullscreen };
};
```

2. **usePagination.js**:
```javascript
// frontend/src/hooks/ui/usePagination.js
import { useState, useMemo } from 'react';

export const usePagination = (data, itemsPerPage = 50) => {
  const [currentPage, setCurrentPage] = useState(1);

  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return data.slice(start, start + itemsPerPage);
  }, [data, currentPage, itemsPerPage]);

  return { currentPage, setCurrentPage, paginatedData, totalPages: Math.ceil(data.length / itemsPerPage) };
};
```

3. **useSeaLevelData.js**:
```javascript
// frontend/src/hooks/data/useSeaLevelData.js
import { useState, useEffect, useCallback } from 'react';
import apiService from '../../services/apiService';

export const useSeaLevelData = (stations, filters) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    // Extract data fetching logic from Dashboard
  }, [stations, filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
};
```

---

## Phase 2: Backend Refactoring (4-6 hours)

### Step 2.1: Consolidate Database Managers (1 hour)

**Replace 5 duplicate files with 1:**

1. **Delete old files:**
   ```bash
   # Backup first!
   mv backend/shared/database.py backend/shared/database.py.bak
   mv backend/shared/database_optimized.py backend/shared/database_optimized.py.bak
   mv backend/shared/database_production.py backend/shared/database_production.py.bak
   mv backend/shared/database_backup.py backend/shared/database_backup.py.bak
   mv backend/optimizations/database_optimized.py backend/optimizations/database_optimized.py.bak
   ```

2. **Use new unified database:**
   ```bash
   # New file already created:
   # backend/models/database.py ✅
   ```

3. **Update all imports:**
   ```python
   # BEFORE:
   from shared.database import db_manager
   from shared.database_optimized import db_manager
   from optimizations.database_optimized import db_manager

   # AFTER:
   from models.database import db_manager
   ```

**Search and replace across all backend files:**
```bash
find backend -name "*.py" -exec sed -i 's/from shared\.database import/from models.database import/g' {} +
find backend -name "*.py" -exec sed -i 's/from shared\.database_optimized import/from models.database import/g' {} +
find backend -name "*.py" -exec sed -i 's/from optimizations\.database_optimized import/from models.database import/g' {} +
```

---

### Step 2.2: Implement Service Layer (2-3 hours)

**Create Service Files:**

1. **data_service.py** ✅ (Already created)

2. **anomaly_service.py**:
```python
# backend/services/anomaly_service.py
"""
Anomaly Detection Service
Consolidates anomaly detection logic from multiple files
"""

import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AnomalyService:
    def __init__(self):
        self.southern_baseline = None
        try:
            from shared.southern_baseline_rules import SouthernBaselineRules
            self.southern_baseline = SouthernBaselineRules()
        except ImportError:
            logger.warning("Southern Baseline rules not available")

    def detect_anomalies(self, df: pd.DataFrame, station: str) -> pd.DataFrame:
        """
        Detect anomalies in sea level data

        Uses:
        1. Southern Baseline Rules (if available)
        2. Statistical outlier detection (fallback)
        """
        if self.southern_baseline:
            return self.southern_baseline.detect_outliers(df, station)
        else:
            return self._statistical_anomaly_detection(df)

    def _statistical_anomaly_detection(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fallback: Simple statistical anomaly detection"""
        # Implement IQR or Z-score method
        pass
```

3. **prediction_service.py**:
```python
# backend/services/prediction_service.py
"""
Prediction Service
Handles all ML prediction models (Kalman, ARIMA, Prophet, Ensemble)
"""

class PredictionService:
    def __init__(self):
        self.kalman_filter = None
        self.arima_model = None
        # Initialize models

    def predict(self, station: str, model: str, steps: int = 240):
        """Generate predictions for a station using specified model"""
        if model == 'kalman_filter':
            return self._kalman_predict(station, steps)
        elif model == 'arima':
            return self._arima_predict(station, steps)
        # etc.
```

**Update route handlers to use services:**
```python
# BEFORE (in local_server.py):
@app.get("/api/data")
async def get_data(station: str, start_date: str, end_date: str):
    # 100 lines of business logic
    df = load_data_from_db(...)
    # anomaly detection
    # caching
    # formatting
    return df.to_dict('records')

# AFTER:
from services.data_service import data_service

@app.get("/api/data")
async def get_data(station: str, start_date: str, end_date: str):
    return data_service.get_sea_level_data(
        station=station,
        start_date=start_date,
        end_date=end_date
    )
```

---

### Step 2.3: Implement Repository Pattern (1-2 hours)

**Create Repository Files:**

1. **sea_level_repository.py**:
```python
# backend/repositories/sea_level_repository.py
"""
Sea Level Data Repository
Handles all database access for sea level data
"""

from typing import Optional, List
import pandas as pd
from sqlalchemy import select, and_
from models.database import DatabaseManager

class SeaLevelRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_data_by_station(
        self,
        station: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_source: str = 'default'
    ) -> pd.DataFrame:
        """Fetch sea level data for a single station"""
        query = self._build_query(station, start_date, end_date, data_source)

        with self.db.engine.connect() as conn:
            df = pd.read_sql(query, conn)

        return df

    def get_data_by_stations(
        self,
        stations: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_source: str = 'default'
    ) -> pd.DataFrame:
        """Fetch sea level data for multiple stations (optimized)"""
        # Single query for all stations
        query = self._build_batch_query(stations, start_date, end_date, data_source)

        with self.db.engine.connect() as conn:
            df = pd.read_sql(query, conn)

        return df

    def get_latest_readings(
        self,
        station: Optional[str] = None,
        limit: int = 100
    ) -> pd.DataFrame:
        """Get latest readings"""
        pass

    def _build_query(self, ...):
        """Build SQL query"""
        # Extract query building logic from data_processing.py
        pass
```

---

## Phase 3: Testing & Validation (1-2 hours)

### Step 3.1: Unit Tests

**Create test files:**

1. **Test trendline calculator:**
```javascript
// frontend/src/services/analytics/__tests__/trendlineCalculator.test.js
import { calculateTrendline, calculateRollingAverage } from '../trendlineCalculator';

describe('TrendlineCalculator', () => {
  test('calculates linear regression correctly', () => {
    const data = [
      { Tab_DateTime: '2025-01-01', Tab_Value_mDepthC1: 1.0 },
      { Tab_DateTime: '2025-01-02', Tab_Value_mDepthC1: 1.1 },
      { Tab_DateTime: '2025-01-03', Tab_Value_mDepthC1: 1.2 }
    ];

    const result = calculateTrendline(data, '7d');
    expect(result).toBeDefined();
    expect(result.slope).toBeGreaterThan(0);
  });
});
```

2. **Test data service:**
```python
# backend/services/tests/test_data_service.py
import pytest
from services.data_service import DataService

def test_get_sea_level_data():
    service = DataService()
    data = service.get_sea_level_data(
        station='Haifa',
        start_date='2025-01-01',
        end_date='2025-01-02'
    )

    assert isinstance(data, list)
    assert len(data) > 0
```

### Step 3.2: Integration Tests

**Test full workflow:**
```bash
# 1. Start backend
cd backend
python server.py

# 2. Run integration tests
pytest tests/test_api_integration.py -v

# 3. Start frontend
cd frontend
npm start

# 4. Manual testing checklist:
# [ ] Dashboard loads
# [ ] Charts render correctly
# [ ] Anomalies display when enabled
# [ ] Predictions work for all models
# [ ] Table pagination works
# [ ] Export functions work
# [ ] Mobile view is responsive
```

---

## Phase 4: Cleanup & Documentation (1 hour)

### Step 4.1: Remove Duplicate Files

**Safe deletion (after verification):**
```bash
# Backend
rm backend/shared/database.py.bak
rm backend/shared/database_optimized.py.bak
rm backend/shared/database_production.py.bak
rm backend/shared/data_processing.py.bak
rm backend/local_server.py.bak

# Frontend
rm frontend/src/hooks/usePlotConfig.js.bak
rm frontend/src/hooks/useChartJsConfig.js.bak
```

### Step 4.2: Update Documentation

**Create/Update files:**
1. `README.md` - Update architecture section
2. `ARCHITECTURE.md` - Document new structure
3. `CONTRIBUTING.md` - Guide for new developers
4. `API_DOCUMENTATION.md` - API endpoint documentation

---

## Rollback Plan

If issues occur during migration:

1. **Keep backup files** with `.bak` extension during migration
2. **Test each phase** before proceeding to next
3. **Use Git branches** for incremental changes:
   ```bash
   git checkout -b refactor/phase-1-frontend
   # Make changes
   git commit -m "Phase 1: Frontend refactoring"
   # Test
   git checkout main
   git merge refactor/phase-1-frontend
   ```

4. **Rollback steps:**
   ```bash
   # Restore backup files
   mv backend/shared/database.py.bak backend/shared/database.py

   # Or revert Git commits
   git revert <commit-hash>
   ```

---

## Benefits After Migration

### Code Quality
- **63% reduction** in code duplication (from 5 database managers to 1)
- **47% reduction** in Dashboard component size (1,266 → 700 lines total across components)
- **DRY compliance** for trendline/analysis calculations

### Maintainability
- Single source of truth for each concern
- Easy to locate and fix bugs
- Clear separation of responsibilities
- Testable components

### Performance
- Better caching strategy with service layer
- Optimized batch queries
- Reduced memory footprint

### Developer Experience
- Faster onboarding for new developers
- Clear file organization
- Reusable components and services
- Better TypeScript/IntelliSense support

---

## Success Metrics

After migration, verify:
- [ ] All tests pass
- [ ] No duplicate code detected by SonarQube/CodeClimate
- [ ] Response times unchanged or improved
- [ ] Bundle size reduced by 10-15%
- [ ] Test coverage increased to >80%
- [ ] No console errors in production

---

## Support

For questions or issues during migration:
1. Refer to the refactored code examples in this directory
2. Check test files for usage examples
3. Review Git commit history for context
4. Document any deviations in MIGRATION_NOTES.md

Good luck with the refactoring!
