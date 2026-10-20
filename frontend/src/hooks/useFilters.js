import { useState, useMemo, useCallback } from 'react';

const defaultFilters = {
  startDate: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
  endDate: new Date(),
  dataType: 'default',
  trendline: 'none',
  analysisType: 'none',
  showAnomalies: false,
  predictionModels: [],
  forecastHours: 72,
  // Calibration correction state
  calibrationMode: false,              // toggle — panel visible and active
  calibrationStart: null,              // string | null — full ISO-8601 datetime, e.g. "2026-10-08T15:13"
  calibrationEnd: null,                // string | null
  calibrationOffset: 0.0,              // metres, float
  calibrationReference: 'none',        // 'none' | 'Ashdod' | 'Ashkelon'
  calibrationCorrectionType: 'offset', // 'offset' | 'interpolate' | 'relative'
  calibrationExpectedGap: null,        // metres, float | null — only used in relative mode
  calibrationPreviewData: null,        // API response or null
};

export const useFilters = () => {
  const [filters, setFilters] = useState(defaultFilters);

  // Computed filter values formatted for API
  const filterValues = useMemo(() => {
    const formatDate = (date) => {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    };

    const startDateStr = formatDate(filters.startDate);
    const endDateStr = formatDate(filters.endDate);
    return {
      startDate: startDateStr,
      endDate: endDateStr,
      dataType: filters.dataType,
      showAnomalies: filters.showAnomalies,
      trendline: filters.trendline,
      analysisType: filters.analysisType,
      predictionModels: filters.predictionModels,
      forecastHours: filters.forecastHours,
      // Calibration — full ISO timestamps for sub-minute precision in SQL
      calibrationStart: filters.calibrationStart || `${startDateStr}T00:00`,
      calibrationEnd: filters.calibrationEnd || `${endDateStr}T23:59`,
      calibrationOffset: filters.calibrationOffset,
      calibrationReference: filters.calibrationReference,
      calibrationCorrectionType: filters.calibrationCorrectionType,
      calibrationExpectedGap: filters.calibrationExpectedGap ?? 0.0,
    };
  }, [filters]);

  const updateFilter = useCallback((key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  }, []);

  const updateDateRange = useCallback((startDate, endDate) => {
    setFilters(prev => ({ ...prev, startDate, endDate }));
  }, []);

  const toggleModel = useCallback((model) => {
    setFilters(prev => {
      const currentModels = prev.predictionModels || [];
      if (currentModels.includes(model)) {
        return { ...prev, predictionModels: currentModels.filter(m => m !== model) };
      } else {
        return { ...prev, predictionModels: [...currentModels, model] };
      }
    });
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(defaultFilters);
  }, []);

  return {
    filters,
    filterValues,
    setFilters,
    updateFilter,
    updateDateRange,
    toggleModel,
    resetFilters
  };
};

export default useFilters;
