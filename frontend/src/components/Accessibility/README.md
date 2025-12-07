# Accessibility Widget Component

## Overview
The AccessibilityWidget provides a floating action button (FAB) and panel interface for users to customize accessibility settings in the Sea Level Dashboard.

## Files
- `AccessibilityWidget.js` - Main React component
- `AccessibilityWidget.css` - Component styling

## Features

### Floating Action Button (FAB)
- **Position**: Fixed bottom-right corner (desktop: 20px, mobile: 15px from edges, 80px from bottom)
- **Size**: 56px desktop, 48px mobile
- **Icon**: Universal access symbol (♿)
- **Functionality**: Toggles accessibility panel
- **Accessibility**: Full ARIA support, keyboard navigation (Enter/Space to toggle)

### Accessibility Panel
- **Layout**: Slides in from right (desktop), bottom (mobile)
- **Size**: 320px width desktop, full-width mobile (70vh max-height)
- **Sections**:
  1. **Contrast Mode**: Radio buttons (Normal / High Contrast)
  2. **Text Size**: Radio buttons (Normal / Large / Extra Large)
  3. **Large Cursor**: Toggle switch
  4. **Highlight Links**: Toggle switch
- **Controls**: Close button (X), Reset to Default button
- **Accessibility**:
  - Role="dialog"
  - Focus trap
  - Escape to close
  - Tab navigation
  - Return focus to FAB on close

## Integration

### Required Hook
The component requires the `useAccessibility` hook from `../../hooks/useAccessibility`:

```javascript
const { settings, updateSetting, resetSettings } = useAccessibility();
```

### Expected Hook API
- `settings`: Object containing current accessibility settings
  - `contrastMode`: 'normal' | 'high'
  - `textSize`: 'normal' | 'large' | 'extraLarge'
  - `largeCursor`: boolean
  - `highlightLinks`: boolean
- `updateSetting(key, value)`: Function to update a setting
- `resetSettings()`: Function to reset all settings to default

### Usage
```javascript
import AccessibilityWidget from './components/Accessibility/AccessibilityWidget';

function App() {
  return (
    <>
      {/* Your app content */}
      <AccessibilityWidget />
    </>
  );
}
```

## Styling

### Theme
- **Background**: Dark blue gradient (#1e3c72, #2a4a8c)
- **Border**: Blue (#3b82f6)
- **Panel**: White background, dark text
- **Shadows**: Elevation effects with blue glow

### Responsive Breakpoints
- **Desktop**: Default styles
- **Mobile**: ≤768px (full-width panel, adjusted FAB position)
- **Small Mobile**: ≤480px (reduced font sizes, padding)

### Animations
- **Panel Entry**: 0.3s slide-in animation
  - Desktop: from right
  - Mobile: from bottom
- **Hover/Focus**: Scale and glow effects
- **Transitions**: 0.3s ease for smooth interactions

## Accessibility Features

### Keyboard Navigation
- **FAB**: Enter/Space to toggle
- **Panel**:
  - Tab/Shift+Tab to navigate controls
  - Escape to close
  - Focus trap within panel
  - Focus returns to FAB on close

### Screen Reader Support
- All controls properly labeled
- ARIA roles and states
- Semantic HTML structure
- Live region announcements (handled by parent context)

### Touch Targets
- Minimum 44x44px for all interactive elements (WCAG AA)
- Mobile: 48x48px FAB, generous padding on controls

## High Contrast Mode
The widget itself adapts to high contrast mode when applied:
- Black background
- White borders and text
- Enhanced focus indicators

## Print Styles
The widget is hidden when printing the page.

## Browser Support
- Modern browsers (Chrome, Firefox, Safari, Edge)
- IE11+ (with polyfills)
- Mobile browsers (iOS Safari, Chrome Android)

## Notes
- Z-index: 12000 (ensures widget stays above other content)
- Click outside panel to close
- State managed locally for panel visibility
- Settings synced with global context
