import React, { useMemo, useState } from 'react';
import { Modal, Table, Button, Form, Pagination, Badge } from 'react-bootstrap';

/**
 * Tabular editor for the calibration window (OTT Hydras-style "table view").
 *
 * Shows every raw sample of the window: time, raw (original) value, validated value, state.
 * The operator can tick rows (same selection as the graph) and type corrected values;
 * typed values are previewed and committed with correction type "manual".
 */
const PAGE = 100;

const fmt = (v) => (v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(3));

export const parseTyped = (text) => {
  const t = String(text ?? '').trim().replace(',', '.');
  if (t === '') return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : undefined;   // undefined = invalid text
};

const ValueCell = ({ ts, raw, edit, onEdit }) => {
  const [text, setText] = useState(edit != null ? String(edit) : '');
  const parsed = parseTyped(text);
  const invalid = parsed === undefined || (parsed != null && raw != null && Math.abs(parsed - raw) > 10);
  const commit = () => { if (!invalid) onEdit(ts, parsed); };
  return (
    <Form.Control
      size="sm"
      inputMode="decimal"
      aria-label={`New value for ${ts}`}
      placeholder="—"
      value={text}
      isInvalid={invalid}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === 'Enter') commit(); }}
      className="py-0"
      style={{ maxWidth: 110, fontSize: '0.75rem', height: 24 }}
    />
  );
};

const CalibrationTable = ({ show, onHide, station, samples, selection, edits, onToggle, onSetSelected,
  onEdit, onClearEdits, onPreviewEdits }) => {
  const [onlySelected, setOnlySelected] = useState(false);
  const [onlyFlagged, setOnlyFlagged] = useState(false);
  const [page, setPage] = useState(1);

  const rows = useMemo(() => {
    let list = samples || [];
    if (onlySelected) list = list.filter((r) => selection.has(r.Tab_DateTime));
    if (onlyFlagged) list = list.filter((r) => r.deleted || (r.offset && r.offset !== 0) || edits[r.Tab_DateTime] != null);
    return list;
  }, [samples, selection, edits, onlySelected, onlyFlagged]);

  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const current = Math.min(page, pages);
  const visible = rows.slice((current - 1) * PAGE, current * PAGE);
  const editCount = Object.keys(edits).length;
  const allVisibleSelected = visible.length > 0 && visible.every((r) => selection.has(r.Tab_DateTime));

  const toggleVisible = () => {
    const next = new Set(selection);
    visible.forEach((r) => (allVisibleSelected ? next.delete(r.Tab_DateTime) : next.add(r.Tab_DateTime)));
    onSetSelected([...next]);
  };

  return (
    <Modal show={show} onHide={onHide} size="lg" scrollable aria-labelledby="calibration-table-title"
           data-bs-theme="dark" contentClassName="bg-dark text-light">
      <Modal.Header closeButton>
        <Modal.Title id="calibration-table-title" className="h6">
          {station} · samples in the window ({(samples || []).length.toLocaleString()})
        </Modal.Title>
      </Modal.Header>
      <Modal.Body className="p-2">
        <div className="d-flex flex-wrap gap-3 align-items-center mb-2 small">
          <Form.Check type="switch" id="cal-table-only-selected" label={`Only selected (${selection.size})`}
                      checked={onlySelected} onChange={(e) => { setOnlySelected(e.target.checked); setPage(1); }} />
          <Form.Check type="switch" id="cal-table-only-flagged" label="Only corrected / deleted / typed"
                      checked={onlyFlagged} onChange={(e) => { setOnlyFlagged(e.target.checked); setPage(1); }} />
          <span className="text-muted">Type a value and press Enter. Raw data is never changed.</span>
        </div>
        <Table size="sm" striped hover responsive variant="dark" className="mb-2 align-middle" style={{ fontSize: '0.75rem' }}>
          <thead>
            <tr>
              <th style={{ width: 32 }}>
                <Form.Check aria-label="Select rows on this page" checked={allVisibleSelected} onChange={toggleVisible} />
              </th>
              <th>Time</th>
              <th className="text-end">Raw (m)</th>
              <th className="text-end">Validated (m)</th>
              <th>State</th>
              <th>New value (m)</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr key={r.Tab_DateTime} className={selection.has(r.Tab_DateTime) ? 'table-warning' : undefined}>
                <td>
                  <Form.Check aria-label={`Select ${r.Tab_DateTime}`} checked={selection.has(r.Tab_DateTime)}
                              onChange={() => onToggle(r.Tab_DateTime)} />
                </td>
                <td className="text-nowrap">{r.Tab_DateTime}</td>
                <td className="text-end">{fmt(r.raw_value)}</td>
                <td className="text-end">{r.deleted ? '—' : fmt(r.value)}</td>
                <td>
                  {r.deleted && <Badge bg="danger" className="me-1">deleted</Badge>}
                  {!r.deleted && r.offset !== 0 && <Badge bg="info" text="dark">{`${r.offset > 0 ? '+' : ''}${fmt(r.offset)}`}</Badge>}
                </td>
                <td>
                  <ValueCell key={`${r.Tab_DateTime}:${edits[r.Tab_DateTime] ?? ''}`} ts={r.Tab_DateTime}
                             raw={r.raw_value} edit={edits[r.Tab_DateTime]} onEdit={onEdit} />
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr><td colSpan={6} className="text-center text-muted">No samples</td></tr>
            )}
          </tbody>
        </Table>
        {pages > 1 && (
          <Pagination size="sm" className="mb-0 flex-wrap">
            <Pagination.Prev disabled={current === 1} onClick={() => setPage(current - 1)} />
            <Pagination.Item active>{`${current} / ${pages}`}</Pagination.Item>
            <Pagination.Next disabled={current === pages} onClick={() => setPage(current + 1)} />
          </Pagination>
        )}
      </Modal.Body>
      <Modal.Footer className="justify-content-between">
        <span className="small">{editCount} typed value{editCount === 1 ? '' : 's'}</span>
        <div className="d-flex gap-2">
          <Button variant="outline-secondary" size="sm" onClick={onClearEdits} disabled={!editCount}>Clear typed values</Button>
          <Button variant="warning" size="sm" onClick={onPreviewEdits} disabled={!editCount}>
            Preview typed values
          </Button>
        </div>
      </Modal.Footer>
    </Modal>
  );
};

export default CalibrationTable;
