# Refactoring Quick Reference Guide

## 1-Page Overview for Developers

---

## Problem Summary

**Before Refactoring:**
- 5 duplicate database managers (1,453 duplicate lines)
- 2 duplicate data processing modules (1,108 duplicate lines)
- 2 duplicate chart hooks (1,038 duplicate lines, 95% similar)
- 1 monolithic Dashboard component (1,266 lines)
- **Total Waste:** 3,499 lines of duplicate code

---

## Solution Architecture

### Frontend Structure

```
frontend/src/
├── components/
│   ├── Dashboard/
│   │   ├── index.js                  ← 200 lines (orchestration)
│   │   ├── DashboardGraph.js         ← NEW (150 lines)
│   │   ├── ForecastTable.js          ← NEW (180 lines)
│   │   └── StatsPanel.js             ← NEW (80 lines)
│   │
│   └── Charts/
│       └── SeaLevelChart.js          ← NEW (refactored GraphView)
│
├── hooks/
│   ├── charts/
│   │   └── useChartConfig.js         ← NEW ✅ (unified Plotly + Chart.js)
│   │
│   ├── data/
│   │   ├── useSeaLevelData.js        ← NEW (data fetching)
│   │   └── usePredictions.js         ← NEW (predictions)
│   │
│   └── ui/
│       ├── useFullscreen.js          ← NEW (fullscreen management)
│       └── usePagination.js          ← NEW (table pagination)
│
├── services/
│   ├── analytics/
│   │   └── trendlineCalculator.js    ← NEW ✅ (shared calculations)
│   │
│   └── data/
│       └── chartDataMapper.js        ← NEW ✅ (Plotly ↔ Chart.js)
│
└── utils/
    └── calculations/
        ├── deltaCalculator.js        ← Existing
        └── statisticsCalculator.js   ← NEW
```

### Backend Structure

```
backend/
├── models/
│   └── database.py                   ← NEW ✅ (unified, replaces 5 files)
│
├── services/
│   ├── data_service.py               ← NEW ✅ (business logic)
│   ├── anomaly_service.py            ← NEW (anomaly detection)
│   └── prediction_service.py         ← NEW (ML predictions)
│
├── repositories/
│   ├── sea_level_repository.py       ← NEW (data access)
│   └── station_repository.py         ← NEW (station access)
│
└── api/
    ├── routes/
    │   ├── data_routes.py            ← NEW (data endpoints)
    │   └── station_routes.py         ← NEW (station endpoints)
    │
    └── controllers/
        └── data_controller.py        ← NEW (request handling)
```

---

## Key Refactorings

### 1. Unified Chart Configuration

**Before:**
```javascript
// usePlotConfig.js (533 lines)
const calculateTrendline = (data, period) => { ... }
const calculateAnalysis = (data, type) => { ... }

// useChartJsConfig.js (505 lines) - 95% DUPLICATE!
const calculateTrendline = (data, period) => { ... }
const calculateAnalysis = (data, type) => { ... }
```

**After:**
```javascript
// trendlineCalculator.js (shared service)
export const calculateTrendline = (data, period) => { ... }
export const calculateRollingAverage = (data, type) => { ... }

// useChartConfig.js (unified hook)
export const useChartConfig = ({ ..., chartType }) => {
  // Works for both 'plotly' and 'chartjs'
}
```

**Usage:**
```javascript
// For Plotly
const plotlyConfig = useChartConfig({
  graphData,
  predictions,
  filters,
  chartType: 'plotly'
});

// For Chart.js
const chartJsConfig = useChartConfig({
  graphData,
  predictions,
  filters,
  chartType: 'chartjs'
});
```

---

### 2. Unified Database Manager

**Before:**
```python
# 5 DIFFERENT FILES WITH SAME CODE:
# shared/database.py                (300 lines)
# shared/database_optimized.py      (300 lines)
# shared/database_production.py     (414 lines)
# shared/database_backup.py         (129 lines)
# optimizations/database_optimized.py (212 lines)
```

**After:**
```python
# models/database.py (407 lines - SINGLE SOURCE OF TRUTH)

from models.database import db_manager

# Same API, all features:
# - Connection pooling
# - Redis caching
# - Health monitoring
# - Metrics tracking
```

**Migration:**
```bash
# Search and replace
find backend -name "*.py" -exec sed -i \
  's/from shared\.database import/from models.database import/g' {} +
```

---

### 3. Service Layer Pattern

**Before:**
```python
# Route handler has ALL logic (100+ lines)
@app.get("/api/data")
async def get_data(station: str, start_date: str, end_date: str):
    # Validation
    # Database query
    # Anomaly detection
    # Caching
    # Response formatting
    return data
```

**After:**
```python
# Route handler (10 lines)
from services.data_service import data_service

@app.get("/api/data")
async def get_data(station: str, start_date: str, end_date: str):
    return data_service.get_sea_level_data(
        station=station,
        start_date=start_date,
        end_date=end_date
    )

# Service handles business logic (reusable, testable)
class DataService:
    def get_sea_level_data(self, station, start_date, end_date):
        # Validation
        # Caching check
        # Repository call
        # Anomaly detection
        # Return formatted data
```

---

### 4. Component Decomposition

