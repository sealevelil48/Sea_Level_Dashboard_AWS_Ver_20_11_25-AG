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
  isMobile
}) => {
  // Fullscreen container style - covers entire viewport
  const fullscreenContainerStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    width: '100vw',
    height: '100vh',
    zIndex: 9999,
    backgroundColor: '#0c1c35',
    display: 'flex',
    flexDirection: 'column'
  };

  // Toolbar height for calculating map height in fullscreen
  const toolbarHeight = 50;

  const renderMapContent = () => {
    // Calculate map height based on fullscreen state
    const mapHeight = isFullscreen
      ? `calc(100vh - ${toolbarHeight}px)`
      : '400px';

    if (mapTab === 'govmap') {
      return govmapReady ? (
        <div style={{
          width: '100%',
          height: mapHeight,
          flex: isFullscreen ? 1 : 'none',
          border: isFullscreen ? 'none' : '1px solid #2a4a8c',
          borderRadius: isFullscreen ? '0' : '8px',
          overflow: 'hidden'
        }}>
          <iframe
            key={`govmap-${filterEndDate}`}
            src={`${API_BASE_URL}/mapframe?end_date=${filterEndDate}`}
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
              display: 'block'
            }}
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
        <div style={{
          height: mapHeight,
          flex: isFullscreen ? 1 : 'none'
        }}>
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

  // Fullscreen view - no Card wrapper, direct layout
  if (isFullscreen) {
    return (
      <div style={fullscreenContainerStyle}>
        {/* Toolbar */}
        <div
          style={{
            height: `${toolbarHeight}px`,
            padding: '8px 16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: '#142950',
            borderBottom: '1px solid #2a4a8c'
          }}
        >
          <Tabs
            activeKey={mapTab}
            onSelect={(k) => onMapTabChange(k)}
            className="map-tabs"
          >
            <Tab eventKey="govmap" title="GovMap" />
            <Tab eventKey="osm" title="OpenStreetMap" />
          </Tabs>
          <Button
            variant="danger"
            size="sm"
            onClick={onToggleFullscreen}
          >
            Exit
          </Button>
        </div>

        {/* Map Content - fills remaining space */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          {renderMapContent()}
        </div>
      </div>
    );
  }

  // Normal view - with Card wrapper
  return (
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
          {/* Desktop: button at top, Mobile: button at bottom */}
          {!isMobile && (
            <Button
              variant="outline-secondary"
              size="sm"
              onClick={onToggleFullscreen}
            >
              Fullscreen
            </Button>
          )}
        </div>

        {/* Map Content */}
        {renderMapContent()}

        {/* Mobile: fullscreen button at bottom */}
        {isMobile && (
          <div className="mt-2 text-center">
            <Button
              variant="outline-secondary"
              size="sm"
              onClick={onToggleFullscreen}
            >
              Fullscreen
            </Button>
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

export default React.memo(DashboardMap);
