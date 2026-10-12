import React from 'react';
import { Button, Spinner } from 'react-bootstrap';

/**
 * Floating action bar that appears at the bottom of the screen when the user
 * has loaded a calibration preview and needs to confirm or cancel.
 *
 * Props:
 *   isVisible     {boolean}  — show/hide (controlled by parent)
 *   offset        {number}   — the offset value being applied (metres)
 *   station       {string}   — target station name
 *   isCommitting  {boolean}  — true while the commit request is in-flight
 *   commitResult  {object}   — API response after a successful commit, or null
 *   onConfirm     {Function} — called when the user clicks "Confirm Update"
 *   onCancel      {Function} — called when the user clicks "Cancel" or "Close"
 */
const CalibrationActionBar = ({
  isVisible,
  offset,
  station,
  isCommitting,
  commitResult,
  onConfirm,
  onCancel,
}) => {
  if (!isVisible) return null;

  const offsetLabel = offset >= 0 ? `+${offset}` : `${offset}`;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 9998,
        background: 'rgba(10, 20, 40, 0.97)',
        borderTop: '1px solid #2a3f5f',
        padding: '10px 24px',
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        boxShadow: '0 -4px 16px rgba(0,0,0,0.4)',
      }}
    >
      {commitResult ? (
        /* ── Success state ── */
        <>
          <span style={{ color: '#00ff99', fontWeight: 600 }}>
            ✓ Updated {commitResult.rows_updated?.toLocaleString() ?? '?'} rows for{' '}
            <strong>{commitResult.station}</strong>
          </span>
          <Button variant="secondary" size="sm" onClick={onCancel}>
            Close
          </Button>
        </>
      ) : (
        /* ── Pending-confirm state ── */
        <>
          <span style={{ color: '#aab', fontSize: '0.85rem' }}>
            Calibration ready to commit:&nbsp;
            <strong style={{ color: '#00ff99' }}>{station}</strong>
            &nbsp;&nbsp;|&nbsp;&nbsp;
            Offset:&nbsp;
            <strong style={{ color: '#00ff99' }}>{offsetLabel}&nbsp;m</strong>
          </span>

          <Button
            variant="success"
            size="sm"
            disabled={isCommitting}
            onClick={onConfirm}
            style={{ minWidth: 130 }}
          >
            {isCommitting ? (
              <>
                <Spinner animation="border" size="sm" className="me-1" />
                Saving…
              </>
            ) : (
              '✓ Confirm Update'
            )}
          </Button>

          <Button variant="danger" size="sm" onClick={onCancel} disabled={isCommitting}>
            ✗ Cancel
          </Button>
        </>
      )}
    </div>
  );
};

export default CalibrationActionBar;
