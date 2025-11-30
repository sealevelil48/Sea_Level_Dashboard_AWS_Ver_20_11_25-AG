# Debugging Guide - GovMap Issues

## Changes Applied

### 1. Exit Fullscreen Button Debugging
**Problem**: Button not appearing on desktop
**Fix Applied**:
- Changed from conditional rendering `{!isMobile && <Button />}` to always render
- Button now uses CSS `display: none` when on mobile
- Added console.log to track `isMobile` value

**To Debug**:
1. Open browser console (F12)
2. Enter fullscreen mode
3. Look for: `🖥️  DashboardMap - Fullscreen mode, isMobile: false`
4. Check if button is in DOM but hidden (inspect element)
5. If `isMobile: true` on desktop → problem is with window width detection
6. If `isMobile: false` but button not visible → CSS issue

### 2. Marker Loading Delay
**Problem**: Markers take extra seconds after map loads
**Fix Applied**:
- Removed dependency on `isMapLoaded` event
- Now checks for `govmapInstanceRef.current` existence
- Added 500ms delay to ensure map is rendered
- Changed from waiting for onLoad event to checking map instance

**Expected Console Output**:
```
⏳ Waiting for map and markers... {mapInstance: false, markers: 0}
🗺️  Initializing GovMap with config: {...}
✅ GovMap loaded and ready for marker display
⏳ Waiting for map and markers... {mapInstance: true, markers: 8}
🎯 Triggering marker display - all requirements met
📍 Displaying 8 markers on GovMap...
✅ Displayed 8 markers in XX ms
```

### 3. Mobile Portrait - Container Sizing
**Problem**: Map doesn't fill container in normal (non-fullscreen) view
**Fix Applied**:
- Added specific CSS for non-fullscreen mode
- Used `:not(.govmap-fullscreen)` selectors
- Added `!important` flags to override GovMap's default styles
- Set `width: 100%`, `height: 100%`, `min-height: 400px`

**CSS Applied** (lines 337-363 in GovMapViewer.css):
```css
@media screen and (max-width: 768px) and (orientation: portrait) {
  .govmap-wrapper:not(.govmap-fullscreen) {
    position: relative !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 400px !important;
  }
  /* ... more rules */
}
```

### 4. Mobile Portrait Fullscreen Centering
**Problem**: Map not centered, cut off on iPhone 16
**Existing Fix**: Already using `position: absolute` to fill parent
**Parent Container**: DashboardMap uses `position: fixed` with z-index 9999

**To Debug**:
1. Open Chrome DevTools
2. Toggle device toolbar (Ctrl+Shift+M)
3. Select "iPhone 12 Pro" or "iPhone 13 Pro"
4. Set orientation to Portrait
5. Enter fullscreen
6. Inspect the fullscreen container styles
7. Check computed styles for `.govmap-fullscreen`

---

## Testing Instructions

### Step 1: Restart Servers
```bash
# Terminal 1 - Backend
cd backend
python local_server.py

# Terminal 2 - Frontend
cd frontend
npm start
```

### Step 2: Desktop Testing

1. **Open browser console** (F12 → Console tab)
2. **Navigate to dashboard**: http://localhost:30887
3. **Watch console output** for loading sequence
4. **Time the marker display**: Should be 2-3 seconds total
5. **Enter fullscreen**: Click fullscreen button
6. **Check console**: Look for `🖥️  DashboardMap - Fullscreen mode, isMobile: false`
7. **Verify exit button**: Should be visible at top-right
8. **If button not visible**:
   - Inspect element (right-click → Inspect)
   - Search for "Exit Full Screen" in HTML
   - Check computed styles for `display` property
   - Check if `isMobile` value in console log

### Step 3: Mobile Portrait Testing (Chrome DevTools)

1. **Open DevTools**: F12
2. **Toggle device toolbar**: Ctrl+Shift+M
3. **Select device**: iPhone 12 Pro or iPhone 13 Pro
4. **Set orientation**: Portrait (vertical icon)
5. **Normal view test**:
   - Map should fill entire card height
   - No white space at top/bottom
   - Map fully visible, not cut off
6. **Fullscreen test**:
   - Click fullscreen button at bottom
   - Map should fill entire viewport
   - Map centered, not offset
   - No cutoff on right or bottom
   - Exit button visible at bottom center
7. **Check console**: Look for container dimensions
8. **Inspect styles**:
   - Check `.govmap-fullscreen` computed styles
   - Verify `position: absolute`
   - Verify `width: 100%`, `height: 100%`

### Step 4: Console Debugging

**Key Console Messages to Look For**:

