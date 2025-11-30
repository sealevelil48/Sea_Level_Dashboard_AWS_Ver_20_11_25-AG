# GovMap Component Testing Guide

Quick reference for testing the new GovMapViewer component.

---

## ⚡ Quick Start (2 minutes)

```bash
# Terminal 1 - Backend
cd backend
python local_server.py

# Terminal 2 - Frontend
cd frontend
npm start
```

**Open:** http://localhost:30887

**Expected:** Map loads in 1-2 seconds with 8 station markers

---

## ✅ Visual Checklist

### Desktop (5 minutes)

```
Map View:
□ Map loads successfully (no errors)
□ 8 station markers visible (blue pins)
□ 1 Sea of Galilee marker visible

Marker Interaction:
□ Click Acre marker → popup appears
□ Popup shows: Station name, sea level, temp, update time
□ Popup shows: Wave forecast data (if available)
□ Wave height shows text like "Smooth to slight (30-60 cm)"
□ Wind shows text like "NW-NE (15-25 km/h)"

Navigation:
□ Date picker works → markers update
□ Switch to OSM tab → map changes
□ Switch back to GovMap → markers reappear
□ Fullscreen button → map expands
□ Exit fullscreen → map returns to normal

Console Check:
□ Open DevTools (F12) → Console tab
□ Should see: "✅ GovMap loaded and ready"
□ Should see: "✅ Displayed 8 markers successfully"
□ No red errors (GovMap 401 warnings are OK)
```

### Mobile Portrait (3 minutes)

```
Setup:
□ Chrome DevTools → Device Toolbar (Ctrl+Shift+M)
□ Select "iPhone 12 Pro" or similar
□ Set to Portrait orientation

Map View:
□ Map fills screen
□ Markers visible and tap-able

Popup Positioning:
□ Tap any marker
□ Popup appears on RIGHT SIDE of screen
□ Popup positioned at 50% vertical (middle height)
□ Popup doesn't block entire map
□ Popup is scrollable if content is long

Interaction:
□ Can still pan map with popup open
□ Tap outside popup → popup closes
□ Tap different marker → popup moves to new location
```

### Mobile Landscape (2 minutes)

```
Setup:
□ Rotate device to Landscape

Map View:
□ Map adjusts to landscape layout
□ Markers still visible

Popup Positioning:
□ Tap any marker
□ Popup appears NEAR the marker (not forced to right)
□ Popup has reasonable size (not too big)
□ Popup doesn't overflow screen
```

### Orientation Changes (2 minutes)

```
□ Start in Portrait → tap marker → popup appears RIGHT
□ Rotate to Landscape → popup repositions NEAR marker
□ Rotate back to Portrait → popup repositions RIGHT
□ All transitions smooth (no jumping)
```

---

## 🔍 Detailed Testing (15 minutes)

### Test Each Station

Click each marker and verify popup content:

```
Acre:
□ Sea level value present (e.g., "0.331 m")
□ Temperature present (e.g., "22°C")
□ Last update date present
□ Forecast data: "Northern Coast"
□ Wave height translated
□ Wind direction translated
□ Survey of Israel copyright link
□ IMS Forecast copyright link

Yafo:
□ Similar to above
□ Forecast data: "Central Coast"

Ashkelon:
□ Similar to above
□ Forecast data: "Southern Coast"

Eilat:
□ Similar to above
□ Forecast data: "Gulf of Eilat"

Other Stations (Haifa, Ashdod, Hadera, Tel Aviv):
□ Station data present
□ May or may not have forecast data (this is correct)

Sea of Galilee:
□ Forecast data only (no station data)
□ Wave height, temp, wind present
□ Positioned correctly on map
```

### Test Date Changes

```
□ Open date picker
□ Select yesterday's date
□ Markers update (may show different values)
□ Console shows: "Displayed X markers successfully"
□ No errors in console
```

### Test API Failures

