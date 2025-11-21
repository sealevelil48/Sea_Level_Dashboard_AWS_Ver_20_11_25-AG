# Delta Display Component - Visual Reference Guide

## Display Modes Overview

The DeltaDisplay component supports three distinct display modes, each optimized for different use cases and screen sizes.

---

## Mode 1: Overlay (Default)

**Use Case:** Non-intrusive comparison display that floats over the main content

**Position:** Fixed on the right side of the screen (mobile: bottom of screen)

**Characteristics:**
- Fixed positioning
- Does not affect page layout
- Easy to dismiss
- Visible while scrolling
- Optimal for desktop users

**Layout Structure:**
```
┌────────────────────────────────────┐
│ Δ Station Comparison          [X]  │
├────────────────────────────────────┤
│                                    │
│  Station 1        Δ 0.056m        │
│  ┌──────────┐    ↑         Station 2  │
│  │  Haifa   │   meters     ┌──────────┐
│  │ 0.256 m  │              │  Acre    │
│  │ Nov 20   │              │ 0.312 m  │
│  └──────────┘              │ Nov 20   │
│                            └──────────┘
│                                    │
├────────────────────────────────────┤
│     [ Clear Selection ]            │
└────────────────────────────────────┘
```

**CSS Class:** `.delta-overlay`

**Responsive Behavior:**
- Desktop: Right side, centered vertically
- Tablet: Right side, smaller width
- Mobile: Bottom of screen, full width

---

## Mode 2: Panel

**Use Case:** Inline comparison display within the page content

**Position:** Inline block, follows document flow

**Characteristics:**
- Occupies full container width
- Pushes content down
- More detailed information display
- Best for dedicated comparison section
- Optimal for tablet and desktop

