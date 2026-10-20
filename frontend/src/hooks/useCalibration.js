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
      const params = {
        station: targetStation,
        start_datetime: filterValues.calibrationStart,
        end_datetime: filterValues.calibrationEnd,
        correction_type: filterValues.calibrationCorrectionType,
      };
      // Only include offset for 'offset' mode
      if (filterValues.calibrationCorrectionType === 'offset') {
        params.offset = filterValues.calibrationOffset;
      } else if (filterValues.calibrationCorrectionType === 'relative') {
        params.reference_station = filterValues.calibrationReference;
        params.expected_gap = filterValues.calibrationExpectedGap ?? 0.0;
      }
      // Include reference station if not 'none' and not relative mode
      if (filterValues.calibrationReference !== 'none' && filterValues.calibrationCorrectionType !== 'relative') {
        params.reference_station = filterValues.calibrationReference;
      }
      const result = await apiService.previewCalibration(params);
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
      const params = {
        station: targetStation,
        start_datetime: filterValues.calibrationStart,
        end_datetime: filterValues.calibrationEnd,
      };
      // If reference mode, include reference and gap
      if (filterValues.calibrationCorrectionType === 'relative') {
        params.reference_station = filterValues.calibrationReference;
        params.expected_gap = filterValues.calibrationExpectedGap ?? 0.0;
      }
      const result = await apiService.suggestCalibration(params);

      if (result?.drift_detected && result?.malfunction_start && result?.malfunction_end) {
        // Auto-snap to drift window
        const startISO = new Date(result.malfunction_start).toISOString().slice(0, 16);
        const endISO = new Date(result.malfunction_end).toISOString().slice(0, 16);
        updateFilter('calibrationStart', startISO);
        updateFilter('calibrationEnd', endISO);
        console.info(`[Calibration] Drift detected: ${result.malfunction_start} to ${result.malfunction_end}`);
      } else if (result?.suggested_offset != null) {
        updateFilter('calibrationOffset', result.suggested_offset);
        // Log additional stats from smart suggest algorithm
        const msg = `Suggested: ${result.suggested_offset}m (${result.confidence} confidence, ${result.before_samples} before / ${result.after_samples} after samples)`;
        console.info(`[Calibration] ${msg}`);
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
      const params = {
        station: targetStation,
        start_datetime: filterValues.calibrationStart,
        end_datetime: filterValues.calibrationEnd,
        correction_type: filterValues.calibrationCorrectionType,
      };
      // Only include offset for 'offset' mode
      if (filterValues.calibrationCorrectionType === 'offset') {
        params.offset = filterValues.calibrationOffset;
      } else if (filterValues.calibrationCorrectionType === 'relative') {
        params.reference_station = filterValues.calibrationReference;
        params.expected_gap = filterValues.calibrationExpectedGap ?? 0.0;
      }
      const result = await apiService.commitCalibration(params);
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