```
Scenario 1: Backend Down
□ Stop backend server (Ctrl+C in terminal)
□ Refresh frontend
□ Should see: Error screen with "GovMap Unavailable"
□ Click "Retry" button → tries to reconnect
□ Restart backend → click Retry → map loads

Scenario 2: Bad Date
□ In browser console: set invalid date
□ Should handle gracefully (no crash)
□ Error message or empty state displayed
```

### Test Performance

```
Cold Load (No Cache):
□ Clear browser cache (Ctrl+Shift+Del)
□ Reload page
□ Time from page load to markers visible
□ Expected: 1-2 seconds

Warm Load (With Cache):
□ Reload page (Ctrl+R)
□ Time from page load to markers visible
□ Expected: 300-500ms (much faster!)

Date Change (Cached):
□ Change date picker to today (if not already)
□ Time from date change to markers update
□ Expected: < 200ms (instant!)

Tab Switching:
□ Switch to OSM tab
□ Switch back to GovMap
□ Time to display markers
□ Expected: Instant (< 100ms)
```

---

## 🐛 Known Issues & Expected Behavior

### Expected (Not Bugs)

```
✅ GovMap 401 Authentication Errors in Console
   - These are SUPPRESSED and EXPECTED
   - GovMap tries to authenticate but it's not critical
   - Does not affect functionality

✅ Console.log Statements in Build
   - ESLint warnings about console.log
   - Not functional issues
   - Can be removed later for production

✅ Some Stations Missing Forecast Data
   - Only 4 stations have forecast mappings
   - This is correct behavior based on IMS data
   - Other stations show only station data
```

### Not Expected (Potential Bugs)

```
❌ Map completely blank (not just loading)
   - Check backend is running
   - Check console for actual errors

❌ Markers appear but no data in popups
   - Check API response format
   - Verify backend endpoints return data

❌ Popups in wrong position (mobile)
   - Check device orientation detection
   - Try refreshing page
   - Check if CSS media queries loaded

❌ Build fails with errors
   - Check all files created correctly
   - Verify React Query installed
   - Try npm install again
```

---

## 📊 Performance Benchmarks

### Target Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Initial load | < 2s | DevTools Network tab, DOMContentLoaded |
| Cached load | < 500ms | Reload page, time to markers |
| Date change | < 200ms | Change date, time to markers |
| Tab switch | < 100ms | Switch tabs, time to display |
| Memory usage | < 50MB | DevTools Memory profiler |

### How to Measure

**Chrome DevTools:**

1. **Network Performance**
   - Open DevTools (F12)
   - Network tab
   - Reload page (Ctrl+R)
   - Check "DOMContentLoaded" time (blue line)

2. **JavaScript Performance**
   - Performance tab
   - Click Record
   - Interact with map (click markers, change date)
   - Click Stop
   - Check for:
     - Long tasks (> 50ms)
     - Layout shifts
     - Excessive re-renders

3. **Memory Usage**
   - Memory tab
   - Take heap snapshot
   - Interact with map
   - Take another snapshot
   - Compare → should not grow excessively

---

## 🔧 Debug Commands

### Browser Console Commands

```javascript
// Check if GovMap loaded
console.log(window.govmap ? '✅ Loaded' : '❌ Not loaded');

// Check map instance
console.log(window.govmapInstanceRef);

// Force mobile portrait positioning
applyMobilePortraitPositioning();

// Check orientation
console.log('Portrait:', isMobilePortrait());
console.log('Landscape:', isMobileLandscape());

// Check React Query cache
// (Open React Query DevTools if installed)
```

### Network Tab Checks

Expected requests:
```
✅ GET /stations/map?end_date=2025-11-27  → 200 OK
✅ GET /sea-forecast                      → 200 OK
✅ GET govmap.api.js                      → 200 OK
```

If you see:
```
❌ 404 or 500 → Check backend running
❌ CORS error → Check backend CORS settings
❌ Timeout → Check network connection
```

---

## 📱 Mobile Device Testing (Real Device)

### iOS (iPhone/iPad)

