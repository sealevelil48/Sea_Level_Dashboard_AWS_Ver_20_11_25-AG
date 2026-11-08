import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Button, Spinner } from 'react-bootstrap';
import { AUTH, API_BASE_URL } from '../config';
import {
  CALLBACK_PATH, completeLogin, currentUser, getIdToken, installAuthFetch, login, logout, refreshSession,
} from './session';

const AuthContext = createContext({ user: null, isAdmin: false, login: () => {}, logout: () => {} });
export const useAuth = () => useContext(AuthContext);

const DEV_USER = { email: 'local-dev', name: 'Local development', groups: [] };

function Centered({ children }) {
  return (
    <div className="d-flex flex-column align-items-center justify-content-center text-center p-4"
         style={{ minHeight: '100vh', background: '#0c1c35', color: '#e8eef7' }}>
      {children}
    </div>
  );
}

function LoginScreen({ error }) {
  return (
    <Centered>
      <img src="/assets/Mapi_Logo2.png" alt="" style={{ height: 64, marginBottom: 24 }}
           onError={(e) => { e.currentTarget.style.display = 'none'; }} />
      <h1 className="h3 mb-2">Sea Level Monitoring Dashboard</h1>
      <p className="mb-4" style={{ maxWidth: 420, opacity: 0.85 }}>
        Sign in with your Google account to view station data.
        <br />
        <span dir="rtl" lang="he">יש להתחבר עם חשבון Google כדי לצפות בנתונים.</span>
      </p>
      {error && <div role="alert" className="alert alert-warning py-2" style={{ maxWidth: 420 }}>{error}</div>}
      <Button size="lg" variant="light" onClick={() => login()} aria-label="Sign in with Google">
        Sign in with Google
      </Button>
      <p className="mt-4 small" style={{ opacity: 0.6, maxWidth: 420 }}>
        Access is limited to approved accounts. If you cannot sign in, contact the Israel Mapping Center.
      </p>
    </Centered>
  );
}

export function AuthProvider({ children }) {
  const disabled = AUTH.mode === 'disabled';
  const [user, setUser] = useState(() => (disabled ? DEV_USER : currentUser()));
  const [isAdmin, setIsAdmin] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(!disabled && window.location.pathname === CALLBACK_PATH);

  const handleUnauthorized = useCallback(() => setUser(null), []);
  useEffect(() => { installAuthFetch(handleUnauthorized); }, [handleUnauthorized]);

  // OAuth callback
  useEffect(() => {
    if (disabled || window.location.pathname !== CALLBACK_PATH) return;
    completeLogin(window.location.search)
      .then((back) => { setUser(currentUser()); window.history.replaceState({}, '', back); })
      .catch((e) => { setError(e.message); window.history.replaceState({}, '', '/'); })
      .finally(() => setBusy(false));
  }, [disabled]);

  // Try a silent refresh when the stored ID token has expired.
  useEffect(() => {
    if (disabled || busy || user || !getIdToken()) return;
    refreshSession().then((ok) => ok && setUser(currentUser()));
  }, [disabled, busy, user]);

  // Ask the server what this user may do (the server is the authority).
  useEffect(() => {
    if (!user) { setIsAdmin(false); return; }
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/me`)
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => { if (!cancelled) setIsAdmin(Boolean(me?.is_admin)); })
      .catch(() => { if (!cancelled) setIsAdmin(false); });
    return () => { cancelled = true; };
  }, [user]);

  const value = useMemo(() => ({
    user, isAdmin, login: () => login(), logout: disabled ? () => {} : logout, authDisabled: disabled,
  }), [user, isAdmin, disabled]);

  if (busy) {
    return <Centered><Spinner animation="border" role="status" /><p className="mt-3">Signing you in…</p></Centered>;
  }
  if (!user) return <LoginScreen error={error} />;
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function UserMenu() {
  const { user, isAdmin, logout: doLogout, authDisabled } = useAuth();
  if (!user) return null;
  return (
    <div className="d-flex align-items-center gap-2 small" style={{ color: '#e8eef7' }}>
      {isAdmin && <span className="badge bg-warning text-dark" title="Calibration tools enabled">Admin</span>}
      <span className="d-none d-md-inline text-truncate" style={{ maxWidth: 180 }} title={user.email}>{user.email}</span>
      {!authDisabled && (
        <Button size="sm" variant="outline-light" onClick={doLogout}>Sign out</Button>
      )}
    </div>
  );
}