✅ **Success Pattern**:
```
✅ GovMap API loaded successfully
🗺️  Initializing GovMap with config: {...}
✅ GovMap loaded and ready for marker display
Processing markers: {stations: 8, forecasts: 4}
🎯 Triggering marker display - all requirements met
📍 Displaying 8 markers on GovMap...
✅ Displayed 8 markers in 50 ms
📐 Fullscreen state changed: true
🖥️  DashboardMap - Fullscreen mode, isMobile: false
   Container dimensions: 1920 x 1080
   Markers to persist: 8
   🔄 Re-displaying markers after fullscreen toggle...
✅ Displayed 8 markers in 45 ms
```

❌ **Problem Patterns**:
```
# If isMobile is true on desktop:
🖥️  DashboardMap - Fullscreen mode, isMobile: true  ← WRONG!

# If markers take too long:
⏳ Waiting for map and markers... (appears for > 3 seconds)

# If map doesn't initialize:
❌ Failed to load GovMap API
```

---

## Diagnostic Questions

### If Exit Button Not Visible:

1. **What does console show for `isMobile`?**
   - `isMobile: false` → Button should be visible
   - `isMobile: true` → Wrong detection, check window.innerWidth

2. **Is button in DOM?**
   - Open DevTools → Elements tab
   - Search (Ctrl+F) for "Exit Full Screen"
   - If found → CSS hiding issue
   - If not found → Rendering issue

3. **What's the computed style?**
   - Find button element
   - Check Styles panel → Computed
   - Look for `display: none` or `display: block`

### If Markers Load Slowly:

1. **What's the timing?**
   - Note time from page load to "✅ Displayed 8 markers"
   - Should be < 3 seconds

2. **Check console sequence:**
   - Is "🗺️  Initializing GovMap" appearing quickly?
   - Is "🎯 Triggering marker display" delayed?
   - Any errors between initialization and display?

3. **Network tab check:**
   - Open DevTools → Network tab
   - Check `/stations/map` request time
   - Check `/sea-forecast` request time
   - Both should be < 500ms

### If Mobile Container Not Full:

1. **Inspect the container:**
   - Right-click on map → Inspect
   - Find `.govmap-wrapper` element
   - Check computed height value
   - Should be matching parent card height

2. **Check parent height:**
   - Inspect parent Card.Body element
   - Check if it has explicit height
   - Check if flex layout is working

3. **CSS cascade check:**
   - Look for red strikethrough styles
   - Check if `!important` is being overridden
   - Verify media query is active

### If Mobile Fullscreen Not Centered:

1. **Check fullscreen container:**
   - Inspect `.govmap-fullscreen` element
   - Verify `position: absolute`
   - Check `top: 0`, `left: 0`, `right: 0`, `bottom: 0`
   - Check `width: 100%`, `height: 100%`

2. **Check parent positioning:**
   - Find parent div with `position: fixed`
   - Should have `z-index: 9999`
   - Should have `width: 100vw`, `height: 100vh`

3. **Check for transform issues:**
   - Look for unexpected `transform` properties
   - Check for `translate` or `scale` values

---

## Expected Timing Benchmarks

| Event | Target Time | Acceptable Range |
|-------|-------------|------------------|
| Page load to GovMap loaded | 1-2s | < 3s |
| GovMap loaded to markers displayed | 0.5-1s | < 2s |
| Total (page to markers) | 2-3s | < 4s |
| Fullscreen toggle | Instant | < 100ms |
| Marker persistence after fullscreen | 100-200ms | < 500ms |

---

## Files Modified

1. **frontend/src/components/Dashboard/DashboardMap.js**
   - Line 102: Added console.log for isMobile debugging
   - Line 127-140: Changed button rendering logic
   - Line 136: Added `display: isMobile ? 'none' : 'block'`

2. **frontend/src/components/GovMap/GovMapViewer.jsx**
   - Line 308-324: Simplified marker display logic
   - Line 318: Changed to 500ms delay instead of waiting for onLoad
   - Line 375-379: Updated mobile positioning dependency

3. **frontend/src/components/GovMap/GovMapViewer.css**
   - Lines 337-363: Enhanced mobile portrait normal view styles
   - Added `:not(.govmap-fullscreen)` selectors
   - Added `!important` flags for specificity

---

## Next Steps

1. **Start servers** and open browser console
2. **Test desktop** - verify console logs and button visibility
3. **Test mobile** - use Chrome DevTools device toolbar
4. **Report findings**:
   - What console logs appear?
   - What is the `isMobile` value on desktop?
   - Is the exit button in DOM but hidden?
   - How long do markers take to load?
   - Does mobile container fill properly?
   - Is mobile fullscreen centered?

---

**Status**: Debugging build deployed
**Date**: 2025-11-27
**Build**: frontend/build (with console logs)

Please test and share the console output so we can pinpoint the exact issues!
