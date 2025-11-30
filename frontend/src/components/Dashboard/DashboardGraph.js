import React, { useRef, useCallback, Suspense, lazy } from 'react';
import { Button, Spinner, Card } from 'react-bootstrap';
import DeltaDisplay from '../DeltaDisplay';

const Plot = lazy(() => import('react-plotly.js'));

const DashboardGraph = ({
  traces,
  layout,
  config,
  selectedPoints,
  onPointSelect,
  onClearSelection,
  isFullscreen,
  onToggleFullscreen,
  isMobile,
  deltaResult
}) => {
  const plotRef = useRef(null);

  const handlePlotClick = useCallback((event) => {
    if (!event.points || event.points.length === 0) return;

    const clickedPoint = event.points[0];
    const pointData = {
      x: clickedPoint.x,
      y: clickedPoint.y,
      station: clickedPoint.data.name || 'Unknown',
      timestamp: clickedPoint.x,
      pointIndex: clickedPoint.pointIndex,
      traceIndex: clickedPoint.curveNumber,
      fullData: clickedPoint.fullData
    };

    onPointSelect(pointData);
  }, [onPointSelect]);

  // Toolbar height for calculating graph height in fullscreen
  const toolbarHeight = 50;

  // Fullscreen container style - covers entire viewport
  const fullscreenContainerStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    width: '100%',
    height: '100%',
    margin: 0,
    padding: 0,
    maxWidth: '100%',
    maxHeight: '100%',
    zIndex: 9999,
    backgroundColor: '#0c1c35',
    display: 'flex',
    flexDirection: 'column'
  };

  // Fullscreen view
  if (isFullscreen) {
    return (
      <div style={fullscreenContainerStyle}>
        {/* Toolbar at top - only show on desktop */}
        {!isMobile && (
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
            <div>
              {selectedPoints.length > 0 && (
                <Button
                  variant="outline-warning"
                  size="sm"
                  onClick={onClearSelection}
                >
                  Clear Selection ({selectedPoints.length})
                </Button>
              )}
            </div>
            <Button
              variant="danger"
              size="sm"
              onClick={onToggleFullscreen}
            >
              Exit
            </Button>
          </div>
        )}

        {/* Graph Content - fills remaining space */}
        <div style={{ flex: 1, overflow: 'hidden', padding: '10px' }}>
          <Suspense fallback={
            <div className="d-flex justify-content-center align-items-center" style={{ height: '100%' }}>
              <Spinner animation="border" variant="primary" />
            </div>
          }>
            <Plot
              ref={plotRef}
              data={traces}
              layout={{
                ...layout,
                height: isMobile
                  ? window.innerHeight - 80
                  : window.innerHeight - toolbarHeight - 40
              }}
              config={config}
              onClick={handlePlotClick}
              style={{ width: '100%' }}
              useResizeHandler={true}
            />
          </Suspense>

          {/* Delta Display */}
          {deltaResult && deltaResult.success && (
            <div className="mt-2">
              <DeltaDisplay
                station1={{
                  name: deltaResult.point1.station,
                  value: deltaResult.point1.value,
                  timestamp: deltaResult.point1.timestamp
                }}
                station2={{
                  name: deltaResult.point2.station,
                  value: deltaResult.point2.value,
                  timestamp: deltaResult.point2.timestamp
                }}
                delta={deltaResult.delta.valueDelta}
                onClear={onClearSelection}
              />
            </div>
          )}
        </div>

        {/* Mobile: Exit button at bottom - same style as Table */}
        {isMobile && (
          <div
            style={{
              position: 'fixed',
              bottom: '20px',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 10000
            }}
          >
            <Button
              variant="outline-danger"
              size="sm"
              className="py-1"
              onClick={onToggleFullscreen}
              style={{ fontSize: '0.75rem' }}
            >
              Exit Full Screen
            </Button>
          </div>
        )}
      </div>
    );
  }

  // Normal view - with Card wrapper
  return (
    <Card className="graph-card h-100">
      <Card.Body className="p-2">
        {/* Toolbar - Desktop: button at top-right, Mobile: no button here */}
        <div className="d-flex justify-content-between align-items-center mb-2">
          <div>
            {selectedPoints.length > 0 && (
              <Button
                variant="outline-warning"
                size="sm"
                onClick={onClearSelection}
                className="me-2"
              >
                Clear Selection ({selectedPoints.length})
              </Button>
            )}
          </div>
          {/* Desktop only: Fullscreen button at top */}
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

        {/* Chart */}
        <Suspense fallback={
          <div className="d-flex justify-content-center align-items-center" style={{ height: '400px' }}>
            <Spinner animation="border" variant="primary" />
          </div>
        }>
          <Plot
            ref={plotRef}
            data={traces}
            layout={{
              ...layout,
              height: 400
            }}
            config={config}
            onClick={handlePlotClick}
            style={{ width: '100%' }}
            useResizeHandler={true}
          />
        </Suspense>

        {/* Delta Display */}
        {deltaResult && deltaResult.success && (
          <div className="mt-2">
            <DeltaDisplay
              station1={{
                name: deltaResult.point1.station,
                value: deltaResult.point1.value,
                timestamp: deltaResult.point1.timestamp
              }}
              station2={{
                name: deltaResult.point2.station,
                value: deltaResult.point2.value,
                timestamp: deltaResult.point2.timestamp
              }}
              delta={deltaResult.delta.valueDelta}
              onClear={onClearSelection}
            />
          </div>
        )}

        {/* Mobile only: Fullscreen button at bottom */}
        {isMobile && (
          <div className="mt-2 text-center">
            <Button
              variant="outline-primary"
              size="sm"
              onClick={onToggleFullscreen}
              style={{ minWidth: '120px' }}
            >
              Fullscreen
            </Button>
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

export default React.memo(DashboardGraph);
