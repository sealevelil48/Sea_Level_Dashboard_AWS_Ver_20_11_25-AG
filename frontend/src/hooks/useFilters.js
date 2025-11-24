import { useState, useMemo, useCallback } from 'react';

const defaultFilters = {
  startDate: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
  endDate: new Date(),
  dataType: 'default',
  trendline: 'none',
  analysisType: 'none',
  showAnomalies: false,
  predictionModels: [],
  forecastHours: 72
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

    return {
      startDate: formatDate(filters.startDate),
      endDate: formatDate(filters.endDate),
      dataType: filters.dataType,
      showAnomalies: filters.showAnomalies,
      trendline: filters.trendline,
      analysisType: filters.analysisType,
      predictionModels: filters.predictionModels,
      forecastHours: filters.forecastHours
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
