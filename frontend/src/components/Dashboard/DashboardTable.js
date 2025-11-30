import React, { useMemo } from 'react';
import { Card, Table, Button, Pagination } from 'react-bootstrap';

const DashboardTable = ({
  tableData,
  sortConfig,
  onSort,
  currentPage,
  itemsPerPage,
  onPageChange,
  isFullscreen,
  onToggleFullscreen,
  onExport
}) => {
  // Sort data
  const sortedData = useMemo(() => {
    if (!tableData || tableData.length === 0) return [];

    const sorted = [...tableData].sort((a, b) => {
      let aValue, bValue;

      if (sortConfig.key === 'Tab_DateTime') {
        aValue = a.Tab_DateTime || a.Date || '';
        bValue = b.Tab_DateTime || b.Date || '';
      } else if (sortConfig.key === 'Station') {
        aValue = a.Station || '';
        bValue = b.Station || '';
      } else {
        return 0;
      }

      if (sortConfig.direction === 'asc') {
        return aValue.localeCompare(bValue);
      } else {
        return bValue.localeCompare(aValue);
      }
    });

    return sorted;
  }, [tableData, sortConfig]);

  // Paginate
  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return sortedData.slice(start, start + itemsPerPage);
  }, [sortedData, currentPage, itemsPerPage]);

  const totalPages = Math.ceil(sortedData.length / itemsPerPage);

  // Render sort icon
  const renderSortIcon = (key) => {
    if (sortConfig.key !== key) return ' ⇅';
    return sortConfig.direction === 'asc' ? ' ▲' : ' ▼';
  };

  const containerStyle = isFullscreen ? {
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
    backgroundColor: '#142950',
    overflow: 'auto'
  } : {};

  return (
    <div style={containerStyle}>
      <Card className="table-card h-100">
        <Card.Body className="p-2">
          {/* Toolbar */}
          <div className="d-flex justify-content-between align-items-center mb-2">
            <small className="text-muted">
              Showing {paginatedData.length} of {sortedData.length} records
            </small>
            <div>
              <Button
                variant="outline-primary"
                size="sm"
                onClick={onExport}
                className="me-2"
              >
                Export Excel
              </Button>
              <Button
                variant={isFullscreen ? 'danger' : 'outline-primary'}
                size="sm"
                onClick={onToggleFullscreen}
              >
                {isFullscreen ? 'Exit' : 'Fullscreen'}
              </Button>
            </div>
          </div>

          {/* Table */}
          <div style={{ maxHeight: isFullscreen ? 'calc(100vh - 150px)' : '400px', overflowY: 'auto' }}>
            <Table striped bordered hover variant="dark" size="sm">
              <thead style={{ position: 'sticky', top: 0, backgroundColor: '#1a2332' }}>
                <tr>
                  <th
                    onClick={() => onSort('Tab_DateTime')}
                    style={{ cursor: 'pointer', userSelect: 'none' }}
                  >
                    Date/Time{renderSortIcon('Tab_DateTime')}
                  </th>
                  <th
                    onClick={() => onSort('Station')}
                    style={{ cursor: 'pointer', userSelect: 'none' }}
                  >
                    Station{renderSortIcon('Station')}
                  </th>
                  <th>Sea Level (m)</th>
                  <th>Temp (°C)</th>
                </tr>
              </thead>
              <tbody>
                {paginatedData.map((row, index) => (
                  <tr key={index}>
                    <td>{row.Tab_DateTime || row.Date}</td>
                    <td>{row.Station}</td>
                    <td>{row.Tab_Value_mDepthC1?.toFixed(3) || '-'}</td>
                    <td>{row.Tab_Value_monT2m?.toFixed(1) || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="d-flex justify-content-center mt-2">
              <Pagination size="sm">
                <Pagination.First onClick={() => onPageChange(1)} disabled={currentPage === 1} />
                <Pagination.Prev onClick={() => onPageChange(currentPage - 1)} disabled={currentPage === 1} />

                {[...Array(Math.min(5, totalPages))].map((_, i) => {
                  let pageNum;
                  if (totalPages <= 5) {
                    pageNum = i + 1;
                  } else if (currentPage <= 3) {
                    pageNum = i + 1;
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i;
                  } else {
                    pageNum = currentPage - 2 + i;
                  }
                  return (
                    <Pagination.Item
                      key={pageNum}
                      active={pageNum === currentPage}
                      onClick={() => onPageChange(pageNum)}
                    >
                      {pageNum}
                    </Pagination.Item>
                  );
                })}

                <Pagination.Next onClick={() => onPageChange(currentPage + 1)} disabled={currentPage === totalPages} />
                <Pagination.Last onClick={() => onPageChange(totalPages)} disabled={currentPage === totalPages} />
              </Pagination>
            </div>
          )}
        </Card.Body>
      </Card>
    </div>
  );
};

export default React.memo(DashboardTable);
