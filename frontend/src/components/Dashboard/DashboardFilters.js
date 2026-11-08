import React from 'react';
import { Card, Form, Button, Collapse, Row, Col } from 'react-bootstrap';
import DateRangePicker from '../DateRangePicker';
import OffsetInput from './OffsetInput';
import DriftPanel from './DriftPanel';
import CustomDropdown from '../CustomDropdown';

const DashboardFilters = ({
  filters,
  stations,
  selectedStations,
  favorites,
  addFavorite,
  removeFavorite,
  isFavorite,
  onFilterChange,
  onDateRangeChange,
  onStationChange,
  onModelChange,
  onExportGraph,
  onExportData,
  onExportCsv,
  isMobile,
  filtersOpen,
  setFiltersOpen,
  calibrationHook,
  selectedPoints,
}) => {
  return (
    <>
      {isMobile && (
        <Button
          variant="primary"
          className="w-100 mb-2"
          onClick={() => setFiltersOpen(!filtersOpen)}
          aria-controls="filters-collapse"
          aria-expanded={filtersOpen}
        >
          {filtersOpen ? '▲ Hide Filters' : '▼ Show Filters'}
        </Button>
      )}

      <Collapse in={filtersOpen || !isMobile}>
        <div id="filters-collapse">
          <Card className="filters-card h-100">
            <Card.Body className="p-2" style={{ maxHeight: '90vh', overflowY: 'auto' }}>
              <h6 className="mb-2">Filters</h6>

              {/* Date Range */}
              <Form.Group className="mb-2">
                <Form.Label className="small mb-1">Date Range</Form.Label>
                <DateRangePicker
                  startDate={filters.startDate}
                  endDate={filters.endDate}
                  onChange={onDateRangeChange}
                />
              </Form.Group>

              {/* Stations */}
              <Form.Group className="mb-2">
                <Form.Label className="small mb-1">Stations ({selectedStations.length}/3)</Form.Label>
                {stations.map(station => (
                  <div key={station} className="d-flex align-items-center">
                    <Form.Check
                      type="checkbox"
                      id={`station-${station.replace(/\s+/g, '-').toLowerCase()}`}
                      label={station}
                      checked={selectedStations.includes(station)}
                      onChange={() => onStationChange(station)}
                      disabled={!selectedStations.includes(station) && selectedStations.length >= 3 && station !== 'All Stations'}
                      className="flex-grow-1"
                    />
                    {station !== 'All Stations' && (
                      <Button
                        variant="link"
                        size="sm"
                        className="p-0 ms-2"
                        onClick={() => isFavorite(station) ? removeFavorite(station) : addFavorite(station)}
                        title={isFavorite(station) ? 'Remove from favorites' : 'Add to favorites'}
                      >
                        {isFavorite(station) ? '⭐' : '☆'}
                      </Button>
                    )}
                  </div>
                ))}
                <small className="text-muted" style={{ fontSize: '0.7rem' }}>Select up to 3 stations</small>
                {favorites.length > 0 && (
                  <div className="mt-1">
                    <small className="text-info" style={{ fontSize: '0.7rem' }}>Favorites: {favorites.join(', ')}</small>
                  </div>
                )}
              </Form.Group>

              {/* Data Type */}
              <Form.Group className="mb-2">
                <Form.Label className="small mb-1">Data Type</Form.Label>
                <CustomDropdown
                  value={filters.dataType}
                  onChange={(value) => onFilterChange('dataType', value)}
                  options={[
                    { value: 'default', label: 'Default' },
                    { value: 'tides', label: 'Tidal Data' }
                  ]}
                />
              </Form.Group>

              {/* Trendline Period */}
              <Form.Group className="mb-2">
                <Form.Label className="small mb-1">Trendline Period</Form.Label>
                <CustomDropdown
                  value={filters.trendline}
                  onChange={(value) => onFilterChange('trendline', value)}
                  options={[
                    { value: 'none', label: 'None' },
                    { value: '7d', label: '7 Days' },
                    { value: '30d', label: '30 Days' },
                    { value: '90d', label: '90 Days' },
                    { value: '1y', label: '1 Year' },
                    { value: 'last_decade', label: 'Last Decade' },
                    { value: 'last_two_decades', label: 'Last Two Decades' },
                    { value: 'all', label: 'All Time' }
                  ]}
                />
              </Form.Group>

              {/* Analysis Type */}
              <Form.Group className="mb-2">
                <Form.Label className="small mb-1">Analysis Type</Form.Label>
                <CustomDropdown
                  value={filters.analysisType}
                  onChange={(value) => onFilterChange('analysisType', value)}
                  options={[
                    { value: 'none', label: 'None' },
                    { value: 'rolling_avg_3h', label: '3-Hour Average' },
                    { value: 'rolling_avg_6h', label: '6-Hour Average' },
                    { value: 'rolling_avg_24h', label: '24-Hour Average' },
                    { value: 'all', label: 'All Analyses' }
                  ]}
                />
              </Form.Group>

              {/* ── Calibration Correction (admins only: calibrationHook is null otherwise) ── */}
              {calibrationHook && (
              <Form.Group className="mb-2">
                <Form.Check
                  type="checkbox"
                  id="calibration-mode-check"
                  label="Calibration Correction"
                  checked={filters.calibrationMode || false}
                  onChange={(e) => onFilterChange('calibrationMode', e.target.checked)}
                  className="small"
                />
                <small className="text-muted d-block" style={{ fontSize: '0.7rem' }}>
                  Non-destructive, audited, reversible
                </small>
              </Form.Group>
              )}

              {filters.calibrationMode && calibrationHook && (
                <div style={{
                  backgroundColor: '#0c1c35',
                  padding: '8px',
                  borderRadius: '4px',
                  border: '1px solid #2a3f5f',
                  marginBottom: '8px',
                }}>
                  <Form.Label className="small mb-1" style={{ color: '#00ff99', fontWeight: 600 }}>
                    Correction Window
                  </Form.Label>

                  <Button
                    variant="outline-success"
                    size="sm"
                    className="w-100 mb-2"
                    style={{ fontSize: '0.75rem' }}
                    disabled={!selectedPoints || selectedPoints.length !== 2}
                    title={!selectedPoints || selectedPoints.length !== 2 ? 'Click two points on the graph first' : undefined}
                    onClick={() => {
                      // Sort by time to ensure start < end. Chart times are local wall-clock times:
                      // format their local parts (toISOString() would shift them to UTC, 2–3 h early).
                      const sorted = [...selectedPoints].sort((a, b) => new Date(a.x) - new Date(b.x));
                      const pad = (n) => String(n).padStart(2, '0');
                      const local = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
                      onFilterChange('calibrationStart', local(new Date(sorted[0].x)));
                      onFilterChange('calibrationEnd', local(new Date(sorted[1].x)));
                    }}
                  >
                    🎯 Use Graph Selection
                  </Button>
                  {(!selectedPoints || selectedPoints.length !== 2) && (
                    <small className="d-block mb-2" style={{ fontSize: '0.65rem', color: '#8FA3BD', marginTop: '-4px' }}>
                      Click two points on the graph to set the window.
                    </small>
                  )}

                  <Form.Group className="mb-1">
                    <Form.Label htmlFor="calibration-start" className="small mb-0" style={{ fontSize: '0.7rem' }}>
                      Start (exact time)
                    </Form.Label>
                    <Form.Control
                      id="calibration-start"
                      type="datetime-local"
                      size="sm"
                      value={filters.calibrationStart || ''}
                      onChange={(e) => onFilterChange('calibrationStart', e.target.value || null)}
                      style={{ fontSize: '0.75rem' }}
                    />
                  </Form.Group>

                  <Form.Group className="mb-1">
                    <Form.Label htmlFor="calibration-end" className="small mb-0" style={{ fontSize: '0.7rem' }}>
                      End (exact time)
                    </Form.Label>
                    <Form.Control
                      id="calibration-end"
                      type="datetime-local"
                      size="sm"
                      value={filters.calibrationEnd || ''}
                      onChange={(e) => onFilterChange('calibrationEnd', e.target.value || null)}
                      style={{ fontSize: '0.75rem' }}
                    />
                  </Form.Group>

                  <Form.Group className="mb-2">
                    <Form.Label htmlFor="calibration-type" className="small mb-0" style={{ fontSize: '0.7rem' }}>
                      Correction Type
                    </Form.Label>
                    <Form.Select
                      id="calibration-type"
                      value={filters.calibrationCorrectionType || 'offset'}
                      onChange={(e) => onFilterChange('calibrationCorrectionType', e.target.value)}
                      size="sm"
                      style={{ fontSize: '0.75rem' }}
                    >
                      <option value="offset">Vertical Offset</option>
                      <option value="interpolate">Interpolate Gap (Snip)</option>
                      <option value="relative">Relative Gap Calibration</option>
                    </Form.Select>
                    {filters.calibrationCorrectionType === 'interpolate' && (
                      <small className="text-info d-block mt-1" style={{ fontSize: '0.65rem' }}>
                        ℹ️ Removes spikes by linear interpolation. Offset field disabled.
                      </small>
                    )}
                  </Form.Group>

                  {filters.calibrationCorrectionType === 'relative' && (
                    <div className="mb-2">
                      <OffsetInput
                        id="calibration-gap"
                        label="Expected gap: Target − Reference (metres)"
                        sliderLabel="Expected gap slider"
                        suggestionLabel="Typical gap"
                        value={filters.calibrationExpectedGap ?? 0}
                        onChange={(v) => onFilterChange('calibrationExpectedGap', v)}
                        onValidity={calibrationHook.setGapValid}
                        suggestion={calibrationHook.gapSuggestion
                          ? { value: calibrationHook.gapSuggestion.value,
                              confidence: `${calibrationHook.gapSuggestion.days} d before, ${calibrationHook.gapSuggestion.confidence}` }
                          : null}
                      />
                      <Button variant="outline-info" size="sm" className="w-100 mb-2" style={{ fontSize: '0.72rem' }}
                              onClick={() => calibrationHook.fetchGapSuggestion(7)}
                              disabled={calibrationHook.isLoadingGap || !filters.calibrationReference || filters.calibrationReference === 'none'}>
                        {calibrationHook.isLoadingGap ? 'Measuring…' : '📏 Measure typical gap (7 days before)'}
                      </Button>
                      <fieldset className="mb-1">
                        <legend className="small mb-1" style={{ fontSize: '0.7rem', float: 'none' }}>Correction strength</legend>
                        <Form.Check type="radio" id="strength-follow" name="calibration-strength" className="small"
                                    label="Follow reference (Target = Ref + Gap)"
                                    checked={(filters.calibrationStrength || 'follow') === 'follow'}
                                    onChange={() => onFilterChange('calibrationStrength', 'follow')} />
                        <Form.Check type="radio" id="strength-level" name="calibration-strength" className="small"
                                    label="Level shift (one constant, keeps own signal)"
                                    checked={filters.calibrationStrength === 'level'}
                                    onChange={() => onFilterChange('calibrationStrength', 'level')} />
                      </fieldset>
                    </div>
                  )}

                  {filters.calibrationCorrectionType === 'offset' && (
                    <OffsetInput
                      value={filters.calibrationOffset ?? 0}
                      onChange={(v) => onFilterChange('calibrationOffset', v)}
                      onValidity={calibrationHook.setOffsetValid}
                      suggestion={calibrationHook.suggestion}
                    />
                  )}

                  <Form.Group className="mb-2">
                    <Form.Label htmlFor="calibration-reference" className="small mb-0" style={{ fontSize: '0.7rem' }}>
                      {filters.calibrationCorrectionType === 'relative' ? 'Reference station' : 'Compare with station'}
                      {calibrationHook.isLoadingReferences && <span style={{ color: '#8FA3BD' }}> · checking coverage…</span>}
                    </Form.Label>
                    <Form.Select
                      id="calibration-reference"
                      size="sm"
                      value={filters.calibrationReference || 'none'}
                      onChange={(e) => onFilterChange('calibrationReference', e.target.value)}
                      style={{ fontSize: '0.75rem' }}
                    >
                      <option value="none">None</option>
                      {(calibrationHook.references
                        ? calibrationHook.references.map((r) => ({
                            value: r.station,
                            label: r.coverage > 0 ? `${r.station} · ${Math.round(r.coverage * 100)}%` : `${r.station} · no data in window`,
                            disabled: r.coverage === 0,
                          }))
                        : (stations || [])
                            .filter((st) => st !== calibrationHook.targetStation && st !== 'All Stations')
                            .map((st) => ({ value: st, label: st, disabled: false }))
                      ).map((o) => (
                        <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>
                      ))}
                    </Form.Select>
                    {calibrationHook.references && (
                      <small className="d-block mt-1" style={{ fontSize: '0.62rem', color: '#8FA3BD' }}>
                        % = share of the window with a reference sample within ±2 min
                      </small>
                    )}
                  </Form.Group>

                  {filters.calibrationCorrectionType === 'relative' && (
                    <Form.Group className="mb-2">
                      <Form.Label htmlFor="drift-threshold" className="small mb-0" style={{ fontSize: '0.7rem' }}>
                        Drift threshold (metres)
                      </Form.Label>
                      <Form.Select id="drift-threshold" size="sm" style={{ fontSize: '0.75rem' }}
                                   value={String(filters.calibrationDriftThreshold ?? 0.05)}
                                   onChange={(e) => onFilterChange('calibrationDriftThreshold', Number(e.target.value))}>
                        <option value="0.02">0.02 m (sensitive)</option>
                        <option value="0.03">0.03 m</option>
                        <option value="0.05">0.05 m (standard)</option>
                        <option value="0.1">0.10 m</option>
                        <option value="0.2">0.20 m (coarse)</option>
                      </Form.Select>
                    </Form.Group>
                  )}

                  <Button
                    variant="outline-info"
                    size="sm"
                    className="w-100 mb-1"
                    style={{ fontSize: '0.75rem' }}
                    onClick={calibrationHook.fetchSuggest}
                    disabled={calibrationHook.isLoadingSuggest}
                  >
                    {calibrationHook.isLoadingSuggest
                      ? 'Detecting…'
                      : filters.calibrationCorrectionType === 'relative' ? '🔎 Detect Drift (snap window)' : '⚡ Auto-Suggest Offset'}
                  </Button>

                  <Button
                    variant="outline-warning"
                    size="sm"
                    className="w-100"
                    style={{ fontSize: '0.75rem' }}
                    onClick={calibrationHook.fetchPreview}
                    disabled={calibrationHook.isLoadingPreview || calibrationHook.offsetBlocked}
                  >
                    {calibrationHook.isLoadingPreview ? 'Loading…' : '👁 Preview Correction'}
                  </Button>

                  {calibrationHook.error && (
                    <small role="alert" className="text-danger d-block mt-1" style={{ fontSize: '0.7rem' }}>
                      {calibrationHook.error}
                    </small>
                  )}

                  {/* Stays visible after "Correct this" switches to offset mode */}
                  <DriftPanel
                    drift={calibrationHook.drift}
                    threshold={filters.calibrationDriftThreshold ?? 0.05}
                    onApplyEpisode={calibrationHook.applyEpisode}
                  />
                </div>
              )}

              {/* Show Anomalies */}
              <Form.Group className="mb-2">
                <Form.Check
                  type="checkbox"
                  label="Show Anomalies"
                  checked={filters.showAnomalies}
                  onChange={(e) => onFilterChange('showAnomalies', e.target.checked)}
                  className="small"
                />
                <small className="text-muted d-block" style={{ fontSize: '0.7rem' }}>
                  Uses Israeli sea level monitoring rules
                </small>
              </Form.Group>

              {/* Prediction Models */}
              <Form.Group className="mb-2">
                <Form.Label className="small mb-1">Prediction Models</Form.Label>
                <div style={{
                  backgroundColor: '#0c1c35',
                  padding: '6px',
                  borderRadius: '4px',
                  border: '1px solid #2a3f5f'
                }}>
                  <Form.Check
                    type="checkbox"
                    id="kalman-check"
                    label="Kalman Filter"
                    checked={filters.predictionModels?.includes('kalman_filter') || false}
                    onChange={() => onModelChange('kalman_filter')}
                    className="small"
                  />
                  <Form.Check
                    type="checkbox"
                    id="ensemble-check"
                    label="Ensemble"
                    checked={filters.predictionModels?.includes('ensemble') || false}
                    onChange={() => onModelChange('ensemble')}
                    className="small"
                  />
                  <Form.Check
                    type="checkbox"
                    id="arima-check"
                    label="ARIMA"
                    checked={filters.predictionModels?.includes('arima') || false}
                    onChange={() => onModelChange('arima')}
                    className="small"
                  />
                </div>
                {selectedStations.length > 3 && filters.predictionModels.length > 0 && (
                  <small className="text-warning" style={{ fontSize: '0.7rem' }}>
                    Max 3 stations
                  </small>
                )}
              </Form.Group>

              {/* Forecast Period */}
              {filters.predictionModels.length > 0 && (
                <Form.Group className="mb-2">
                  <Form.Label className="small mb-1">Forecast Period</Form.Label>
                  <Form.Select
                    size="sm"
                    value={filters.forecastHours}
                    onChange={(e) => onFilterChange('forecastHours', parseInt(e.target.value))}
                  >
                    <option value={24}>24 Hours</option>
                    <option value={48}>48 Hours (2 Days)</option>
                    <option value={72}>72 Hours (3 Days)</option>
                    <option value={168}>1 Week</option>
                    <option value={336}>2 Weeks</option>
                  </Form.Select>
                  <small className="text-muted d-block mt-1">
                    Current: {filters.forecastHours} hours
                  </small>
                </Form.Group>
              )}

              {/* Export Buttons */}
              <Row className="mt-2">
                <Col>
                  <Button
                    variant="outline-primary"
                    size="sm"
                    className="w-100 py-1"
                    onClick={onExportGraph}
                    style={{ fontSize: '0.75rem' }}
                  >
                    Export Graph
                  </Button>
                </Col>
                <Col>
                  <Button
                    variant="outline-primary"
                    size="sm"
                    className="w-100 py-1"
                    onClick={onExportData}
                    style={{ fontSize: '0.75rem' }}
                  >
                    Export Excel
                  </Button>
                </Col>
              </Row>
              {onExportCsv && (
                <Row className="mt-1">
                  <Col>
                    <Button variant="outline-secondary" size="sm" className="w-100 py-1"
                            onClick={onExportCsv} style={{ fontSize: '0.75rem' }}
                            title="Full-resolution CSV generated on the server (corrected values)">
                      Download CSV
                    </Button>
                  </Col>
                </Row>
              )}
            </Card.Body>
          </Card>
        </div>
      </Collapse>
    </>
  );
};

export default React.memo(DashboardFilters);
