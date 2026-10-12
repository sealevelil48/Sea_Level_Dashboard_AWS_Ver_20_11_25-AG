import { useState, useMemo, useCallback } from 'react';
import apiService from '../services/apiService';

/**
 * Manages calibration correction state and API interactions.
 *
 * The calibration tool lets operators apply a non-destructive offset
 * to a corrupted time window in sensor data. The offset is stored in
 * the database's Calibration_Offset column — raw values are never modified.
 *
 * @param {Function} updateFilter - from useFilters
 * @param {Object}   filterValues - computed filter values from useFilters
 * @param {Array}    selectedStations - currently selected station names
 */
export const useCalibration = ({ updateFilter, filterValues, selectedStations }) => {
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isLoadingSuggest, setIsLoadingSuggest] = useState(false);
  const [isCommitting, setIsCommitting] = useState(false);
  const [commitResult, setCommitResult] = useState(null);
  const [error, setError] = useState(null);

  // The first non-"All Stations" station is the target for calibration
  const targetStation = useMemo(
    () => (selectedStations || []).find(s => s !== 'All Stations') || null,
    [selectedStations]
  );

  /**
   * Fetch a preview of the corrected data (in-memory, no DB writes).
   * Stores the result in filterValues so the chart hook can render the overlay.
   */
  const fetchPreview = useCallback(async () => {
    if (!targetStation) {
      setError('Select a single station first');
      return;
    }
    setIsLoadingPreview(true);
    setError(null);
    try {
      const result = await apiService.previewCalibration({
        station: targetStation,
        start_datetime: filterValues.calibrationStart,
        end_datetime: filterValues.calibrationEnd,
        offset: filterValues.calibrationOffset,
        ...(filterValues.calibrationReference !== 'none' && {
          reference_station: filterValues.calibrationReference,
        }),
      });
      if (!result) {
        setError('Preview returned no data');
        return;
      }
      updateFilter('calibrationPreviewData', result);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoadingPreview(false);
    }
  }, [targetStation, filterValues, updateFilter]);

  /**
   * Auto-detect the largest step change and populate the offset field.
   */
  const fetchSuggest = useCallback(async () => {
    if (!targetStation) {
      setError('Select a single station first');
      return;
    }
    setIsLoadingSuggest(true);
    setError(null);
    try {
      const result = await apiService.suggestCalibration({
        station: targetStation,
        start_datetime: filterValues.calibrationStart,
        end_datetime: filterValues.calibrationEnd,
      });
      if (result?.suggested_offset != null) {
        updateFilter('calibrationOffset', result.suggested_offset);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoadingSuggest(false);
    }
  }, [targetStation, filterValues, updateFilter]);

  /**
   * Commit the offset permanently to the database (additive UPDATE).
   * On success, clears preview data and closes calibration mode so the
   * main chart re-fetches with the new offset applied transparently.
   */
  const commitCalibration = useCallback(async () => {
    if (!targetStation) return false;
    setIsCommitting(true);
    setError(null);
    try {
      const result = await apiService.commitCalibration({
        station: targetStation,
        start_datetime: filterValues.calibrationStart,
        end_datetime: filterValues.calibrationEnd,
        offset: filterValues.calibrationOffset,
      });
      setCommitResult(result);
      updateFilter('calibrationPreviewData', null);
      updateFilter('calibrationMode', false);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setIsCommitting(false);
    }
  }, [targetStation, filterValues, updateFilter]);

  /**
   * Cancel without committing — resets all calibration state.
   */
  const cancelCalibration = useCallback(() => {
    updateFilter('calibrationMode', false);
    updateFilter('calibrationPreviewData', null);
    updateFilter('calibrationOffset', 0.0);
    setError(null);
    setCommitResult(null);
  }, [updateFilter]);

  return {
    targetStation,
    isLoadingPreview,
    isLoadingSuggest,
    isCommitting,
    commitResult,
    error,
    fetchPreview,
    fetchSuggest,
    commitCalibration,
    cancelCalibration,
  };
};

export default useCalibration;
