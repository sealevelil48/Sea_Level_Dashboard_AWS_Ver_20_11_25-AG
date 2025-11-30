import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './utils/queryClientSetup';
import Dashboard from './components/Dashboard';
import Disclaimer from './components/Disclaimer';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="App">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/disclaimer" element={<Disclaimer />} />
          </Routes>
        </div>
      </Router>
    </QueryClientProvider>
  );
}

export default App;