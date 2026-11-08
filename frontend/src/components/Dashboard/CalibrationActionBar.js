import React, { useState } from 'react';
import { Button, Modal, Spinner } from 'react-bootstrap';

/**
 * Bottom action bar for calibration (admin only).
 *
 * States:
 *   preview loaded  → summary + "Review & commit" (opens a confirmation dialog)
 *   committed       → result + "Undo" (reverts exactly, via the audit log)
 *   error           → message
 */
const MODE_LABEL = {
  offset: 'Vertical offset',
  interpolate: 'Linear interpolation',
  relative: 'Relative to reference station',
};

const fmt = (v, digits = 3) => (v == null || Number.isNaN(Number(v)) ? '—' : `${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(digits)}`);
const fmtDate = (s) => (s ? new Date(s).toLocaleString() : '—');

const CalibrationActionBar = ({
  preview,          // preview API response or null
  mode,             // offset | interpolate | relative
  offset,           // live slider value (offset mode)
  station,
  error,
  isCommitting,
  commitBlocked = false,
  isReverting,
  commitResult,
  onConfirm,
  onCancel,
  onRevert,
}) => {
  const [showConfirm, setShowConfirm] = useState(false);
  if (!preview && !commitResult && !error) return null;

  const rows = preview?.rows_affected ?? preview?.data?.length ?? 0;
  // Relative mode: the server refuses commits when the reference covers too little of the window.
  const coverage = preview?.coverage;
  const minCoverage = preview?.parameters?.min_coverage;
  const coverageBlocked = preview?.commit_allowed === false;
  const strength = preview?.parameters?.strength;
  const coverageMsg = coverageBlocked
    ? `Reference covers ${Math.round(coverage * 100)}% of the window — ${Math.round(minCoverage * 100)}% is required`
      + (strength === 'follow' ? '. Shorten the window, choose another reference, or use Level shift.' : '.')
    : null;
  const change = mode === 'offset'
    ? `${fmt(offset)} m on every sample`
    : `${fmt(preview?.change_summary?.min)} to ${fmt(preview?.change_summary?.max)} m`;

  const confirm = async () => {
    const ok = await onConfirm();
    if (ok) setShowConfirm(false);
  };

  return (
    <>
      <div className="calibration-action-bar" role="region" aria-label="Calibration actions">
        {error && <span role="alert" className="text-warning me-2">⚠ {error}</span>}

        {commitResult ? (
          <>
            <span className="text-success fw-semibold">
              {commitResult.reverted
                ? `↺ Reverted the last correction for ${commitResult.station} (${commitResult.rows_restored?.toLocaleString() ?? 0} samples restored)`
                : `✓ Saved ${commitResult.rows_updated?.toLocaleString() ?? '?'} corrected samples for ${commitResult.station}`}
            </span>
            {!commitResult.reverted && (
              <Button variant="outline-warning" size="sm" onClick={onRevert} disabled={isReverting}>
                {isReverting ? <Spinner animation="border" size="sm" /> : '↺ Undo'}
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={onCancel}>Close</Button>
          </>
        ) : preview ? (
          <>
            <span className="small">
              <strong>{station}</strong> · {MODE_LABEL[mode] || mode} · {rows.toLocaleString()} samples · {change}
              {coverage != null && !coverageBlocked && <> · reference coverage {Math.round(coverage * 100)}%</>}
            </span>
            {coverageMsg && (
              <span role="alert" className="small fw-semibold" style={{ color: '#FFB454' }}>⚠ {coverageMsg}</span>
            )}
            <Button variant="success" size="sm" onClick={() => setShowConfirm(true)}
                    disabled={isCommitting || commitBlocked || coverageBlocked}
                    title={coverageBlocked ? coverageMsg : commitBlocked ? 'Enter a valid number first' : undefined}>
              Review &amp; commit…
            </Button>
            <Button variant="outline-light" size="sm" onClick={onCancel} disabled={isCommitting}>Cancel</Button>
          </>
        ) : (
          <Button variant="secondary" size="sm" onClick={onCancel}>Close</Button>
        )}
      </div>

      <Modal show={showConfirm} onHide={() => !isCommitting && setShowConfirm(false)} centered>
        <Modal.Header closeButton={!isCommitting}>
          <Modal.Title>Commit calibration correction?</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <dl className="row mb-2 small">
            <dt className="col-5">Station</dt><dd className="col-7">{station}</dd>
            <dt className="col-5">Method</dt><dd className="col-7">{MODE_LABEL[mode] || mode}</dd>
            <dt className="col-5">From</dt><dd className="col-7">{fmtDate(preview?.start_datetime)}</dd>
            <dt className="col-5">To</dt><dd className="col-7">{fmtDate(preview?.end_datetime)}</dd>
            <dt className="col-5">Samples affected</dt><dd className="col-7">{rows.toLocaleString()}</dd>
            <dt className="col-5">Change</dt><dd className="col-7">{change}</dd>
            {coverage != null && (<>
              <dt className="col-5">Reference coverage</dt>
              <dd className="col-7">{Math.round(coverage * 100)}% ({preview?.parameters?.reference_station}, ±{preview?.parameters?.tolerance_seconds ?? 120} s)</dd>
            </>)}
          </dl>
          <p className="small text-muted mb-0">
            Raw sensor data is not modified. The correction is recorded in the audit log with your account
            and can be undone.
          </p>
          {error && <div role="alert" className="alert alert-danger py-2 mt-2 mb-0 small">{error}</div>}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowConfirm(false)} disabled={isCommitting}>Back</Button>
          <Button variant="success" onClick={confirm} disabled={isCommitting || commitBlocked || coverageBlocked}>
            {isCommitting ? <><Spinner animation="border" size="sm" className="me-1" />Saving…</> : 'Commit correction'}
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
};

export default CalibrationActionBar;
