import { useState, useMemo, useCallback, useRef } from 'react';
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
  const [isReverting, setIsReverting] = useState(false);
  // Phase 3 step 1: typed offset validity + suggestion shown next to the input (not auto-applied)
  const [offsetValid, setOffsetValid] = useState(true);
  const [suggestion, setSuggestion] = useState(null);
  const offsetBlocked = filterValues.calibrationCorrectionType === 'offset' && !offsetValid;
  // One request id per confirmed commit: a retry or double click re-sends the same id,
  // and the server applies it once.
  const pendingCommitId = useRef(null);
  const newId = () => (window.crypto?.randomUUID ? window.crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (window.crypto.getRandomValues(new Uint8Array(1))[0] & 15);
        return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
      }));

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
    if (offsetBlocked) {
      setError('Enter a valid offset first');
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
      pendingCommitId.current = null; // new preview → new commit id
      if (!result) {
        setError('Preview returned no data');
        return;
      }
      updateFilter('calibrationPreviewData', result);
    } catch (e) {
      setError(e.data?.error || e.message);
    } finally {
      setIsLoadingPreview(false);
    }
  }, [targetStation, filterValues, updateFilter, offsetBlocked]);

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
        // DB timestamps are local (Israel) wall-clock time without a zone: keep them as-is.
        // (toISOString() converted them to UTC and moved the window 2–3 hours early.)
        const toLocalInput = (ts) => String(ts).replace(' ', 'T').slice(0, 16);
        const startISO = toLocalInput(result.malfunction_start);
        const endISO = toLocalInput(result.malfunction_end);
        updateFilter('calibrationStart', startISO);
        updateFilter('calibrationEnd', endISO);

      } else if (result?.suggested_offset != null) {
        // Offer the suggestion next to the input; the operator applies it with "Use".
        setSuggestion({ value: result.suggested_offset, confidence: result.confidence });
        setCommitResult(null);
      }
    } catch (e) {
      setError(e.data?.error || e.message);
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
    if (offsetBlocked) {
      setError('Enter a valid offset first');
      return false;
    }
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
      if (!pendingCommitId.current) pendingCommitId.current = newId();
      const result = await apiService.commitCalibration(params, pendingCommitId.current);
      pendingCommitId.current = null;
      setCommitResult(result);
      updateFilter('calibrationPreviewData', null);
      updateFilter('calibrationMode', false);
      return true;
    } catch (e) {
      setError(e.data?.error || e.message);
      return false;
    } finally {
      setIsCommitting(false);
    }
  }, [targetStation, filterValues, updateFilter, offsetBlocked]);

  /**
   * Undo the most recent commit for the target station (restores previous offsets exactly).
   */
  const revertLastCalibration = useCallback(async () => {
    if (!targetStation) return false;
    setIsReverting(true);
    setError(null);
    try {
      const result = await apiService.revertCalibration(targetStation, newId());
      setCommitResult({ ...result, reverted: true, station: targetStation });
      return true;
    } catch (e) {
      setError(e.data?.error || e.message);
      return false;
    } finally {
      setIsReverting(false);
    }
  }, [targetStation]);

  /**
   * Cancel without committing — resets all calibration state.
   */
  const cancelCalibration = useCallback(() => {
    updateFilter('calibrationMode', false);
    updateFilter('calibrationPreviewData', null);
    updateFilter('calibrationOffset', 0.0);
    setError(null);
    setCommitResult(null);
    setSuggestion(null);
    setOffsetValid(true);
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
    revertLastCalibration,
    isReverting,
    offsetValid,
    setOffsetValid,
    offsetBlocked,
    suggestion,
  };
};

export default useCalibration;
