# Sea Level Dashboard - User Manual

Version 2.0.0 | Last Updated: November 2025

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Dashboard Overview](#dashboard-overview)
4. [Features and Workflows](#features-and-workflows)
5. [Advanced Features](#advanced-features)
6. [Troubleshooting](#troubleshooting)
7. [FAQ](#faq)
8. [Glossary](#glossary)

---

## Introduction

### What is the Sea Level Dashboard?

The Sea Level Dashboard is a comprehensive monitoring and analysis system for tracking sea level measurements across Israeli coastal monitoring stations. It provides real-time data visualization, predictive analytics, and anomaly detection to support maritime operations, research, and environmental monitoring.

### Who Should Use This System?

- **Maritime Operations**: Harbor masters, port authorities, and navigation teams
- **Researchers**: Oceanographers, climate scientists, and environmental researchers
- **Government Agencies**: Environmental protection agencies and coastal management
- **Weather Services**: Meteorological services and forecast teams
- **General Public**: Anyone interested in sea level data and coastal conditions

### Key Capabilities

- Monitor real-time sea level measurements from 6 coastal stations
- Visualize historical data with interactive charts and maps
- Detect anomalies and outliers using advanced algorithms
- Generate predictions up to 7 days in advance
- Compare multiple stations simultaneously
- Export data for external analysis
- Access weather forecasts and warnings

---

## Getting Started

### System Requirements

**For Desktop/Laptop Use:**
- Modern web browser (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
- Internet connection (minimum 1 Mbps)
- Screen resolution: 1280x720 or higher (1920x1080 recommended)
- JavaScript enabled

**For Mobile/Tablet Use:**
- iOS 13+ or Android 8+
- Mobile browser with JavaScript support
- 3G/4G/WiFi connection

### Accessing the Dashboard

1. **Open Your Web Browser**
   Navigate to the dashboard URL provided by your administrator
   - Development: `http://localhost:30887`
   - Production: `https://your-domain.com`

2. **First Time Setup**
   - The dashboard loads automatically
   - No login required (public access mode)
   - Wait for initial data load (5-10 seconds)

3. **Verify Connection**
   - Check status indicator in top-right corner
   - Green dot = Connected and receiving data
   - Red dot = Connection issue (see Troubleshooting)

### Interface Overview

```
┌─────────────────────────────────────────────────────────┐
│  Sea Level Dashboard                         🟢 Online  │
├─────────────────────────────────────────────────────────┤
│  [Station ▼] [Date Range] [Options] [Export] [⚙]      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌──────────────────────────┐ │
│  │   Latest Readings   │  │    Delta Comparison      │ │
│  │                     │  │                          │ │
│  └─────────────────────┘  └──────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│  [Graph] [Table] [Map] [Forecast]                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│              Interactive Chart Area                     │
│                                                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Dashboard Overview

### Navigation Bar

**Station Selector**
- Dropdown menu showing all available stations
- Options: Acre, Haifa, Ashdod, Ashkelon, Yafo, Eilat, All Stations
- Multi-select: Hold Ctrl/Cmd to select up to 3 stations
- Favorites: Star icon to mark frequently used stations

**Date Range Picker**
- Quick select buttons:
  - Last 24 Hours
  - Last 7 Days
  - Last 30 Days
  - Last 90 Days
  - Last Year
  - Custom Range
- Custom range: Click dates to select start and end
- Maximum range: 365 days

**View Tabs**
- **Graph View**: Interactive time-series chart
- **Table View**: Detailed tabular data
- **Map View**: Geographic station visualization
- **Forecast View**: Predictions and forecasts

### Status Cards

**Latest Readings Card**
Displays most recent measurement for selected station(s):
- Current sea level value (in meters)
- Timestamp of measurement
- Temperature (if available)
- Quality indicator (Good, Fair, Poor)

**Delta Comparison Card**
Shows change from previous measurement:
- Delta value with +/- indicator
- Percentage change
- Color coding:
  - Green: Rising (+)
  - Red: Falling (-)
  - Yellow: No significant change
- Time period of comparison (configurable)

**Warnings Card** (when applicable)
Displays active weather warnings:
- IMS weather alerts
- Sea condition warnings
- Anomaly detections
- System alerts

---

## Features and Workflows

### Workflow 1: Viewing Current Sea Level

**Objective**: Check the current sea level at a specific station

**Steps:**

1. **Select Station**
   - Click station dropdown in navigation bar
   - Select desired station (e.g., "Acre")
   - Dashboard updates automatically

2. **View Latest Reading**
   - Look at "Latest Readings" card
   - Current value displayed in large font
   - Timestamp shows when measured

3. **Check Delta**
   - Review "Delta Comparison" card
   - See how much the level has changed
   - Green arrow = rising, Red arrow = falling

**Example:**
```
Latest Readings
Station: Acre
Value: 1.234 m
Time: 2025-01-15 10:30
Temp: 18.5°C
Status: Good

Delta Comparison
Change: +0.012 m (↑)
From: 2025-01-15 10:24
Trend: Rising
```

**Interpretation:**
- Sea level at Acre is currently 1.234 meters
- It has risen 0.012 meters in the last 6 minutes
- Water temperature is 18.5°C
- Data quality is good

### Workflow 2: Analyzing Historical Trends

**Objective**: Examine sea level patterns over the past month

**Steps:**

1. **Select Date Range**
   - Click "Last 30 Days" button
   - Or use custom range picker

2. **Choose Visualization**
   - Click "Graph" tab for chart view
   - Interactive chart displays automatically

3. **Interact with Chart**
   - **Zoom**: Scroll wheel or pinch gesture
   - **Pan**: Click and drag
   - **Tooltip**: Hover over data point
   - **Reset**: Click "Reset Zoom" button

4. **Enable Trendline** (optional)
   - Click settings icon ⚙
   - Select "Trendline" → "Linear" or "Polynomial"
   - Trendline overlays on chart

5. **View Rolling Averages** (optional)
   - Settings → "Rolling Average"
   - Select window: 3h, 6h, or 24h
   - Smoothed line appears on chart

**Chart Controls:**
- **Zoom In**: Scroll up or Ctrl + Plus
- **Zoom Out**: Scroll down or Ctrl + Minus
- **Pan**: Click + Drag
- **Reset**: Double-click or "Reset Zoom" button
- **Download**: Click download icon for PNG export

**[Screenshot Placeholder: Monthly Trend Chart]**
*Description: Interactive Chart.js graph showing 30 days of sea level data for Acre station with linear trendline and 24-hour rolling average enabled. X-axis shows dates from Jan 1-31, Y-axis shows sea level in meters ranging from 0.8 to 1.6m.*

### Workflow 3: Comparing Multiple Stations

**Objective**: Compare sea level behavior across different locations

**Steps:**

1. **Multi-Select Stations**
   - Hold Ctrl (Windows/Linux) or Cmd (Mac)
   - Click up to 3 stations in dropdown
   - Example: Acre, Yafo, Eilat

2. **Adjust View**
   - Graph tab shows all stations on same chart
   - Each station has different color
   - Legend shows which color represents which station

3. **Analyze Differences**
   - Look for patterns across stations
   - Mediterranean stations (Acre, Yafo) typically sync
   - Eilat (Red Sea) shows different patterns
   - Time lag between stations indicates wave propagation

4. **Use Station Differential Analysis**
   - Settings → "Analysis Type" → "Station Diff"
   - Select two stations to compare
   - Chart shows difference: Station A - Station B
   - Helps identify relative changes

**Color Legend:**
- Blue: Acre
- Green: Yafo
- Orange: Ashkelon
- Red: Eilat

**[Screenshot Placeholder: Multi-Station Comparison]**
*Description: Graph view showing three overlapping time-series lines for Acre (blue), Yafo (green), and Eilat (red) over 7 days. Legend in top-right corner. Mediterranean stations show synchronized tidal patterns while Eilat displays distinct pattern.*

### Workflow 4: Detecting and Understanding Anomalies

**Objective**: Identify unusual sea level measurements

**Steps:**

1. **Enable Anomaly Detection**
   - Click settings icon ⚙
   - Toggle "Show Anomalies" → ON
   - Dashboard processes data (may take 5-10 seconds)

2. **Review Detected Anomalies**
   - Red markers appear on chart at anomaly points
   - Click marker to see details:
     - Measured value
     - Expected value (based on baseline)
     - Deviation amount
     - Confidence level
     - Validation rule violated

3. **Understand Anomaly Types**
   - **Spike**: Sudden increase > 3 standard deviations
   - **Drop**: Sudden decrease > 3 standard deviations
   - **Plateau**: Extended period with no variation
   - **Rate Change**: Unusually rapid rise/fall

4. **View Anomaly Report**
   - Click "Anomalies" button in toolbar
   - Opens detailed report with:
     - Total anomalies detected
     - Percentage of data flagged
     - List of all anomalies with timestamps
     - Suggested corrections

5. **Export Anomaly Data**
   - Click "Export" → "Anomalies Only"
   - Downloads Excel file with flagged records

**Anomaly Indicators:**
- 🔴 Red Dot: High confidence anomaly
- 🟡 Yellow Dot: Medium confidence anomaly
- ⚠️ Warning Icon: System alert

**[Screenshot Placeholder: Anomaly Detection]**
*Description: Graph view of sea level data with normal measurements in blue line and red circular markers highlighting 3 anomalies. Tooltip visible on one anomaly showing: "Anomaly Detected | Time: Jan 5, 14:30 | Measured: 2.45m | Expected: 1.23m | Deviation: +1.22m | Confidence: 95%"*

### Workflow 5: Generating Predictions

**Objective**: Forecast sea level for the next 48 hours

**Steps:**

1. **Select Station**
   - Choose station for prediction
   - Note: Can predict one station at a time

2. **Configure Prediction**
   - Settings → "Prediction Model"
   - Select model:
     - **Kalman Filter**: Best for 24-72 hours
     - **Prophet**: Best for weekly forecasts
   - Set "Forecast Hours": 24, 48, 72, or 168

3. **Generate Forecast**
   - Click "Generate Prediction" button
   - Processing takes 3-10 seconds depending on model
   - Progress indicator shows status

4. **View Results**
   - Prediction appears as dashed line extending from current time
   - Shaded area shows confidence interval
   - Tooltip shows:
     - Forecast timestamp
     - Predicted value
     - Confidence bounds (lower/upper)

5. **Compare Models** (optional)
   - Enable both Kalman and Prophet
   - Compare predictions side-by-side
   - Model accuracy shown in legend

**Model Selection Guide:**

| Use Case | Recommended Model | Typical Accuracy |
|----------|------------------|-----------------|
| Next 24 hours | Kalman Filter | ±3-5 cm |
| Next 48-72 hours | Kalman Filter | ±5-8 cm |
| Next 7 days | Prophet | ±10-15 cm |
| Seasonal trends | Prophet | ±15-20 cm |

**[Screenshot Placeholder: Prediction Forecast]**
*Description: Graph showing historical data (solid blue line) from Jan 1-15, with Kalman Filter prediction (dashed blue line) extending from Jan 15-17. Light blue shaded area represents 95% confidence interval. Legend shows "Historical Data" and "Kalman Filter (48h forecast, MAPE: 2.3%)".*

### Workflow 6: Exporting Data

**Objective**: Download sea level data for offline analysis

**Steps:**

1. **Select Data to Export**
   - Choose station(s)
   - Set date range
   - Apply any filters (anomalies, predictions)

2. **Choose Export Format**
   - Click "Export" button in toolbar
   - Select format:
     - **Excel (.xlsx)**: Full data with all columns
     - **CSV (.csv)**: Text format for imports
     - **JSON**: For programmatic access

3. **Configure Export Options**
   - Select columns to include:
     - Station name
     - Timestamp
     - Sea level value
     - Temperature
     - Quality indicators
     - Anomaly flags
     - Predictions
   - Choose decimal precision (2, 3, or 4 places)
   - Include metadata (optional)

4. **Download File**
   - Click "Download" button
   - File saves to default download folder
   - Filename format: `sealevel_[station]_[startdate]_[enddate].xlsx`

**Export File Structure (Excel):**

| Column | Description | Example |
|--------|-------------|---------|
| Station | Station name | Acre |
| DateTime | ISO timestamp | 2025-01-15T10:30:00 |
| Value_m | Sea level in meters | 1.234 |
| Temp_C | Temperature in Celsius | 18.5 |
| Quality | Data quality flag | Good |
| IsAnomaly | Anomaly flag | FALSE |
| Prediction | Predicted value (if applicable) | 1.245 |

**[Screenshot Placeholder: Export Dialog]**
*Description: Modal dialog titled "Export Data" showing checkboxes for column selection (all checked), dropdown for format (Excel selected), slider for decimal precision (set to 3), and two buttons: "Cancel" and "Download". Preview pane at bottom shows first 5 rows of data to be exported.*

---

## Advanced Features

### Favorites System

**Purpose**: Quickly access frequently monitored stations

**How to Use:**

1. **Add to Favorites**
   - Hover over station name in dropdown
   - Click star icon ★
   - Star turns gold ⭐

2. **Access Favorites**
   - Favorites appear at top of station list
   - Separated by horizontal line
   - Quick-select from favorites section

3. **Remove from Favorites**
   - Click gold star ⭐
   - Returns to regular star ★

**Use Cases:**
- Monitor home port station daily
- Track multiple research sites
- Quick comparison of key stations

### Advanced Analysis Tools

#### Rolling Averages

Smooth out short-term fluctuations to see underlying trends.

**Configuration:**
- Settings → "Rolling Average" → Select window
- Options: 3 hours, 6 hours, 24 hours
- Multiple windows can be enabled simultaneously

**Use Cases:**
- Remove tidal noise to see climate trends
- Identify gradual changes masked by variations
- Compare short-term vs long-term averages

#### Trendline Fitting

Add statistical trendlines to identify patterns.

**Types:**
- **Linear**: Straight line (constant rate of change)
- **Polynomial**: Curved line (changing rate)
- **Moving Average**: Smoothed line (local trends)

**Configuration:**
- Settings → "Trendline" → Select type
- Polynomial degree: 2 (quadratic) or 3 (cubic)
- Moving average window: 24h, 48h, or 7d

#### Station Differential

Calculate and visualize the difference between two stations.

**Formula:** `Diff = Station A Value - Station B Value`

**Configuration:**
- Settings → "Analysis Type" → "Station Diff"
- Select Station A and Station B
- Chart shows differential over time

**Interpretation:**
- Positive values: Station A higher than Station B
- Negative values: Station B higher than Station A
- Zero line: Stations at same level
- Trend: Increasing divergence or convergence

**Use Cases:**
- Compare Mediterranean and Red Sea levels
- Detect wave propagation between stations
- Identify geographic variations

### Map View Features

#### Interactive Map

**Controls:**
- **Zoom**: +/- buttons or scroll wheel
- **Pan**: Click and drag
- **Marker Click**: Shows station popup with:
  - Latest reading
  - Temperature
  - Timestamp
  - "View Details" button

**Map Providers:**
- **OpenStreetMap**: Default, open-source
- **GovMap**: Israeli government mapping service

**Toggle:**
- Settings → "Map Provider" → Select option

#### Station Markers

**Color Coding:**
- 🔵 Blue: Normal operation
- 🟡 Yellow: Delayed data (>30 minutes old)
- 🔴 Red: No recent data (>1 hour old)
- ⚫ Gray: Station offline

**Size:**
- Larger markers = more recent data
- Smaller markers = older data

**[Screenshot Placeholder: Interactive Map View]**
*Description: Map of Israeli coastline with 6 station markers. Acre, Haifa, and Yafo (north to south along Mediterranean) shown with blue markers. Ashdod and Ashkelon (central/southern Mediterranean) with blue markers. Eilat (southern tip, Red Sea) with blue marker. Popup open over Acre showing: "Acre | 1.234m | 18.5°C | Updated: 10:30 | View Details button".*

### Weather Integration

#### IMS Warnings

Displays active weather warnings from Israel Meteorological Service.

**Warning Types:**
- Storm warnings
- High wind alerts
- Flood warnings
- Sea condition warnings

**Severity Levels:**
- 🟢 Green: Normal conditions
- 🟡 Yellow: Watch/Advisory
- 🟠 Orange: Warning
- 🔴 Red: Severe Warning

**Display:**
- Warnings appear in dedicated card
- Click for detailed information
- Auto-refresh every 15 minutes

#### Mariners Forecast

Sea conditions forecast for Mediterranean regions.

**Information Provided:**
- Wave height (meters)
- Wave direction
- Wind speed and direction
- Sea state description
- Forecast period (12/24 hours)

**Regions:**
- Northern Coast (Rosh Hanikra to Haifa)
- Central Coast (Haifa to Ashkelon)
- Southern Coast (Ashkelon to Rafah)

**Access:**
- Click "Forecast" tab
- Select "Mariners Forecast"
- Choose region from dropdown

---

## Troubleshooting

### Connection Issues

**Symptom:** Red status dot, "Connection Failed" message

**Solutions:**

1. **Check Internet Connection**
   - Verify you're connected to internet
   - Try opening another website
   - Restart router if needed

2. **Check Backend Server**
   - Is the API server running?
   - Check: `http://localhost:30886/api/health`
   - Should return: `{"status": "healthy"}`

3. **Check CORS Settings**
   - Browser console (F12) for CORS errors
   - Verify backend CORS_ORIGINS includes your domain

4. **Clear Browser Cache**
   - Press Ctrl+Shift+Delete
   - Clear cached images and files
   - Reload page

5. **Try Different Browser**
   - Test in Chrome, Firefox, or Edge
   - Rules out browser-specific issues

### Data Not Loading

**Symptom:** Spinning loader never completes, empty charts

**Solutions:**

1. **Check Date Range**
   - Ensure date range is valid
   - Maximum range is 365 days
   - Start date must be before end date

2. **Verify Station Has Data**
   - Try different station
   - Some stations may have gaps in data

3. **Check Database Connection**
   - Backend logs for database errors
   - Verify PostgreSQL is running

4. **Reduce Data Volume**
   - Shorten date range
   - Select single station instead of "All Stations"

### Chart Not Rendering

**Symptom:** Blank chart area, no graph visible

**Solutions:**

1. **Check JavaScript Errors**
   - Open browser console (F12)
   - Look for red error messages
   - Screenshot and report if found

2. **Disable Browser Extensions**
   - Ad blockers may interfere
   - Temporarily disable extensions
   - Reload page

3. **Update Browser**
   - Ensure browser is up-to-date
   - Minimum versions:
     - Chrome 90+
     - Firefox 88+
     - Safari 14+

4. **Try Different Chart Library**
   - Settings → "Chart Library"
   - Toggle between Chart.js and Plotly

### Predictions Failing

**Symptom:** "Prediction failed" error message

**Solutions:**

1. **Check Sufficient Data**
   - Kalman Filter needs minimum 24 hours of data
   - Prophet needs minimum 7 days
   - Increase date range if needed

2. **Verify Model Availability**
   - Check backend logs for model errors
   - Prophet requires additional dependencies

3. **Reduce Forecast Horizon**
   - Try shorter forecast (24h instead of 168h)
   - Longer forecasts are more computationally intensive

4. **Wait and Retry**
   - Server may be processing other requests
   - Wait 30 seconds and try again

### Anomaly Detection Not Working

**Symptom:** No anomalies detected when expected

**Solutions:**

1. **Check Baseline Requirements**
   - Anomaly detection requires all stations' data
   - Ensure "All Stations" is selected

2. **Verify Date Range**
   - Minimum 7 days recommended
   - More data = better baseline accuracy

3. **Adjust Sensitivity**
   - Settings → "Anomaly Sensitivity"
   - Options: Low, Medium, High
   - Higher sensitivity = more anomalies detected

4. **Check Backend Availability**
   - Anomaly API may be disabled
   - Check `/api/health` for feature flags

### Export Failing

**Symptom:** Download doesn't start, error message

**Solutions:**

1. **Check Browser Popup Blocker**
   - Allow popups for dashboard domain
   - Export may open in new window/tab

2. **Verify Data Selected**
   - Must have at least one station and date range
   - Check that data loaded successfully

3. **Reduce Export Size**
   - Limit to 10,000 records maximum
   - Split large exports into multiple files

4. **Try Different Format**
   - Excel failing? Try CSV
   - Simpler formats less prone to errors

### Performance Issues

**Symptom:** Slow loading, laggy interactions

**Solutions:**

1. **Reduce Data Volume**
   - Shorter date ranges load faster
   - Fewer stations = better performance

2. **Close Unused Tabs**
   - Each tab consumes memory
   - Dashboard works best in dedicated tab

3. **Clear Cache**
   - Ctrl+Shift+Delete → Clear cache
   - Forces fresh data load

4. **Check System Resources**
   - Task Manager (Ctrl+Shift+Esc)
   - Close memory-intensive programs

5. **Use Caching**
   - Backend Redis cache improves speed
   - Check with administrator

---

## FAQ

### General Questions

**Q: Do I need to create an account?**
A: No. The dashboard is publicly accessible without authentication. However, favorites and preferences are stored locally in your browser.

**Q: How often is data updated?**
A: Sea level measurements are updated every 6 minutes. The dashboard automatically refreshes data every 5 minutes when viewing real-time data.

**Q: Can I access historical data?**
A: Yes. Historical data is available dating back to [start date]. Maximum query range is 365 days.

**Q: Is there a mobile app?**
A: Not currently. The dashboard is fully responsive and works well on mobile browsers.

**Q: Can I share my view with others?**
A: Yes. Copy the URL from your browser - it includes station, date range, and view settings. Share the URL to recreate your exact view.

### Data Questions

**Q: What do the sea level values represent?**
A: Values are in meters relative to the Israeli Leveling Datum (ILD). Positive values are above datum, negative below.

**Q: Why are some values missing?**
A: Gaps can occur due to:
- Station maintenance
- Equipment malfunction
- Data transmission issues
- Quality control filtering

**Q: How accurate are the measurements?**
A: Measurements are accurate to ±1 cm under normal conditions. Temperature affects accuracy; quality indicators show reliability.

**Q: What causes anomalies?**
A: Anomalies can result from:
- Equipment malfunctions (most common)
- Extreme weather events
- Tsunamis or storm surges
- Data transmission errors
- Calibration issues

### Prediction Questions

**Q: How accurate are predictions?**
A: Typical accuracy:
- 24 hours: ±3-5 cm (Kalman Filter)
- 48 hours: ±5-8 cm (Kalman Filter)
- 7 days: ±10-15 cm (Prophet)

**Q: What factors affect accuracy?**
A:
- Weather events (storms reduce accuracy)
- Data quality (gaps reduce accuracy)
- Forecast horizon (longer = less accurate)
- Model selection (wrong model for use case)

**Q: Why do models disagree?**
A: Different models use different algorithms:
- Kalman assumes linear dynamics (short-term)
- Prophet captures seasonal patterns (long-term)
- Disagreement often indicates uncertainty

**Q: Can I trust predictions for navigation?**
A: Predictions are for informational purposes only. Always consult official tide tables and forecasts for navigation.

### Technical Questions

**Q: What browsers are supported?**
A: Modern browsers with JavaScript:
- Chrome 90+ (recommended)
- Firefox 88+
- Safari 14+
- Edge 90+

**Q: Can I use this on my phone?**
A: Yes. The dashboard is responsive and optimized for mobile devices (iOS 13+, Android 8+).

**Q: Why is my browser cache important?**
A: Cache stores data locally for faster loading. Clear cache if you see outdated data or errors.

**Q: Can I integrate this data into my application?**
A: Yes. See API_DOCUMENTATION.md for REST API endpoints. Data available in JSON format.

**Q: Is there a rate limit?**
A: No explicit rate limit for web interface. API access may have limits - check with administrator.

---

## Glossary

### Terms and Definitions

**Anomaly**: A measurement that significantly deviates from expected values based on statistical analysis of historical patterns.

**Baseline**: The expected value for a measurement at a given time, calculated from historical data and accounting for tidal patterns.

**Chart.js**: Open-source JavaScript library used for creating interactive charts and graphs.

**Confidence Interval**: Range within which the true value is expected to fall with specified probability (e.g., 95% confidence interval).

**CORS (Cross-Origin Resource Sharing)**: Security mechanism that controls which domains can access API resources.

**Delta**: Change in value between two measurements, typically shown with +/- sign.

**Forecast Horizon**: Length of time into the future that a prediction covers (e.g., 24-hour forecast horizon).

**IMS (Israel Meteorological Service)**: National meteorological service providing weather forecasts and warnings.

**ISO 8601**: International standard for date and time format (YYYY-MM-DDTHH:MM:SS).

**Kalman Filter**: Mathematical algorithm for making predictions from noisy data, excellent for short-term forecasting.

**Mariners Forecast**: Weather and sea condition forecast specifically for maritime navigation.

**MAPE (Mean Absolute Percentage Error)**: Metric for measuring prediction accuracy; lower is better.

**Outlier**: Data point that lies outside the normal range, potentially indicating error or unusual event.

**Prophet**: Facebook's open-source forecasting tool, good for data with strong seasonal patterns.

**Real-time Data**: Most recent measurements, typically updated every 6 minutes.

**Rolling Average**: Moving average calculated over a sliding time window (e.g., 24-hour rolling average).

**Station**: Geographic location where sea level is measured and monitored.

**Tidal Pattern**: Regular rise and fall of sea level due to gravitational forces from moon and sun.

**Trendline**: Statistical line fitted to data to show underlying trend, removing short-term variations.

**Validation Rule**: Criterion used by anomaly detection algorithm to identify suspicious data points.

### Units of Measurement

- **Meters (m)**: Sea level height
- **Celsius (°C)**: Water temperature
- **Hours (h)**: Time duration
- **Minutes (min)**: Time duration
- **Percentage (%)**: Relative change or proportion

### Acronyms

- **API**: Application Programming Interface
- **CSV**: Comma-Separated Values
- **HTTP**: Hypertext Transfer Protocol
- **ILD**: Israeli Leveling Datum
- **JSON**: JavaScript Object Notation
- **REST**: Representational State Transfer
- **SQL**: Structured Query Language
- **UTC**: Coordinated Universal Time
- **URL**: Uniform Resource Locator
- **XML**: Extensible Markup Language

---

## Support and Additional Resources

### Getting Help

**Technical Support:**
- Email: support@example.com
- Phone: +972-XX-XXXXXX
- Hours: Sunday-Thursday, 9:00-17:00 Israel Time

**Documentation:**
- API Documentation: See API_DOCUMENTATION.md
- Developer Guide: See README.md
- Code Examples: See JSDOC_EXAMPLES.md and PYTHON_DOCSTRINGS_EXAMPLES.md

**Community:**
- GitHub Issues: [repository-url]/issues
- Discussion Forum: [forum-url]

### Training Resources

**Video Tutorials:**
1. Getting Started (5 minutes)
2. Data Visualization (10 minutes)
3. Anomaly Detection (8 minutes)
4. Generating Predictions (12 minutes)
5. Advanced Analysis (15 minutes)

**Webinars:**
- Monthly Q&A sessions
- Quarterly feature updates
- Annual training workshops

### Feedback

We welcome your feedback to improve the dashboard:
- Feature requests: [feedback-url]
- Bug reports: [github-issues-url]
- User survey: [survey-url]

---

**End of User Manual**

*Document Version: 2.0.0*
*Last Updated: November 2025*
*For technical documentation, see API_DOCUMENTATION.md*
