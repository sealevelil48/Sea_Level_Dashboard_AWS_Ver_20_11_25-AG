import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import apiService from '../services/apiService';
import {
  selectInBox, nearestSample, mergeSelection, selectionExtent, windowDays,
} from '../utils/calibrationSelection';

export const EDITOR_MAX_DAYS = 14;              // matches the server's 20,000-sample editor limit
const SELECTION_MODES = ['offset', 'interpolate', 'relative', 'delete', 'restore'];

/**
 * Calibration state and API interactions (admin only; the API enforces it).
 *
 * Corrections are stored in the audited calibration layer — raw sensor values are never modified.
 *
 * Phase 3 (Hydras-style):
 *   - one request builder shared by preview / commit / suggest, so they can never disagree
 *   - reference list with per-station coverage of the window (Compare dropdown)
 *   - relative mode: expected gap (typed or suggested from a baseline) and strength (follow | level)
 *   - drift detection: episodes, slow-drift trend and the deviation series; "Correct this" per episode
 *
 * Graphical / tabular editor (OTT Hydras-style):
 *   - samples: every raw sample of the window with its state (raw, offset, deleted)
 *   - selection: points picked on the graph (box or click) or in the table; every operation
 *     then acts on the selection only
 *   - edits: values typed in the table (manual mode)
 *
 * @param {Function} updateFilter - from useFilters
 * @param {Object}   filterValues - computed filter values from useFilters
 * @param {Array}    selectedStations - currently selected station names
 */

// DB timestamps are local (Israel) wall-clock time without a zone: keep them as-is for
// <input type="datetime-local">. (toISOString() would convert to UTC and shift by 2–3 h.)
export const toLocalInput = (ts) => String(ts ?? '').replace(' ', 'T').slice(0, 16);

const newId = () => (window.crypto?.randomUUID ? window.crypto.randomUUID()
  : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (window.crypto.getRandomValues(new Uint8Array(1))[0] & 15);
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    }));

