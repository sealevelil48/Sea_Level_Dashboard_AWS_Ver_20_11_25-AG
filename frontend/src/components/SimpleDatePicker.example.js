// frontend/src/components/SimpleDatePicker.example.js
// Usage examples for SimpleDatePicker component

import React, { useState } from 'react';
import SimpleDatePicker from './SimpleDatePicker';
import { Container, Row, Col, Card } from 'react-bootstrap';

/**
 * EXAMPLE 1: Basic Usage
 */
export const BasicExample = () => {
  const [startDate, setStartDate] = useState(new Date('2024-01-01'));
  const [endDate, setEndDate] = useState(new Date('2024-01-31'));

  const handleDateChange = (start, end) => {
    setStartDate(start);
    setEndDate(end);
    console.log('Date range changed:', { start, end });
  };

  return (
    <SimpleDatePicker
      startDate={startDate}
      endDate={endDate}
      onChange={handleDateChange}
    />
  );
};

/**
 * EXAMPLE 2: Without Preset Buttons
 */
export const WithoutPresetsExample = () => {
  const [startDate, setStartDate] = useState(new Date());
  const [endDate, setEndDate] = useState(new Date());

  return (
    <SimpleDatePicker
      startDate={startDate}
      endDate={endDate}
      onChange={(start, end) => {
        setStartDate(start);
        setEndDate(end);
      }}
      showPresets={false}  // Hide preset buttons
    />
  );
};

/**
 * EXAMPLE 3: Inline Layout
 */
export const InlineLayoutExample = () => {
  const [startDate, setStartDate] = useState(new Date());
  const [endDate, setEndDate] = useState(new Date());

  return (
    <SimpleDatePicker
      startDate={startDate}
      endDate={endDate}
      onChange={(start, end) => {
        setStartDate(start);
        setEndDate(end);
      }}
      inline={true}  // Use inline layout
    />
  );
};

/**
 * EXAMPLE 4: In a Dashboard Card (Full Integration Example)
 */
