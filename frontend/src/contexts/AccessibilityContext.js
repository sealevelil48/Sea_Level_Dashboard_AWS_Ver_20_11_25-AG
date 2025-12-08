import React, { createContext, useState, useEffect, useCallback, useMemo } from 'react';

/**
 * Storage key for accessibility settings
 */
const STORAGE_KEY = 'seaLevelDashboard_accessibility';

/**
 * Default accessibility settings
 */
const DEFAULT_SETTINGS = {
  contrast: 'normal',
  textSize: 'normal',
  largeCursor: false,
  highlightLinks: false,
  dyslexiaFont: false
};

/**
 * Accessibility Context
 * Provides accessibility settings and controls throughout the application
 */
export const AccessibilityContext = createContext({
  settings: DEFAULT_SETTINGS,
  updateSetting: () => {},
  resetSettings: () => {}
});

AccessibilityContext.displayName = 'AccessibilityContext';

/**
 * AccessibilityProvider Component
 * Manages accessibility settings with localStorage persistence
 *
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - Child components
 * @returns {JSX.Element} Provider component
 */
export const AccessibilityProvider = ({ children }) => {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [storageAvailable, setStorageAvailable] = useState(false);

  /**
   * Check if localStorage is available
   */
  const checkStorage = useCallback(() => {
    try {
      const test = '__storage_test__';
      window.localStorage.setItem(test, test);
      window.localStorage.removeItem(test);
      return true;
    } catch (e) {
      console.warn('localStorage not available:', e);
      return false;
    }
  }, []);

  /**
   * Apply CSS classes to document.body based on accessibility settings
   */
  const applyAccessibilityClasses = useCallback((accessibilitySettings) => {
    // Remove all accessibility classes first
    document.body.classList.remove(
      'a11y-high-contrast',
      'a11y-text-normal',
      'a11y-text-large',
      'a11y-text-xl',
      'a11y-large-cursor',
      'a11y-highlight-links',
      'a11y-dyslexia-font'
    );

    // Apply contrast class
    if (accessibilitySettings.contrast === 'high') {
      document.body.classList.add('a11y-high-contrast');
    }

    // Apply text size class
    switch (accessibilitySettings.textSize) {
      case 'normal':
        document.body.classList.add('a11y-text-normal');
        break;
      case 'large':
        document.body.classList.add('a11y-text-large');
        break;
      case 'extra-large':
        document.body.classList.add('a11y-text-xl');
        break;
      default:
        document.body.classList.add('a11y-text-normal');
    }

    // Apply large cursor class
    if (accessibilitySettings.largeCursor) {
      document.body.classList.add('a11y-large-cursor');
    }

    // Apply highlight links class
    if (accessibilitySettings.highlightLinks) {
      document.body.classList.add('a11y-highlight-links');
    }

    // Apply dyslexia font class
    if (accessibilitySettings.dyslexiaFont) {
      document.body.classList.add('a11y-dyslexia-font');
    }
  }, []);

  /**
   * Initialize settings from localStorage on mount
   */
  useEffect(() => {
    const isAvailable = checkStorage();
    setStorageAvailable(isAvailable);

    if (isAvailable) {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const parsed = JSON.parse(stored);
          // Validate the parsed data has expected structure
          if (parsed && typeof parsed === 'object') {
            const validatedSettings = {
              contrast: ['normal', 'high'].includes(parsed.contrast)
                ? parsed.contrast
                : DEFAULT_SETTINGS.contrast,
              textSize: ['normal', 'large', 'extra-large'].includes(parsed.textSize)
                ? parsed.textSize
                : DEFAULT_SETTINGS.textSize,
              largeCursor: typeof parsed.largeCursor === 'boolean'
                ? parsed.largeCursor
                : DEFAULT_SETTINGS.largeCursor,
              highlightLinks: typeof parsed.highlightLinks === 'boolean'
                ? parsed.highlightLinks
                : DEFAULT_SETTINGS.highlightLinks,
              dyslexiaFont: typeof parsed.dyslexiaFont === 'boolean'
                ? parsed.dyslexiaFont
                : DEFAULT_SETTINGS.dyslexiaFont
            };
            setSettings(validatedSettings);
            applyAccessibilityClasses(validatedSettings);
          }
        } else {
          // No stored settings, apply default classes
          applyAccessibilityClasses(DEFAULT_SETTINGS);
        }
      } catch (error) {
        console.error('Error loading accessibility settings:', error);
        setSettings(DEFAULT_SETTINGS);
        applyAccessibilityClasses(DEFAULT_SETTINGS);
      }
    } else {
      // Storage not available, still apply default classes
      applyAccessibilityClasses(DEFAULT_SETTINGS);
    }
  }, [checkStorage, applyAccessibilityClasses]);

  /**
   * Sync settings to localStorage and apply CSS classes when settings change
   */
  useEffect(() => {
    if (storageAvailable) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
      } catch (error) {
        console.error('Error saving accessibility settings:', error);
      }
    }
    applyAccessibilityClasses(settings);
  }, [settings, storageAvailable, applyAccessibilityClasses]);

  /**
   * Update a specific accessibility setting
   *
   * @param {string} key - Setting key to update
   * @param {*} value - New value for the setting
   */
  const updateSetting = useCallback((key, value) => {
    if (!Object.prototype.hasOwnProperty.call(DEFAULT_SETTINGS, key)) {
      console.error(`Invalid accessibility setting key: ${key}`);
      return;
    }

    // Validate the value based on the key
    let isValid = false;
    switch (key) {
      case 'contrast':
        isValid = ['normal', 'high'].includes(value);
        break;
      case 'textSize':
        isValid = ['normal', 'large', 'extra-large'].includes(value);
        break;
      case 'largeCursor':
      case 'highlightLinks':
      case 'dyslexiaFont':
        isValid = typeof value === 'boolean';
        break;
      default:
        isValid = false;
    }

    if (!isValid) {
      console.error(`Invalid value for accessibility setting ${key}:`, value);
      return;
    }

    setSettings(prevSettings => ({
      ...prevSettings,
      [key]: value
    }));
  }, []);

  /**
   * Reset all accessibility settings to defaults
   */
  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
    if (storageAvailable) {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch (error) {
        console.error('Error resetting accessibility settings:', error);
      }
    }
  }, [storageAvailable]);

  /**
   * Memoize context value to prevent unnecessary re-renders
   */
  const contextValue = useMemo(() => ({
    settings,
    updateSetting,
    resetSettings
  }), [settings, updateSetting, resetSettings]);

  return (
    <AccessibilityContext.Provider value={contextValue}>
      {children}
    </AccessibilityContext.Provider>
  );
};

/**
 * Custom hook to use accessibility context
 *
 * @returns {Object} Accessibility context value
 * @throws {Error} If used outside of AccessibilityProvider
 */
export const useAccessibility = () => {
  const context = React.useContext(AccessibilityContext);
  if (!context) {
    throw new Error('useAccessibility must be used within an AccessibilityProvider');
  }
  return context;
};

export default AccessibilityContext;
