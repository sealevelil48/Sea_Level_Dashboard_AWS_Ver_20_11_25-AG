# Delta Display Component - Integration Guide

## Overview
The `DeltaDisplay` component provides a responsive UI for displaying calculated delta values between two selected sea level monitoring stations. It features three display modes (overlay, panel, tooltip), dark theme styling matching the dashboard, and full mobile responsiveness.

## Component Location
- **Component:** `frontend/src/components/DeltaDisplay.js`
- **Styles:** `frontend/src/components/DeltaDisplay.css`

## Features

### Core Functionality
- Display two station comparison with names, values, and timestamps
- Calculate and display delta (difference) between stations
- Visual indicators: color coding and directional arrows
- "Clear Selection" button to reset comparison
- Responsive design for mobile and desktop

### Display Modes
1. **Overlay** (default): Fixed position overlay on the right side of the screen
2. **Panel**: Full-width panel component for inline display
3. **Tooltip**: Compact floating tooltip display

### Visual Indicators
- **Positive Delta (↑)**: Green color (#34d399) - Station 2 is higher
- **Negative Delta (↓)**: Red color (#f87171) - Station 1 is higher
- **Neutral Delta (→)**: Blue color (#a0c8f0) - Levels are equal

## Props API

```javascript
DeltaDisplay.propTypes = {
  station1: {
    name: string,      // Station name (e.g., "Haifa")
    value: number,     // Sea level value in meters
    timestamp: string  // ISO timestamp or date string
  },
  station2: {
    name: string,      // Station name (e.g., "Acre")
    value: number,     // Sea level value in meters
    timestamp: string  // ISO timestamp or date string
  },
  delta: number,       // Calculated difference (station2 - station1)
  onClear: function,   // Callback when user clicks clear button
  position: string,    // 'overlay' | 'panel' | 'tooltip' (default: 'overlay')
  isMobile: boolean    // Mobile device flag for responsive styling
}
```

## Integration with Dashboard.js

### Step 1: Import the Component

Add to the imports section of `Dashboard.js`:

```javascript
import DeltaDisplay from './DeltaDisplay';
```

### Step 2: Add State Management

Add these state variables to manage delta display:

```javascript
const [deltaData, setDeltaData] = useState(null);
const [selectedStationsForDelta, setSelectedStationsForDelta] = useState([]);
```

### Step 3: Create Selection Handler

Add a handler for station selection (this would be triggered by clicking on graph data points or table rows):

```javascript
const handleStationSelection = (stationName, value, timestamp) => {
  setSelectedStationsForDelta(prev => {
    if (prev.length === 0) {
      // First station selected
      return [{ name: stationName, value, timestamp }];
    } else if (prev.length === 1) {
      // Second station selected - calculate delta
      const station1 = prev[0];
      const station2 = { name: stationName, value, timestamp };
      const delta = station2.value - station1.value;

      setDeltaData({
        station1,
        station2,
        delta
      });

      return [station1, station2];
    } else {
      // Reset and start over
      setDeltaData(null);
      return [{ name: stationName, value, timestamp }];
    }
  });
};
```

### Step 4: Create Clear Handler

```javascript
const handleClearDelta = () => {
  setDeltaData(null);
  setSelectedStationsForDelta([]);
};
```

### Step 5: Render the Component

Add the DeltaDisplay component to your render method (place it after the main content):

```javascript
{/* Delta Display - shows when two stations are selected */}
{deltaData && (
  <DeltaDisplay
    station1={deltaData.station1}
    station2={deltaData.station2}
    delta={deltaData.delta}
    onClear={handleClearDelta}
    position="overlay"  // or "panel" or "tooltip"
    isMobile={isMobile}
  />
)}
```

### Step 6: Add Click Handlers to Graph

For Plotly graph integration, add click event handling:

```javascript
<Plot
  ref={plotRef}
  data={createPlot.data}
  layout={createPlot.layout}
  config={{
    // ... existing config
  }}
  onClick={(data) => {
    if (data.points && data.points.length > 0) {
      const point = data.points[0];
      handleStationSelection(
        point.data.name,        // Station name
        point.y,                // Value
        point.x                 // Timestamp
      );
    }
  }}
  style={{ width: '100%', height: '100%' }}
/>
```

### Step 7: Add Click Handlers to Table (Optional)

For table row selection:

```javascript
<tr
  key={idx}
  onClick={() => handleStationSelection(
    row.Station,
    row.Tab_Value_mDepthC1,
    row.Tab_DateTime
  )}
  style={{ cursor: 'pointer' }}
>
  {/* ... table cells */}
</tr>
```

## Usage Examples

### Example 1: Overlay Display (Default)

```javascript
<DeltaDisplay
  station1={{
    name: "Haifa",
    value: 0.256,
    timestamp: "2025-11-20T14:30:00Z"
  }}
  station2={{
    name: "Acre",
    value: 0.312,
    timestamp: "2025-11-20T14:30:00Z"
  }}
  delta={0.056}
  onClear={() => console.log('Clear delta')}
  position="overlay"
  isMobile={false}
/>
```

### Example 2: Panel Display

```javascript
<DeltaDisplay
  station1={{
    name: "Ashdod",
    value: 0.189,
    timestamp: "2025-11-20T14:30:00Z"
  }}
  station2={{
    name: "Ashkelon",
    value: 0.143,
    timestamp: "2025-11-20T14:30:00Z"
  }}
  delta={-0.046}
  onClear={handleClearDelta}
  position="panel"
  isMobile={false}
/>
```

### Example 3: Tooltip Display (Mobile)

```javascript
<DeltaDisplay
  station1={{
    name: "Eilat",
    value: 0.401,
    timestamp: "2025-11-20T14:30:00Z"
  }}
  station2={{
    name: "Haifa",
    value: 0.256,
    timestamp: "2025-11-20T14:30:00Z"
  }}
  delta={-0.145}
  onClear={handleClearDelta}
  position="tooltip"
  isMobile={true}
/>
```

## Styling and Customization

### Theme Colors
The component uses the dashboard's dark theme:
- Background: `#142950`
- Border: `#3b82f6`
- Text: `white`, `#a0c8f0`
- Positive: `#34d399` (green)
- Negative: `#f87171` (red)
- Neutral: `#a0c8f0` (blue)

### Responsive Breakpoints
- Desktop: > 992px
- Tablet: 768px - 992px
- Mobile: < 768px
- Small Mobile: < 576px

### Custom Positioning

To customize the overlay position, modify the CSS:

```css
.delta-overlay {
  position: fixed;
  top: 50%;           /* Vertical position */
  right: 20px;        /* Horizontal position */
  transform: translateY(-50%);
}
```

## Accessibility

- Proper ARIA labels on buttons
- Keyboard navigation support
- High contrast colors for readability
- Responsive text sizing
- Touch-friendly button sizes on mobile

## Browser Compatibility

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- Mobile browsers (iOS Safari, Chrome Mobile)

## Performance Considerations

- Component is memoized with `React.memo` to prevent unnecessary re-renders
- CSS animations use GPU-accelerated properties
- Minimal DOM manipulation
- Efficient event handlers

## Troubleshooting

### Issue: Component not displaying
**Solution:** Ensure both station1 and station2 props are provided with valid data.

### Issue: Styling conflicts
**Solution:** Check that `DeltaDisplay.css` is imported after global styles but before component-specific overrides.

### Issue: Mobile responsiveness issues
**Solution:** Ensure the `isMobile` prop is correctly passed based on window width detection.

### Issue: Click handlers not working
**Solution:** Verify that `onClear` callback is properly defined and passed to the component.

## Future Enhancements

Potential improvements for future versions:
1. Add drag-and-drop repositioning for overlay mode
2. Support for more than 2 station comparison
3. Historical delta trend visualization
4. Export delta data to CSV/Excel
5. Real-time delta updates with WebSocket integration
6. Statistical analysis (mean, median, std dev)
7. Configurable animation preferences
8. Custom color themes

## Testing

### Unit Tests
```javascript
// Example test cases
describe('DeltaDisplay', () => {
  it('should render with valid props', () => {
    // Test rendering
  });

  it('should calculate correct delta color', () => {
    // Test color logic
  });

  it('should call onClear when button clicked', () => {
    // Test callback
  });

  it('should format timestamps correctly', () => {
    // Test formatting
  });
});
```

## Support

For issues or questions:
- Check the component source code for inline documentation
- Review this integration guide
- Test with the provided examples
- Verify prop types and data formats

---

**Component Version:** 1.0
**Last Updated:** November 2025
**Author:** Agent 10
**Dashboard Version:** AWS Ver 20_11_25