export const useCalibration = ({ updateFilter, filterValues, selectedStations }) => {
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isLoadingSuggest, setIsLoadingSuggest] = useState(false);
  const [isCommitting, setIsCommitting] = useState(false);
  const [isReverting, setIsReverting] = useState(false);
  const [commitResult, setCommitResult] = useState(null);
  const [error, setError] = useState(null);

  // Typed-value validity (offset and expected gap) + suggestions shown next to the inputs
  const [offsetValid, setOffsetValid] = useState(true);
  const [gapValid, setGapValid] = useState(true);
  const [suggestion, setSuggestion] = useState(null);
  const [gapSuggestion, setGapSuggestion] = useState(null);
  const [isLoadingGap, setIsLoadingGap] = useState(false);

  // References with coverage, drift results
  const [references, setReferences] = useState(null);
  const [isLoadingReferences, setIsLoadingReferences] = useState(false);
  const [drift, setDrift] = useState(null);

  // Editor: samples of the window, selected timestamps, typed values
  const [samples, setSamples] = useState(null);
  const [samplesNote, setSamplesNote] = useState(null);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);
  const [samplesVersion, setSamplesVersion] = useState(0);
  const [selection, setSelection] = useState(() => new Set());
  const [selectMode, setSelectMode] = useState(false);
  const [edits, setEdits] = useState({});

  const mode = filterValues.calibrationCorrectionType || 'offset';
  const editCount = Object.keys(edits).length;
  const offsetBlocked = (mode === 'offset' && !offsetValid) || (mode === 'relative' && !gapValid)
    || (mode === 'manual' && editCount === 0);
  const pendingCommitId = useRef(null);
  // Window changes made by drift detection / "Correct this" must not wipe the results that caused them.
  const keepResultsOnNextWindowChange = useRef(false);

  // The first non-"All Stations" station is the target for calibration
  const targetStation = useMemo(
    () => (selectedStations || []).find((s) => s !== 'All Stations') || null,
    [selectedStations]
  );

  const reference = filterValues.calibrationReference && filterValues.calibrationReference !== 'none'
    ? filterValues.calibrationReference : null;

  /** The single source of request parameters for preview, commit and suggest. */
  const buildParams = useCallback((type = mode) => {
    const p = {
      station: targetStation,
      start_datetime: filterValues.calibrationStart,
      end_datetime: filterValues.calibrationEnd,
      correction_type: type,
    };
    if (type === 'offset') p.offset = filterValues.calibrationOffset;
    if (reference) p.reference_station = reference;
    if (type === 'relative') {
      p.expected_gap = filterValues.calibrationExpectedGap ?? 0.0;
      p.strength = filterValues.calibrationStrength || 'follow';
    }
    if (SELECTION_MODES.includes(type) && selection.size > 0) p.timestamps = [...selection];
    if (type === 'manual') {
      p.values = Object.entries(edits).map(([ts, value]) => ({ Tab_DateTime: ts, value }));
    }
    return p;
  }, [targetStation, filterValues, mode, reference, selection, edits]);

  const requireWindow = () => {
    if (!targetStation) { setError('Select a single station first'); return false; }
    if (!filterValues.calibrationStart || !filterValues.calibrationEnd) {
      setError('Set the correction window first'); return false;
    }
    return true;
  };

  // --- Editor samples: every raw sample of the window (graph points + table) -------------
  useEffect(() => {
    const { calibrationStart: start, calibrationEnd: end, calibrationMode: on } = filterValues;
    if (!on || !targetStation || !start || !end) {
      setSamples(null);
      setSamplesNote(null);
      return undefined;
    }
    if (windowDays(start, end) > EDITOR_MAX_DAYS) {
      setSamples(null);
      setSamplesNote(`Point editing needs a window of ${EDITOR_MAX_DAYS} days or less`);
      return undefined;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      setIsLoadingSamples(true);
      try {
        const res = await apiService.calibrationSamples({ station: targetStation, start_datetime: start, end_datetime: end });
        if (cancelled) return;
        setSamples(res);
        setSamplesNote(null);
        // Keep only selected / edited samples that still exist in the window
        const present = new Set((res?.samples || []).map((r) => r.Tab_DateTime));
        setSelection((prev) => new Set([...prev].filter((t) => present.has(t))));
        setEdits((prev) => Object.fromEntries(Object.entries(prev).filter(([t]) => present.has(t))));
      } catch (e) {
        if (!cancelled) { setSamples(null); setSamplesNote(e.data?.error || e.message); }
      } finally {
        if (!cancelled) setIsLoadingSamples(false);
      }
    }, 400);
    return () => { cancelled = true; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetStation, filterValues.calibrationStart, filterValues.calibrationEnd, filterValues.calibrationMode, samplesVersion]);

  // A new target station starts with an empty selection
  useEffect(() => { setSelection(new Set()); setEdits({}); }, [targetStation]);

  /** Box drawn on the chart (or a click: box.click with box.x) → selection. */
  const selectFromChart = useCallback((box) => {
    const list = samples?.samples;
    if (!list?.length || !box) return;
    const how = box.toggle ? 'toggle' : box.additive ? 'add' : 'replace';
    let picked;
    if (box.click) {
      const t = nearestSample(list, box.x, box.maxDistanceMs ?? Infinity);
      picked = t ? [t] : [];
      setSelection((prev) => mergeSelection(prev, picked, box.additive || box.toggle ? 'toggle' : 'replace'));
    } else {
      picked = selectInBox(list, box);
      setSelection((prev) => mergeSelection(prev, picked, how));
    }
    updateFilter('calibrationPreviewData', null); // a new selection invalidates the preview
  }, [samples, updateFilter]);

  const toggleSample = useCallback((ts) => {
    setSelection((prev) => mergeSelection(prev, [ts], 'toggle'));
    updateFilter('calibrationPreviewData', null);
  }, [updateFilter]);

  const setSelected = useCallback((list) => {
    setSelection(new Set(list));
    updateFilter('calibrationPreviewData', null);
  }, [updateFilter]);

  const clearSelection = useCallback(() => {
    setSelection(new Set());
    updateFilter('calibrationPreviewData', null);
  }, [updateFilter]);

  /** Shrink the correction window to the selected samples (exact first/last sample). */
  const fitWindowToSelection = useCallback(() => {
    const ext = selectionExtent(selection);
    if (!ext) return;
    const toInput = (ts) => String(ts).replace(' ', 'T').slice(0, 19);
    updateFilter('calibrationStart', toInput(ext.start));
    updateFilter('calibrationEnd', toInput(ext.end));
  }, [selection, updateFilter]);

  /** Table edit: a typed value (number) or null to clear it. */
  const setEdit = useCallback((ts, value) => {
    setEdits((prev) => {
      const next = { ...prev };
      if (value == null || !Number.isFinite(value)) delete next[ts]; else next[ts] = value;
      return next;
    });
    updateFilter('calibrationPreviewData', null);
  }, [updateFilter]);

  const clearEdits = useCallback(() => { setEdits({}); updateFilter('calibrationPreviewData', null); }, [updateFilter]);

  // --- Compare dropdown: coverage of every other station for this window ----------------
  useEffect(() => {
    if (!targetStation || !filterValues.calibrationStart || !filterValues.calibrationEnd
        || !filterValues.calibrationMode) {
      setReferences(null);
      return undefined;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      setIsLoadingReferences(true);
      try {
        const res = await apiService.calibrationReferences({
          station: targetStation,
          start_datetime: filterValues.calibrationStart,
          end_datetime: filterValues.calibrationEnd,
        });
        if (!cancelled) setReferences(res?.references || []);
      } catch {
        if (!cancelled) setReferences(null); // fall back to the plain station list
      } finally {
        if (!cancelled) setIsLoadingReferences(false);
      }
    }, 400);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [targetStation, filterValues.calibrationStart, filterValues.calibrationEnd, filterValues.calibrationMode]);

  // Reset the reference when it becomes the target or has no data in the window.
  useEffect(() => {
    if (!reference) return;
    const covered = references?.find((r) => r.station === reference);
    if (reference === targetStation || (references && (!covered || covered.coverage === 0))) {
      updateFilter('calibrationReference', 'none');
    }
  }, [reference, targetStation, references, updateFilter]);

  // A different target, window or reference invalidates earlier suggestions and drift results
  // (unless the window was just set from those results).
  useEffect(() => {
    if (keepResultsOnNextWindowChange.current) {
      keepResultsOnNextWindowChange.current = false;
      return;
    }
    setSuggestion(null);
    setGapSuggestion(null);
    setDrift(null);
  }, [targetStation, filterValues.calibrationStart, filterValues.calibrationEnd, reference]);

  /** Set the window from drift results, keeping those results (only if the window really changes). */
  const setWindowFromResults = (startTs, endTs) => {
    const start = toLocalInput(startTs);
    const end = toLocalInput(endTs);
    if (start === filterValues.calibrationStart && end === filterValues.calibrationEnd) return;
    keepResultsOnNextWindowChange.current = true;
    updateFilter('calibrationStart', start);
    updateFilter('calibrationEnd', end);
  };

  // --- Preview ---------------------------------------------------------------------------
  const fetchPreview = useCallback(async (typeOverride) => {
    const type = typeof typeOverride === 'string' ? typeOverride : mode;
    if (!requireWindow()) return;
    if (type === mode && offsetBlocked && type !== 'manual') { setError('Enter a valid number first'); return; }
    if (type === 'relative' && !reference) { setError('Choose a reference station'); return; }
    if (type === 'manual' && editCount === 0) { setError('Type at least one value in the table first'); return; }
    if (type === 'delete' && selection.size === 0) {
      setError('Select the points to delete on the graph or in the table first'); return;
    }
    setIsLoadingPreview(true);
    setError(null);
    try {
      const result = await apiService.previewCalibration(buildParams(type));
      pendingCommitId.current = null; // new preview → new commit id
      if (!result) { setError('Preview returned no data'); return; }
      setCommitResult(null);           // the bar now shows this preview, not the last saved result
      updateFilter('calibrationPreviewData', result);
    } catch (e) {
      setError(e.data?.error || e.message);
    } finally {
      setIsLoadingPreview(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildParams, updateFilter, offsetBlocked, mode, reference, editCount, selection]);

  /** Switch the operation and preview it in one step (editor quick actions, table "Preview typed values"). */
  const previewAs = useCallback((type) => {
    if (type !== mode) updateFilter('calibrationCorrectionType', type);
    return fetchPreview(type);
  }, [mode, updateFilter, fetchPreview]);

  // --- Suggest: offset (no reference) or drift detection (relative + reference) --------------
  const fetchSuggest = useCallback(async () => {
    if (!requireWindow()) return;
    setIsLoadingSuggest(true);
    setError(null);
    try {
      const params = {
        station: targetStation,
        start_datetime: filterValues.calibrationStart,
        end_datetime: filterValues.calibrationEnd,
      };
      if (mode === 'relative') {
        if (!reference) { setError('Choose a reference station'); return; }
        params.reference_station = reference;
        params.expected_gap = filterValues.calibrationExpectedGap ?? 0.0;
        params.threshold = filterValues.calibrationDriftThreshold ?? 0.05;
      }
      const result = await apiService.suggestCalibration(params);
      if (mode === 'relative') {
        setDrift(result);
        if (result?.drift_detected && result.malfunction_start && result.malfunction_end) {
          setWindowFromResults(result.malfunction_start, result.malfunction_end);
        }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetStation, filterValues, updateFilter, mode, reference]);

  // --- Expected gap from a calm baseline before the window -----------------------------------
  const fetchGapSuggestion = useCallback(async (baselineDays = 7) => {
    if (!requireWindow()) return;
    if (!reference) { setError('Choose a reference station'); return; }
    setIsLoadingGap(true);
    setError(null);
    try {
      const r = await apiService.suggestCalibrationGap({
        station: targetStation,
        reference_station: reference,
        start_datetime: filterValues.calibrationStart,
        baseline_days: baselineDays,
      });
      setGapSuggestion({ value: r.gap, confidence: r.confidence, days: r.baseline_days, iqr: r.iqr });
    } catch (e) {
      setError(e.data?.error || e.message);
    } finally {
      setIsLoadingGap(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetStation, filterValues.calibrationStart, filterValues.calibrationEnd, reference]);

  /** Drift episode → correction window + offset prefilled, ready for Preview. */
  const applyEpisode = useCallback((episode) => {
    if (!episode) return;
    setWindowFromResults(episode.start, episode.end);
    updateFilter('calibrationCorrectionType', 'offset');
    updateFilter('calibrationOffset', episode.suggested_offset ?? 0);
    updateFilter('calibrationPreviewData', null);
    setSuggestion({ value: episode.suggested_offset, confidence: `from drift episode, ${episode.type}` });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [updateFilter, filterValues.calibrationStart, filterValues.calibrationEnd]);

  // --- Commit / revert / cancel -------------------------------------------------------------
  const commitCalibration = useCallback(async () => {
    if (!targetStation) return false;
    if (offsetBlocked) { setError('Enter a valid number first'); return false; }
    setIsCommitting(true);
    setError(null);
    try {
      if (!pendingCommitId.current) pendingCommitId.current = newId();
      const result = await apiService.commitCalibration(buildParams(), pendingCommitId.current);
      pendingCommitId.current = null;
      setCommitResult(result);
      updateFilter('calibrationPreviewData', null);
      // Stay in the editor (Hydras-style): reload the samples so the next edit starts from the saved state
      setSelection(new Set());
      setEdits({});
      setSamplesVersion((v) => v + 1);
      setDrift(null);
      return true;
    } catch (e) {
      setError(e.data?.error || e.message);
      return false;
    } finally {
      setIsCommitting(false);
    }
  }, [targetStation, buildParams, updateFilter, offsetBlocked]);

  const revertLastCalibration = useCallback(async () => {
    if (!targetStation) return false;
    setIsReverting(true);
    setError(null);
    try {
      const result = await apiService.revertCalibration(targetStation, newId());
      setCommitResult({ ...result, reverted: true, station: targetStation });
      setSamplesVersion((v) => v + 1);
      return true;
    } catch (e) {
      setError(e.data?.error || e.message);
      return false;
    } finally {
      setIsReverting(false);
    }
  }, [targetStation]);

  const cancelCalibration = useCallback(() => {
    updateFilter('calibrationMode', false);
    updateFilter('calibrationPreviewData', null);
    updateFilter('calibrationOffset', 0.0);
    setError(null);
    setCommitResult(null);
    setSuggestion(null);
    setGapSuggestion(null);
    setDrift(null);
    setOffsetValid(true);
    setGapValid(true);
    setSelection(new Set());
    setEdits({});
    setSelectMode(false);
  }, [updateFilter]);

  /** Close the preview/result bar but stay in the editor. */
  const dismissResult = useCallback(() => {
    updateFilter('calibrationPreviewData', null);
    setCommitResult(null);
    setError(null);
  }, [updateFilter]);

  return {
    targetStation,
    isLoadingPreview,
    isLoadingSuggest,
    isCommitting,
    commitResult,
    error,
    fetchPreview,
    previewAs,
    fetchSuggest,
    commitCalibration,
    cancelCalibration,
    revertLastCalibration,
    isReverting,
    offsetValid,
    setOffsetValid,
    setGapValid,
    offsetBlocked,
    suggestion,
    // Phase 3
    references,
    isLoadingReferences,
    gapSuggestion,
    isLoadingGap,
    fetchGapSuggestion,
    drift,
    applyEpisode,
    // Graphical / tabular editor
    samples,
    samplesNote,
    isLoadingSamples,
    reloadSamples: () => setSamplesVersion((v) => v + 1),
    selection,
    selectMode,
    setSelectMode,
    selectFromChart,
    toggleSample,
    setSelected,
    clearSelection,
    fitWindowToSelection,
    edits,
    editCount,
    setEdit,
    clearEdits,
    dismissResult,
  };
};

export default useCalibration;
