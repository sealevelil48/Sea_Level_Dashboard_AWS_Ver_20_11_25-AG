import React, { useState, useEffect } from 'react';
import AccessibilityWidget from '../Accessibility/AccessibilityWidget';

const DashboardHeader = ({ isMobile }) => {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="header">
      <h1 className="navbar-brand">
        <img
          src="/assets/Mapi_Logo2.png"
          alt="Survey of Israel Logo"
          onClick={() => window.location.reload()}
          style={{
            height: isMobile ? '25px' : '40px',
            marginRight: isMobile ? '6px' : '10px',
            cursor: 'pointer'
          }}
        />
        <span style={{ fontSize: isMobile ? '1rem' : '1.8rem' }}>
          {isMobile ? 'Sea Level Dashboard' : 'Sea Level Monitoring Dashboard'}
        </span>
      </h1>
      <div id="current-time" style={{ fontSize: isMobile ? '11px' : '18px' }}>
        {currentTime.toLocaleString()}
      </div>
      <AccessibilityWidget />
    </div>
  );
};

export default React.memo(DashboardHeader);
