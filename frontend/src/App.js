import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './utils/queryClientSetup';
import Dashboard from './components/Dashboard';
import Disclaimer from './components/Disclaimer';
import { AccessibilityProvider } from './contexts/AccessibilityContext';
import { AuthProvider } from './auth/AuthProvider';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

function App() {
  return (
    <AccessibilityProvider>
      <AuthProvider>
      <QueryClientProvider client={queryClient}>
        <Router>
          <div className="App">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/disclaimer" element={<Disclaimer />} />
              <Route path="*" element={<Dashboard />} />
            </Routes>
          </div>
        </Router>
      </QueryClientProvider>
      </AuthProvider>
    </AccessibilityProvider>
  );
}

export default App;