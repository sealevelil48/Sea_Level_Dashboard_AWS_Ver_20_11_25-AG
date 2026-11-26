import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Row, Col, Form, Button, Table, Spinner, Alert, Badge } from 'react-bootstrap';
import apiService from '../../services/apiService';

/**
 * Website reports (admin only — the API enforces it; the tab is rendered only for admins).
 *
 * Monthly: hourly means per station (xlsx) + graph (png), in the MM/<Station>/ layout used on the
 * MAPI website. Yearly: per-station daily means, daily / combined / monthly CSVs and the long-term
 * chart. Reports are also made automatically: the 1st of every month (previous month) and 2 January
 * (previous year).
 */
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December'];

const lastMonth = () => {
  const d = new Date();
  d.setDate(0);
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
};

const fmtSize = (b) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} kB`);

const ReportsPanel = () => {
  const lm = lastMonth();
  const [kind, setKind] = useState('monthly');
  const [year, setYear] = useState(lm.year);
  const [month, setMonth] = useState(lm.month);
  const [reports, setReports] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const poll = useRef(null);

  const load = useCallback(async () => {
    try {
      const res = await apiService.listReports();
      setReports(res?.reports || []);
      return res?.reports || [];
    } catch (e) {
      setError(e.data?.detail || e.message);
      return [];
    }
  }, []);

  useEffect(() => {
    load();
    return () => clearInterval(poll.current);
  }, [load]);

  const period = kind === 'monthly' ? `${year}-${String(month).padStart(2, '0')}` : String(year);

  const generate = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    const before = (reports || []).find((r) => r.kind === kind && r.period === period)?.created;
    try {
      await apiService.generateReport(kind === 'monthly' ? { kind, year, month } : { kind, year });
      setMessage(`Generating the ${kind} report for ${period}… it appears below when ready (about a minute).`);
      clearInterval(poll.current);
      let tries = 0;
      poll.current = setInterval(async () => {
        tries += 1;
        const list = await load();
        const done = list.find((r) => r.kind === kind && r.period === period && r.created !== before);
        if (done || tries > 36) {
          clearInterval(poll.current);
          setBusy(false);
          setMessage(done ? `✓ ${done.name} is ready.` : 'Still running — refresh the list in a minute.');
        }
      }, 5000);
    } catch (e) {
      setBusy(false);
      setError(e.data?.detail || e.message);
    }
  };

  const years = [];
  for (let y = new Date().getFullYear(); y >= 2018; y -= 1) years.push(y);

  return (
    <div className="p-1">
      <p className="small mb-2" style={{ color: '#8FA3BD' }}>
        Files for the MAPI website, in the same layout as today&apos;s uploads. Values are the validated
        (calibrated) series. Made automatically on the 1st of each month (previous month) and on 2 January
        (previous year); you can also make one here.
      </p>
      <Form onSubmit={(e) => { e.preventDefault(); generate(); }}>
        <Row className="g-2 align-items-end mb-3">
          <Col xs={12} md="auto">
            <Form.Label htmlFor="report-kind" className="small mb-1">Report</Form.Label>
            <Form.Select id="report-kind" size="sm" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="monthly">Monthly (per station: hourly data + graph)</option>
              <option value="yearly">Yearly (daily / monthly means + long-term chart)</option>
            </Form.Select>
          </Col>
          <Col xs={6} md="auto">
            <Form.Label htmlFor="report-year" className="small mb-1">Year</Form.Label>
            <Form.Select id="report-year" size="sm" value={year} onChange={(e) => setYear(Number(e.target.value))}>
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </Form.Select>
          </Col>
          {kind === 'monthly' && (
            <Col xs={6} md="auto">
              <Form.Label htmlFor="report-month" className="small mb-1">Month</Form.Label>
              <Form.Select id="report-month" size="sm" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
                {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
              </Form.Select>
            </Col>
          )}
          <Col xs={12} md="auto">
            <Button type="submit" size="sm" variant="primary" disabled={busy}>
              {busy ? 'Generating…' : `Generate ${period}`}
            </Button>
          </Col>
        </Row>
      </Form>
      {message && <Alert variant="info" className="py-2 small">{message}</Alert>}
      {error && <Alert variant="danger" className="py-2 small" role="alert">{error}</Alert>}

      <Table size="sm" variant="dark" striped hover responsive className="small align-middle">
        <thead>
          <tr><th>Report</th><th>Period</th><th>Created</th><th>Files</th><th>Notes</th><th aria-label="Download" /></tr>
        </thead>
        <tbody>
          {reports === null && <tr><td colSpan={6} className="text-center"><Spinner animation="border" size="sm" /></td></tr>}
          {reports?.length === 0 && <tr><td colSpan={6} className="text-center text-muted">No reports yet</td></tr>}
          {(reports || []).map((r) => (
            <tr key={r.name}>
              <td><Badge bg={r.kind === 'monthly' ? 'info' : 'warning'} text="dark">{r.kind}</Badge></td>
              <td>{r.period}</td>
              <td className="text-nowrap">{r.created ? new Date(r.created).toLocaleString() : '—'}</td>
              <td>{r.files?.length ?? '—'}{r.size ? ` · ${fmtSize(r.size)}` : ''}</td>
              <td style={{ maxWidth: 360 }}>
                {(r.notes || []).length ? (
                  <details><summary>{r.notes.length} note{r.notes.length > 1 ? 's' : ''}</summary>
                    <ul className="mb-0 ps-3">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul>
                  </details>
                ) : '—'}
              </td>
              <td>
                <Button size="sm" variant="outline-light" onClick={() => apiService.downloadReport(r.name)
                  .catch((e) => setError(e.message))}>
                  Download
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
};

export default ReportsPanel;
