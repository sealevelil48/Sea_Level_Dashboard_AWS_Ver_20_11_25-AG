import { render, screen } from '@testing-library/react';
import App from '../App';

// The dashboard itself pulls in ESM chart libraries Jest can't parse; it is not under test here.
jest.mock('../components/Dashboard', () => () => {
  const React = require('react');
  return React.createElement('div', null, 'Dashboard');
});

describe('App (authentication gate)', () => {
  beforeEach(() => sessionStorage.clear());

  test('shows the Google sign-in screen when nobody is signed in', () => {
    render(<App />);
    expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument();
    // No dashboard data is requested before sign-in
    expect(screen.queryByText(/All Stations/i)).not.toBeInTheDocument();
  });

  test('never shows calibration controls on the sign-in screen', () => {
    render(<App />);
    expect(screen.queryByText(/Calibration Correction/i)).not.toBeInTheDocument();
  });
});
