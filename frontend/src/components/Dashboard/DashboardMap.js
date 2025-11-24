import React, { Suspense, lazy } from 'react';
import { Card, Tabs, Tab, Button, Spinner } from 'react-bootstrap';

const OSMMap = lazy(() => import('../OSMMap'));

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:30886';

const DashboardMap = ({
  mapTab,
  onMapTabChange,
  stations,
  selectedStations,
  graphData,
  forecastData,
  govmapReady,
  filterEndDate,
  isFullscreen,
  onToggleFullscreen,
  _isMobile
}) => {
  const containerStyle = isFullscreen ? {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 9999,
    backgroundColor: '#142950',
    padding: '10px'
  } : {};

  const renderMapContent = () => {
    if (mapTab === 'govmap') {
      return govmapReady ? (
        <div style={{
          width: '100%',
          height: isFullscreen ? 'calc(100vh - 100px)' : '400px',
          border: '1px solid #2a4a8c',
          borderRadius: '8px',
          overflow: 'hidden'
        }}>
          <iframe
            key={`govmap-${filterEndDate}`}
            src={`${API_BASE_URL}/mapframe?end_date=${filterEndDate}`}
            style={{ width: '100%', height: '100%', border: 'none' }}
            title="GovMap"
            allow="geolocation; accelerometer; clipboard-write"
            sandbox="allow-scripts allow-same-origin allow-forms"
            referrerPolicy="no-referrer"
          />
        </div>
      ) : (
        <div className="text-center p-5">
          <Spinner animation="border" variant="primary" />
          <p className="mt-2">Loading map interface...</p>
          <small className="text-muted">
            Dashboard is ready - map loading in background
          </small>
        </div>
      );
    } else if (mapTab === 'osm') {
      return (
        <div style={{ height: isFullscreen ? 'calc(100vh - 100px)' : '400px' }}>
          <Suspense fallback={
            <div className="d-flex justify-content-center align-items-center" style={{ height: '100%' }}>
              <Spinner animation="border" />
            </div>
          }>
            <OSMMap
              key={`osm-map-${selectedStations.join('-')}`}
              stations={stations.filter(s => s !== 'All Stations')}
              currentStation={selectedStations[0]}
              mapData={graphData}
              forecastData={forecastData}
            />
          </Suspense>
        </div>
      );
    }
    return null;
  };

  return (
    <div style={containerStyle}>
      <Card className="map-card h-100">
        <Card.Body className="p-2">
          {/* Toolbar */}
          <div className="d-flex justify-content-between align-items-center mb-2">
            <Tabs
              activeKey={mapTab}
              onSelect={(k) => onMapTabChange(k)}
              className="map-tabs"
            >
              <Tab eventKey="govmap" title="GovMap" />
              <Tab eventKey="osm" title="OpenStreetMap" />
            </Tabs>
            <Button
              variant={isFullscreen ? 'danger' : 'outline-secondary'}
              size="sm"
              onClick={onToggleFullscreen}
            >
              {isFullscreen ? 'Exit' : 'Fullscreen'}
            </Button>
          </div>

          {/* Map Content */}
          {renderMapContent()}
        </Card.Body>
      </Card>
    </div>
  );
};

export default React.memo(DashboardMap);
