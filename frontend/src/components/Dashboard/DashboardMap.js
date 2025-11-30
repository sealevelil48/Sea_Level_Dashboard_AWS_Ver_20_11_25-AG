import React, { Suspense, lazy } from 'react';
import { Card, Tabs, Tab, Button, Spinner } from 'react-bootstrap';
import GovMapViewer from '../GovMap/GovMapViewer';

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
  // Uses fixed positioning with top/right/bottom/left instead of viewport units
  // to avoid iOS Safari scrollbar width issues that push content right
  const fullscreenContainerStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 9999,
    backgroundColor: '#0c1c35',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    margin: 0,
    padding: 0,
    maxWidth: '100%',
    maxHeight: '100%',
    // Removed transform to fix Leaflet popup positioning
    // Transform creates a new containing block which breaks absolute positioning
    willChange: 'auto' // Use will-change instead for performance if needed
  };

  const renderMapContent = () => {
    // Calculate map height based on fullscreen state
    const mapHeight = isFullscreen ? '100%' : '400px';

    if (mapTab === 'govmap') {
      return govmapReady ? (
        <div style={{
          width: '100%',
          height: mapHeight,
          border: isFullscreen ? 'none' : '1px solid #2a4a8c',
          borderRadius: isFullscreen ? '0' : '8px',
          overflow: 'hidden'
        }}>
          <GovMapViewer
            key={`govmap-${filterEndDate}`}
            selectedDate={filterEndDate}
            apiBaseUrl={API_BASE_URL}
            isFullscreen={isFullscreen}
            isMobile={isMobile}
            style={{
              width: '100%',
              height: '100%'
            }}
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
          width: '100%',
          height: mapHeight
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

  // Single return statement - Card expands to fullscreen to prevent component unmounting
  return (
    <>
      <Card
        className="map-card h-100"
        style={isFullscreen ? fullscreenContainerStyle : {}}
      >
        <Card.Body className="p-2" style={isFullscreen ? { padding: 0, height: '100%' } : {}}>
          {/* Toolbar - hidden in fullscreen */}
          {!isFullscreen && (
            <div className="d-flex justify-content-between align-items-center mb-2">
              <Tabs
                activeKey={mapTab}
                onSelect={(k) => onMapTabChange(k)}
                className="map-tabs"
              >
                <Tab eventKey="govmap" title="GovMap" />
                <Tab eventKey="osm" title="OpenStreetMap" />
              </Tabs>
              {!isMobile && (
                <Button
                  variant="outline-primary"
                  size="sm"
                  onClick={onToggleFullscreen}
                >
                  Fullscreen
                </Button>
              )}
            </div>
          )}

          {/* Map Content - always rendered in same position in React tree */}
          <div style={{
            width: '100%',
            height: isFullscreen ? '100%' : 'auto',
            overflow: 'hidden'
          }}>
            {renderMapContent()}
          </div>
        </Card.Body>
      </Card>

      {/* Mobile fullscreen button - hidden in fullscreen */}
      {!isFullscreen && isMobile && (
        <Card className="map-card mt-2">
          <Card.Body className="p-2 text-center">
            <Button
              variant="outline-primary"
              size="sm"
              onClick={onToggleFullscreen}
              style={{ minWidth: '120px' }}
            >
              Fullscreen
            </Button>
          </Card.Body>
        </Card>
      )}

      {/* Exit fullscreen button - shown only in fullscreen */}
      {isFullscreen && (
        <div
          style={{
            position: 'fixed',
            bottom: '20px',
            left: 0,
            right: 0,
            display: 'flex',
            justifyContent: 'center',
            zIndex: 10001,
            pointerEvents: 'none'
          }}
        >
          <Button
            variant="outline-danger"
            size="sm"
            className="py-1 px-3"
            onClick={onToggleFullscreen}
            style={{
              fontSize: isMobile ? '0.75rem' : '0.85rem',
              fontWeight: '600',
              minWidth: isMobile ? '120px' : '140px',
              pointerEvents: 'auto'
            }}
          >
            Exit Full Screen
          </Button>
        </div>
      )}
    </>
  );
};

export default React.memo(DashboardMap);
