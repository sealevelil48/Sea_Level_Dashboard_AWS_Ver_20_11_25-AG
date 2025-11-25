import React from 'react';
import { Card, Form, Button, Collapse, Row, Col } from 'react-bootstrap';
import DateRangePicker from '../DateRangePicker';
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
  isMobile,
  filtersOpen,
  setFiltersOpen
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
                    Export Data
                  </Button>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        </div>
      </Collapse>
    </>
  );
};

export default React.memo(DashboardFilters);
