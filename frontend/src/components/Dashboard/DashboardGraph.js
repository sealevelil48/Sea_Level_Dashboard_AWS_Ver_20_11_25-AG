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
  onExport,
  _isMobile,
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

  // Apply fullscreen class
  const containerClass = isFullscreen
    ? 'graph-fullscreen-container'
    : '';

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

  return (
    <div className={containerClass} style={containerStyle}>
      <Card className="graph-card h-100">
        <Card.Body className="p-2">
          {/* Toolbar */}
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
            <div>
              <Button
                variant="outline-primary"
                size="sm"
                onClick={onExport}
                className="me-2"
              >
                Export
              </Button>
              <Button
                variant={isFullscreen ? 'danger' : 'outline-secondary'}
                size="sm"
                onClick={onToggleFullscreen}
              >
                {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
              </Button>
            </div>
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
                height: isFullscreen ? window.innerHeight - 150 : 400
              }}
              config={config}
              onClick={handlePlotClick}
              style={{ width: '100%' }}
              useResizeHandler={true}
            />
          </Suspense>

          {/* Delta Display */}
          {deltaResult && (
            <div className="mt-2">
              <DeltaDisplay deltaResult={deltaResult} onClear={onClearSelection} />
            </div>
          )}
        </Card.Body>
      </Card>
    </div>
  );
};

export default React.memo(DashboardGraph);