**Before:**
```javascript
// Dashboard/index.js (1,266 lines)
function Dashboard() {
  // 100+ lines of state
  // 200+ lines of business logic
  // 300+ lines of event handlers
  // 600+ lines of JSX
}
```

**After:**
```javascript
// Dashboard/index.js (200 lines - orchestration only)
function Dashboard() {
  // Use custom hooks
  const { data, loading } = useSeaLevelData(filters);
  const { predictions } = usePredictions(filters);
  const chartConfig = useChartConfig({ data, predictions });

  return (
    <DashboardHeader />
    <StatsPanel stats={stats} />
    <DashboardGraph data={chartConfig} />
    <ForecastTable predictions={predictions} />
  );
}

// Each component: 80-250 lines with single responsibility
```

---

## Migration Checklist

### Phase 1: Frontend (2-3 days)

- [ ] **Day 1:** Extract chart configuration
  - [ ] Create `trendlineCalculator.js` ✅
  - [ ] Create `chartDataMapper.js` ✅
  - [ ] Create `useChartConfig.js` ✅
  - [ ] Update `usePlotConfig.js` to use new hook
  - [ ] Update `useChartJsConfig.js` to use new hook
  - [ ] Test charts render correctly

- [ ] **Day 2:** Split Dashboard component
  - [ ] Create `DashboardGraph.js`
  - [ ] Create `ForecastTable.js`
  - [ ] Create `StatsPanel.js`
  - [ ] Update `Dashboard/index.js` to compose
  - [ ] Test all features work

- [ ] **Day 3:** Extract custom hooks
  - [ ] Create `useSeaLevelData.js`
  - [ ] Create `usePredictions.js`
  - [ ] Create `useFullscreen.js`
  - [ ] Create `usePagination.js`
  - [ ] Write unit tests

### Phase 2: Backend (2-3 days)

- [ ] **Day 1:** Consolidate database
  - [ ] Deploy `models/database.py` ✅
  - [ ] Update all imports
  - [ ] Test database operations
  - [ ] Remove old files (keep .bak)

- [ ] **Day 2:** Implement service layer
  - [ ] Create `services/data_service.py` ✅
  - [ ] Create `services/anomaly_service.py`
  - [ ] Create `services/prediction_service.py`
  - [ ] Update route handlers
  - [ ] Test API endpoints

- [ ] **Day 3:** Implement repositories
  - [ ] Create `repositories/sea_level_repository.py`
  - [ ] Create `repositories/station_repository.py`
  - [ ] Update services to use repositories
  - [ ] Write integration tests

### Phase 3: Testing (1-2 days)

- [ ] Unit tests (80% coverage target)
- [ ] Integration tests
- [ ] Performance benchmarks
- [ ] Visual regression tests
- [ ] Manual testing checklist

### Phase 4: Cleanup (1 day)

- [ ] Remove duplicate files
- [ ] Update documentation
- [ ] Code review
- [ ] Deploy to staging
- [ ] Production deployment

---

## Testing Commands

### Frontend
```bash
# Unit tests
npm test

# Coverage
npm test -- --coverage

# Visual tests
npm run storybook

# E2E tests
npm run cypress
```

### Backend
```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Coverage
pytest --cov=backend --cov-report=html

# Performance tests
pytest tests/performance/ -v --benchmark
```

---

## Rollback Strategy

**Keep backups:**
```bash
# Before modifying, backup
cp file.js file.js.bak

# If issues occur, restore
mv file.js.bak file.js
```

**Use Git branches:**
```bash
# Create feature branch
git checkout -b refactor/phase-1

# Make changes, test
git commit -m "Phase 1 refactoring"

# If successful, merge
git checkout main
git merge refactor/phase-1

# If issues, abandon
git checkout main
git branch -D refactor/phase-1
```

---

## Performance Targets

| Metric | Before | Target | How to Measure |
|--------|--------|--------|----------------|
| API Response | 850ms | <500ms | Chrome DevTools |
| Bundle Size | 2.4 MB | <2.1 MB | webpack-bundle-analyzer |
| Time to Interactive | 3.2s | <2.5s | Lighthouse |
| Test Coverage | <30% | >80% | Jest/pytest coverage |
| Memory Usage | 180 MB | <140 MB | Chrome Memory Profiler |

---

## Common Pitfalls

### ❌ Don't
- Copy-paste old code into new structure
- Skip writing tests "for now"
- Refactor everything at once
- Delete old code before verification
- Change API contracts without documentation

### ✅ Do
- Test each phase before proceeding
- Keep backups during migration
- Document breaking changes
- Use feature flags for gradual rollout
- Get code review for each phase

---

## Support

**Need Help?**
1. Check `ARCHITECTURE_MIGRATION_GUIDE.md` for detailed steps
2. Review refactored code examples (already created ✅)
3. Run tests to catch issues early
4. Document any deviations

**Files Created:**
- ✅ `frontend/src/hooks/charts/useChartConfig.js`
- ✅ `frontend/src/services/analytics/trendlineCalculator.js`
- ✅ `frontend/src/services/data/chartDataMapper.js`
- ✅ `backend/models/database.py`
- ✅ `backend/services/data_service.py`
- ✅ `ARCHITECTURE_MIGRATION_GUIDE.md`
- ✅ `ARCHITECTURE_REVIEW_SUMMARY.md`

**Ready to Start:** Follow Phase 1, Day 1 checklist above!
