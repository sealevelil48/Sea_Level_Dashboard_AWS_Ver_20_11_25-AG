import React, { useState, useEffect, useRef } from 'react';
import { useAccessibility } from '../../hooks/useAccessibility';
import './AccessibilityWidget.css';

const AccessibilityWidget = () => {
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const { settings, updateSetting, resetSettings } = useAccessibility();
  const fabRef = useRef(null);
  const panelRef = useRef(null);

  // Toggle panel visibility
  const togglePanel = () => {
    setIsPanelOpen(prev => !prev);
  };

  // Close panel and return focus to FAB
  const closePanel = () => {
    setIsPanelOpen(false);
    if (fabRef.current) {
      fabRef.current.focus();
    }
  };

  // Handle FAB keyboard navigation
  const handleFabKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      togglePanel();
    }
  };

  // Handle panel keyboard navigation
  const handlePanelKeyDown = (e) => {
    // Close on Escape
    if (e.key === 'Escape') {
      e.preventDefault();
      closePanel();
      return;
    }

    // Focus trap - Tab navigation
    if (e.key === 'Tab') {
      const focusableElements = panelRef.current.querySelectorAll(
        'button, [role="radio"], [role="switch"], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        // Shift + Tab
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        // Tab
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    }
  };

  // Focus management when panel opens
  useEffect(() => {
    if (isPanelOpen && panelRef.current) {
      const closeButton = panelRef.current.querySelector('.accessibility-close-btn');
      if (closeButton) {
        closeButton.focus();
      }
    }
  }, [isPanelOpen]);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        isPanelOpen &&
        panelRef.current &&
        fabRef.current &&
        !panelRef.current.contains(e.target) &&
        !fabRef.current.contains(e.target)
      ) {
        closePanel();
      }
    };

    if (isPanelOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [isPanelOpen]);

  // Handle contrast mode change
  const handleContrastChange = (mode) => {
    updateSetting('contrast', mode);
  };

  // Handle text size change
  const handleTextSizeChange = (size) => {
    updateSetting('textSize', size);
  };

  // Handle large cursor toggle
  const handleLargeCursorToggle = () => {
    updateSetting('largeCursor', !settings.largeCursor);
  };

  // Handle highlight links toggle
  const handleHighlightLinksToggle = () => {
    updateSetting('highlightLinks', !settings.highlightLinks);
  };

  return (
    <>
      {/* Floating Action Button */}
      <button
        ref={fabRef}
        className="accessibility-fab"
        onClick={togglePanel}
        onKeyDown={handleFabKeyDown}
        aria-label="Accessibility Settings"
        aria-expanded={isPanelOpen}
        aria-haspopup="dialog"
      >
        <span className="accessibility-fab-icon" aria-hidden="true">♿</span>
      </button>

      {/* Accessibility Panel */}
      {isPanelOpen && (
        <div
          ref={panelRef}
          className="accessibility-panel"
          role="dialog"
          aria-labelledby="accessibility-panel-title"
          aria-modal="false"
          onKeyDown={handlePanelKeyDown}
        >
          {/* Panel Header */}
          <div className="accessibility-panel-header">
            <h2 id="accessibility-panel-title" className="accessibility-panel-title">
              Accessibility Settings
            </h2>
            <button
              className="accessibility-close-btn"
              onClick={closePanel}
              aria-label="Close Accessibility Settings"
            >
              <span aria-hidden="true">&times;</span>
            </button>
          </div>

          {/* Panel Content */}
          <div className="accessibility-panel-content">
            {/* Contrast Mode Section */}
            <div className="accessibility-section">
              <h3 className="accessibility-section-title">Contrast Mode</h3>
              <div className="accessibility-radio-group" role="radiogroup" aria-label="Contrast Mode">
                <label className="accessibility-radio-label">
                  <input
                    type="radio"
                    name="contrast"
                    value="normal"
                    checked={settings.contrast === 'normal'}
                    onChange={() => handleContrastChange('normal')}
                    className="accessibility-radio-input"
                  />
                  <span className="accessibility-radio-custom" role="radio" aria-checked={settings.contrast === 'normal'}></span>
                  <span className="accessibility-radio-text">Normal</span>
                </label>
                <label className="accessibility-radio-label">
                  <input
                    type="radio"
                    name="contrast"
                    value="high"
                    checked={settings.contrast === 'high'}
                    onChange={() => handleContrastChange('high')}
                    className="accessibility-radio-input"
                  />
                  <span className="accessibility-radio-custom" role="radio" aria-checked={settings.contrast === 'high'}></span>
                  <span className="accessibility-radio-text">High Contrast</span>
                </label>
              </div>
            </div>

            {/* Text Size Section */}
            <div className="accessibility-section">
              <h3 className="accessibility-section-title">Text Size</h3>
              <div className="accessibility-radio-group" role="radiogroup" aria-label="Text Size">
                <label className="accessibility-radio-label">
                  <input
                    type="radio"
                    name="textSize"
                    value="normal"
                    checked={settings.textSize === 'normal'}
                    onChange={() => handleTextSizeChange('normal')}
                    className="accessibility-radio-input"
                  />
                  <span className="accessibility-radio-custom" role="radio" aria-checked={settings.textSize === 'normal'}></span>
                  <span className="accessibility-radio-text">Normal</span>
                </label>
                <label className="accessibility-radio-label">
                  <input
                    type="radio"
                    name="textSize"
                    value="large"
                    checked={settings.textSize === 'large'}
                    onChange={() => handleTextSizeChange('large')}
                    className="accessibility-radio-input"
                  />
                  <span className="accessibility-radio-custom" role="radio" aria-checked={settings.textSize === 'large'}></span>
                  <span className="accessibility-radio-text">Large</span>
                </label>
                <label className="accessibility-radio-label">
                  <input
                    type="radio"
                    name="textSize"
                    value="extraLarge"
                    checked={settings.textSize === 'extraLarge'}
                    onChange={() => handleTextSizeChange('extraLarge')}
                    className="accessibility-radio-input"
                  />
                  <span className="accessibility-radio-custom" role="radio" aria-checked={settings.textSize === 'extraLarge'}></span>
                  <span className="accessibility-radio-text">Extra Large</span>
                </label>
              </div>
            </div>

            {/* Large Cursor Section */}
            <div className="accessibility-section">
              <h3 className="accessibility-section-title">Large Cursor</h3>
              <label className="accessibility-toggle-label">
                <input
                  type="checkbox"
                  checked={settings.largeCursor}
                  onChange={handleLargeCursorToggle}
                  className="accessibility-toggle-input"
                  aria-label="Toggle Large Cursor"
                />
                <span
                  className="accessibility-toggle-switch"
                  role="switch"
                  aria-checked={settings.largeCursor}
                  tabIndex="0"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleLargeCursorToggle();
                    }
                  }}
                >
                  <span className="accessibility-toggle-slider"></span>
                </span>
                <span className="accessibility-toggle-text">
                  {settings.largeCursor ? 'Enabled' : 'Disabled'}
                </span>
              </label>
            </div>

            {/* Highlight Links Section */}
            <div className="accessibility-section">
              <h3 className="accessibility-section-title">Highlight Links</h3>
              <label className="accessibility-toggle-label">
                <input
                  type="checkbox"
                  checked={settings.highlightLinks}
                  onChange={handleHighlightLinksToggle}
                  className="accessibility-toggle-input"
                  aria-label="Toggle Highlight Links"
                />
                <span
                  className="accessibility-toggle-switch"
                  role="switch"
                  aria-checked={settings.highlightLinks}
                  tabIndex="0"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleHighlightLinksToggle();
                    }
                  }}
                >
                  <span className="accessibility-toggle-slider"></span>
                </span>
                <span className="accessibility-toggle-text">
                  {settings.highlightLinks ? 'Enabled' : 'Disabled'}
                </span>
              </label>
            </div>

            {/* Reset Button */}
            <div className="accessibility-section accessibility-reset-section">
              <button
                className="accessibility-reset-btn"
                onClick={() => {
                  resetSettings();
                  closePanel();
                }}
                aria-label="Reset all accessibility settings to default"
              >
                Reset to Default
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default AccessibilityWidget;