1. **Connect to same network** as development machine
2. **Find your computer's IP** (ipconfig/ifconfig)
3. **Open Safari** on device
4. **Navigate to:** http://YOUR_IP:30887
5. **Test all mobile scenarios** from checklist above

### Android

1. **Connect to same network**
2. **Find your computer's IP**
3. **Open Chrome** on device
4. **Navigate to:** http://YOUR_IP:30887
5. **Test all mobile scenarios**

### Common Issues

```
Can't connect from mobile device:
□ Check both on same WiFi
□ Check firewall not blocking port 30887
□ Try: http://192.168.1.XXX:30887 (your actual IP)

Mobile positioning not working:
□ Test actual device, not just emulator
□ Check if orientation events firing
□ Try rotating device several times
□ Check browser console for errors
```

---

## ✅ Test Report Template

Copy and fill out after testing:

```
GovMap Component Test Report
Date: ___________
Tester: ___________
Environment: [ ] Dev [ ] Staging [ ] Production

DESKTOP TESTS
✅ ❌ Map loads successfully
✅ ❌ All markers appear (8 + 1)
✅ ❌ Popups display correctly
✅ ❌ Forecast data integrated
✅ ❌ IMS translations working
✅ ❌ Date picker updates map
✅ ❌ Tab switching works
✅ ❌ Fullscreen mode works

MOBILE PORTRAIT TESTS
✅ ❌ Map loads on mobile
✅ ❌ Popups appear on right side
✅ ❌ Popups scrollable
✅ ❌ Can interact with map

MOBILE LANDSCAPE TESTS
✅ ❌ Map adjusts to landscape
✅ ❌ Popups positioned correctly
✅ ❌ All interactions work

PERFORMANCE TESTS
Initial load: _____ seconds (target: < 2s)
Cached load: _____ ms (target: < 500ms)
Date change: _____ ms (target: < 200ms)

ISSUES FOUND:
1. ________________________________
2. ________________________________
3. ________________________________

OVERALL STATUS:
[ ] PASS - Ready for production
[ ] PASS WITH ISSUES - Deploy with known issues
[ ] FAIL - Needs fixes before deploy

NOTES:
_________________________________
_________________________________
_________________________________
```

---

## 🚀 Production Readiness Checklist

Before going live:

```
Code Quality:
□ All tests passed (above checklist)
□ No console errors (except expected GovMap warnings)
□ Build succeeds without errors
□ Code reviewed (if team environment)

Performance:
□ Initial load < 2 seconds
□ No memory leaks detected
□ Responsive on all tested devices

Testing Coverage:
□ Desktop tested (Chrome, Firefox, Edge)
□ Mobile portrait tested (iOS + Android)
□ Mobile landscape tested (iOS + Android)
□ Tablet tested (optional but recommended)

Documentation:
□ GOVMAP_MIGRATION_COMPLETE.md reviewed
□ Known issues documented
□ Support team informed

Deployment:
□ Build artifacts generated (npm run build)
□ Environment variables set correctly
□ Backend endpoints verified
□ Monitoring/analytics configured (optional)

Rollback Plan:
□ Old iframe code backed up
□ Can revert to previous version if needed
□ Database/API changes (none in this case)
```

---

## 📞 Support Contacts

| Issue Type | Contact | Reference |
|------------|---------|-----------|
| Component bugs | Development team | GovMapViewer.jsx |
| API issues | Backend team | /stations/map endpoint |
| GovMap API | GovMap support | govmap.gov.il |
| IMS data | IMS support | ims.gov.il |

---

## 📚 Additional Resources

- **Full documentation:** GOVMAP_MIGRATION_COMPLETE.md
- **Component source:** frontend/src/components/GovMap/GovMapViewer.jsx
- **Helper functions:** frontend/src/utils/govmapHelpers.js
- **React Query docs:** tanstack.com/query/latest
- **GovMap API docs:** govmap.gov.il/api/docs

---

**Testing Time:** 15-30 minutes (basic to thorough)
**Last Updated:** 2025-11-27
**Status:** Ready for testing ✅