**Layout Structure:**
```
┌─────────────────────────────────────────────────────────────┐
│                    Station Comparison                   [Clear Selection] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐      ↑        ┌──────────────────┐  │
│  │  Station 1       │     Δ         │  Station 2       │  │
│  │  Haifa           │      │        │  Acre            │  │
│  ├──────────────────┤      │        ├──────────────────┤  │
│  │ Sea Level:       │      │        │ Sea Level:       │  │
│  │      0.256 m     │      │        │      0.312 m     │  │
│  │                  │      │        │                  │  │
│  │ Timestamp:       │      │        │ Timestamp:       │  │
│  │ Nov 20, 2:30 PM  │      │        │ Nov 20, 2:30 PM  │  │
│  └──────────────────┘      │        └──────────────────┘  │
│                            │                              │
├────────────────────────────┴──────────────────────────────┤
│                                                             │
│            Calculated Delta: +0.056 m                       │
│              Station 2 is higher                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**CSS Class:** `.delta-panel`

**Responsive Behavior:**
- Desktop: 3-column grid (station | delta | station)
- Tablet/Mobile: Single column, stacked vertically

---

## Mode 3: Tooltip

**Use Case:** Compact, minimal comparison display

**Position:** Floating near cursor or at fixed location

**Characteristics:**
- Smallest footprint
- Minimal information
- Quick comparison glance
- Best for mobile devices
- Can be positioned near clicked element

**Layout Structure:**
```
┌──────────────────────────────┐
│ Station Comparison      [X]  │
├──────────────────────────────┤
│                              │
│ Haifa      ↑     Acre        │
│ 0.256 m          0.312 m     │
│                              │
│         Δ 0.056 m            │
└──────────────────────────────┘
```

**CSS Class:** `.delta-tooltip`

**Responsive Behavior:**
- Desktop: Near cursor/element
- Mobile: Bottom center, full width minus margins

---

## Color Coding System

### Positive Delta (Station 2 > Station 1)
- **Arrow:** ↑
- **Color:** Green (#34d399)
- **Message:** "Station 2 is higher"
- **Border:** Solid green

### Negative Delta (Station 1 > Station 2)
- **Arrow:** ↓
- **Color:** Red (#f87171)
- **Message:** "Station 1 is higher"
- **Border:** Solid red

### Neutral Delta (Equal Levels)
- **Arrow:** →
- **Color:** Blue (#a0c8f0)
- **Message:** "Levels are equal"
- **Border:** Solid blue

---

## Theme Integration

### Dark Theme Colors
- **Background:** #142950 (Dark blue)
- **Card Background:** #1e3c72 (Medium blue)
- **Border:** #2a4a8c (Blue gray)
- **Primary Accent:** #3b82f6 (Bright blue)
- **Text Primary:** white
- **Text Secondary:** #a0c8f0 (Light blue)
- **Text Muted:** #8ba8c8 (Lighter blue)

### Typography
- **Font Family:** 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif
- **Title Size:** 1rem (desktop), 0.9rem (mobile)
- **Value Size:** 1.4rem - 2rem (desktop), 1.1rem - 1.4rem (mobile)
- **Label Size:** 0.7rem - 0.9rem

---

## Responsive Breakpoints

### Desktop (> 992px)
- Full-featured overlay display
- 3-column panel layout
- Large text sizes
- Spacious padding

### Tablet (768px - 992px)
- Adjusted overlay size
- 2-column or stacked panel
- Medium text sizes
- Moderate padding

### Mobile (< 768px)
- Overlay moves to bottom
- Single column panel
- Smaller text sizes
- Compact padding
- Touch-friendly buttons

### Small Mobile (< 576px)
- Full-width displays
- Minimal padding
- Smallest text sizes
- Essential information only

---

## Animation Effects

### Slide In (Overlay)
```css
@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translate(20px, -50%);
  }
  to {
    opacity: 1;
    transform: translate(0, -50%);
  }
}
```
- Duration: 0.3s
- Easing: ease-out

### Fade In Up (Panel)
```css
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```
- Duration: 0.3s
- Easing: ease-out

### Fade In (Tooltip)
```css
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
```
- Duration: 0.2s
- Easing: ease-out

---

## Interaction States

### Default State
- Normal colors
- Standard opacity
- No hover effects

### Hover State (Clear Button)
- Increased opacity: 0.8 → 1.0
- Scale transform: 1.0 → 1.1
- Color change: #a0c8f0 → white
- Transition: 0.2s

### Active State (Clear Button)
- Button press effect
- Slight scale down
- Immediate visual feedback

---

## Screen Size Examples

### Desktop View (1920x1080)
```
┌────────────────────────────────────────────────────────────┐
│                     Dashboard Header                       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  [Graph Content]                   ┌─────────────────┐    │
│                                    │ Delta Display   │    │
│                                    │   (Overlay)     │    │
│                                    │                 │    │
│                                    │   Haifa  ↑      │    │
│                                    │  0.256m         │    │
│                                    │    Δ 0.056m     │    │
│                                    │   Acre          │    │
│                                    │  0.312m         │    │
│                                    │                 │    │
│                                    │  [Clear]        │    │
│                                    └─────────────────┘    │
└────────────────────────────────────────────────────────────┘
```

### Tablet View (768x1024)
```
┌────────────────────────────┐
│    Dashboard Header        │
├────────────────────────────┤
│                            │
│  [Graph]   ┌─────────────┐ │
│            │   Delta     │ │
│            │ (Overlay)   │ │
│            │             │ │
│            │ Haifa  ↑    │ │
│            │ Acre        │ │
│            │ Δ 0.056m    │ │
│            │             │ │
│            │ [Clear]     │ │
│            └─────────────┘ │
└────────────────────────────┘
```

### Mobile View (375x667)
```
┌─────────────────────┐
│   Dashboard Header  │
├─────────────────────┤
│                     │
│    [Graph]          │
│                     │
│                     │
├─────────────────────┤
│ Δ Station Comp. [X] │
│ Haifa → Acre        │
│ 0.256m   0.312m     │
│ Δ 0.056m            │
│   [Clear]           │
└─────────────────────┘
```

---

## Accessibility Features

### ARIA Labels
- Clear button: `aria-label="Clear selection"`
- Meaningful semantic HTML
- Proper heading hierarchy

### Keyboard Support
- Tab navigation through buttons
- Enter/Space to activate buttons
- Escape key to close (optional enhancement)

### Screen Reader Support
- Descriptive text for all data points
- Logical reading order
- Status announcements for delta changes

### Visual Accessibility
- High contrast ratios (4.5:1 minimum)
- Color is not the only indicator
- Directional arrows supplement color
- Readable font sizes (minimum 14px)

---

## Best Practices

### When to Use Each Mode

**Overlay:**
- Default choice for most scenarios
- When content should remain visible
- For temporary comparisons
- Desktop-first applications

**Panel:**
- Dedicated comparison sections
- When delta is primary focus
- Content can be pushed down
- Mobile-friendly layouts

**Tooltip:**
- Quick glance comparisons
- Limited screen space
- Mobile-first applications
- Supplementary information

### Performance Tips
- Component is memoized (React.memo)
- Avoid unnecessary re-renders
- Use callbacks for event handlers
- Debounce rapid selections

### UX Recommendations
- Provide visual feedback on selection
- Show instructions for first selection
- Allow easy clearing of selection
- Support keyboard shortcuts
- Test on various screen sizes

---

## Component Variants Summary

| Feature          | Overlay        | Panel          | Tooltip        |
|------------------|----------------|----------------|----------------|
| Position         | Fixed          | Inline         | Absolute/Fixed |
| Screen Space     | Minimal        | Full Width     | Minimal        |
| Detail Level     | Medium         | High           | Low            |
| Mobile Friendly  | Good           | Excellent      | Excellent      |
| Desktop Optimal  | Excellent      | Good           | Fair           |
| Animation        | Slide In Right | Fade In Up     | Fade In        |
| Z-Index          | 1500           | Normal Flow    | 2000           |

---

**Version:** 1.0
**Last Updated:** November 2025
**Compatibility:** React 17+, Bootstrap 5+