export const DashboardCardExample = () => {
  const [startDate, setStartDate] = useState(new Date('2024-11-01'));
  const [endDate, setEndDate] = useState(new Date('2024-11-20'));
  const [data, setData] = useState([]);

  const handleDateChange = async (start, end) => {
    setStartDate(start);
    setEndDate(end);

    // Fetch data with new date range
    console.log('Fetching data for range:', { start, end });
    // await fetchData(start, end);
  };

  return (
    <Container>
      <Row>
        <Col>
          <Card style={{ backgroundColor: '#1a2332', border: '1px solid #2a3f5f' }}>
            <Card.Body>
              <Card.Title style={{ color: 'white', marginBottom: '20px' }}>
                Select Date Range
              </Card.Title>

              <SimpleDatePicker
                startDate={startDate}
                endDate={endDate}
                onChange={handleDateChange}
              />

              <div style={{ color: '#8899aa', marginTop: '15px' }}>
                Selected: {startDate.toLocaleDateString()} - {endDate.toLocaleDateString()}
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

/**
 * EXAMPLE 5: Replace DateRangePicker in Dashboard.js
 */
export const DashboardReplacementExample = () => {
  // BEFORE (OLD DateRangePicker):
  /*
  import DateRangePicker from './DateRangePicker';

  <DateRangePicker
    startDate={startDate}
    endDate={endDate}
    onChange={(start, end) => {
      setStartDate(start);
      setEndDate(end);
      fetchData(start, end);
    }}
  />
  */

  // AFTER (NEW SimpleDatePicker):
  const [startDate, setStartDate] = useState(new Date());
  const [endDate, setEndDate] = useState(new Date());

  return (
    <SimpleDatePicker
      startDate={startDate}
      endDate={endDate}
      onChange={(start, end) => {
        setStartDate(start);
        setEndDate(end);
        // fetchData(start, end);
      }}
    />
  );
};

/**
 * EXAMPLE 6: Hybrid Approach (Mobile vs Desktop)
 */
export const HybridExample = () => {
  const [startDate, setStartDate] = useState(new Date());
  const [endDate, setEndDate] = useState(new Date());
  const [isMobile] = useState(window.innerWidth < 768);

  // Import both components
  // import SimpleDatePicker from './SimpleDatePicker';
  // import DateRangePicker from './DateRangePicker';

  const handleChange = (start, end) => {
    setStartDate(start);
    setEndDate(end);
  };

  return (
    <>
      {isMobile ? (
        // Mobile: Use SimpleDatePicker (native OS pickers)
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={handleChange}
        />
      ) : (
        // Desktop: Use DateRangePicker (calendar grid)
        // <DateRangePicker
        //   startDate={startDate}
        //   endDate={endDate}
        //   onChange={handleChange}
        // />
        <SimpleDatePicker
          startDate={startDate}
          endDate={endDate}
          onChange={handleChange}
        />
      )}
    </>
  );
};

/**
 * EXAMPLE 7: Custom Styling Override
 */
export const CustomStylingExample = () => {
  const [startDate, setStartDate] = useState(new Date());
  const [endDate, setEndDate] = useState(new Date());

  return (
    <div style={{
      backgroundColor: '#142950',  // Custom background
      padding: '20px',
      borderRadius: '8px'
    }}>
      <SimpleDatePicker
        startDate={startDate}
        endDate={endDate}
        onChange={(start, end) => {
          setStartDate(start);
          setEndDate(end);
        }}
      />
    </div>
  );
};

/**
 * EXAMPLE 8: With Form Submission
 */
export const FormSubmissionExample = () => {
  const [startDate, setStartDate] = useState(new Date());
  const [endDate, setEndDate] = useState(new Date());

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log('Form submitted with dates:', { startDate, endDate });
    // API call or data processing here
  };

  return (
    <form onSubmit={handleSubmit}>
      <SimpleDatePicker
        startDate={startDate}
        endDate={endDate}
        onChange={(start, end) => {
          setStartDate(start);
          setEndDate(end);
        }}
      />

      <button type="submit" style={{ marginTop: '15px' }}>
        Apply Date Range
      </button>
    </form>
  );
};

/**
 * Complete Demo Component
 */
export const SimpleDatePickerDemo = () => {
  return (
    <Container style={{ padding: '20px', backgroundColor: '#0a1628' }}>
      <h1 style={{ color: 'white', marginBottom: '30px' }}>
        SimpleDatePicker Examples
      </h1>

      <Row className="mb-4">
        <Col md={6}>
          <Card style={{ backgroundColor: '#1a2332', border: '1px solid #2a3f5f', marginBottom: '20px' }}>
            <Card.Body>
              <Card.Title style={{ color: 'white' }}>Example 1: Basic Usage</Card.Title>
              <BasicExample />
            </Card.Body>
          </Card>
        </Col>

        <Col md={6}>
          <Card style={{ backgroundColor: '#1a2332', border: '1px solid #2a3f5f', marginBottom: '20px' }}>
            <Card.Body>
              <Card.Title style={{ color: 'white' }}>Example 2: Without Presets</Card.Title>
              <WithoutPresetsExample />
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Row className="mb-4">
        <Col md={6}>
          <Card style={{ backgroundColor: '#1a2332', border: '1px solid #2a3f5f', marginBottom: '20px' }}>
            <Card.Body>
              <Card.Title style={{ color: 'white' }}>Example 3: Inline Layout</Card.Title>
              <InlineLayoutExample />
            </Card.Body>
          </Card>
        </Col>

        <Col md={6}>
          <Card style={{ backgroundColor: '#1a2332', border: '1px solid #2a3f5f', marginBottom: '20px' }}>
            <Card.Body>
              <Card.Title style={{ color: 'white' }}>Example 4: Dashboard Integration</Card.Title>
              <DashboardCardExample />
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default SimpleDatePickerDemo;
