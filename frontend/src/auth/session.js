/**
 * Cognito Hosted UI session handling (OAuth 2.0 authorization code + PKCE).
 *
 * - No client secret: the SPA app client is public; PKCE protects the code exchange.
 * - Tokens live in sessionStorage (cleared when the tab closes). The ID token is sent
 *   as the Bearer token; API Gateway's Cognito authorizer validates it.
 * - The server is the only authority on permissions. `isAdmin` here only decides
 *   which UI to show.
 */
import { AUTH, isSameApi } from '../config';

const K = {
  id: 'sl_id_token',
  refresh: 'sl_refresh_token',
  exp: 'sl_expires_at',
  verifier: 'sl_pkce_verifier',
  state: 'sl_oauth_state',
  returnTo: 'sl_return_to',
};

export const CALLBACK_PATH = '/auth/callback';
const redirectUri = () => `${window.location.origin}${CALLBACK_PATH}`;

const b64url = (bytes) =>
  btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

const randomString = (len = 64) => {
  const arr = new Uint8Array(len);
  window.crypto.getRandomValues(arr);
  return b64url(arr).slice(0, len);
};

export function decodeJwt(token) {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(payload).split('').map((c) => `%${`00${c.charCodeAt(0).toString(16)}`.slice(-2)}`).join('')
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export const getIdToken = () => sessionStorage.getItem(K.id);

function storeTokens({ id_token, refresh_token, expires_in }) {
  if (id_token) sessionStorage.setItem(K.id, id_token);
  if (refresh_token) sessionStorage.setItem(K.refresh, refresh_token);
  sessionStorage.setItem(K.exp, String(Date.now() + (Number(expires_in) || 3600) * 1000));
}

export function clearSession() {
  Object.values(K).forEach((k) => sessionStorage.removeItem(k));
}

export function currentUser() {
  const token = getIdToken();
  const claims = token && decodeJwt(token);
  if (!claims) return null;
  const groups = claims['cognito:groups'] || [];
  return {
    email: claims.email,
    name: claims.name || claims.given_name || claims.email,
    picture: claims.picture,
    groups,
    // UI hint only — the API enforces admin rights itself.
    isAdmin: groups.includes('admin'),
    expiresAt: Number(sessionStorage.getItem(K.exp)) || 0,
  };
}

export async function login(returnTo = window.location.pathname + window.location.search) {
  const verifier = randomString(64);
  const state = randomString(32);
  const challenge = b64url(await window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)));
  sessionStorage.setItem(K.verifier, verifier);
  sessionStorage.setItem(K.state, state);
  sessionStorage.setItem(K.returnTo, returnTo.startsWith('/') && !returnTo.startsWith('//') ? returnTo : '/');
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: AUTH.clientId,
    redirect_uri: redirectUri(),
    scope: AUTH.scopes,
    state,
    code_challenge: challenge,
    code_challenge_method: 'S256',
    identity_provider: AUTH.identityProvider,
  });
  window.location.assign(`${AUTH.domain}/oauth2/authorize?${params}`);
}

export function logout() {
  clearSession();
  const params = new URLSearchParams({ client_id: AUTH.clientId, logout_uri: `${window.location.origin}/` });
  window.location.assign(`${AUTH.domain}/logout?${params}`);
}

async function tokenRequest(body) {
  const res = await nativeFetch(`${AUTH.domain}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_id: AUTH.clientId, ...body }),
  });
  if (!res.ok) throw new Error(`Token endpoint returned ${res.status}`);
  return res.json();
}

/** Handle /auth/callback?code=...&state=... Returns the path to go back to. */
export async function completeLogin(search) {
  const q = new URLSearchParams(search);
  if (q.get('error')) throw new Error(q.get('error_description') || q.get('error'));
  const expected = sessionStorage.getItem(K.state);
  if (!q.get('code') || !expected || q.get('state') !== expected) throw new Error('Sign-in state mismatch — please try again');
  const tokens = await tokenRequest({
    grant_type: 'authorization_code',
    code: q.get('code'),
    redirect_uri: redirectUri(),
    code_verifier: sessionStorage.getItem(K.verifier) || '',
  });
  storeTokens(tokens);
  sessionStorage.removeItem(K.verifier);
  sessionStorage.removeItem(K.state);
  const back = sessionStorage.getItem(K.returnTo) || '/';
  sessionStorage.removeItem(K.returnTo);
  return back;
}

let refreshing = null;
export async function refreshSession() {
  const rt = sessionStorage.getItem(K.refresh);
  if (!rt) return false;
  if (!refreshing) {
    refreshing = tokenRequest({ grant_type: 'refresh_token', refresh_token: rt })
      .then((t) => { storeTokens(t); return true; })
      .catch(() => { clearSession(); return false; })
      .finally(() => { refreshing = null; });
  }
  return refreshing;
}

async function ensureFreshToken() {
  const exp = Number(sessionStorage.getItem(K.exp)) || 0;
  if (getIdToken() && Date.now() > exp - 60_000) await refreshSession();
  return getIdToken();
}

// ---------------------------------------------------------------------------
// Attach the token to every API call, including components that call fetch()
// directly. Requests to other origins (GovMap, OSM tiles, IMS) are untouched.
// ---------------------------------------------------------------------------
const nativeFetch = window.fetch.bind(window);
let installed = false;

export function installAuthFetch(onUnauthorized) {
  if (installed || AUTH.mode === 'disabled') return;
  installed = true;
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url;
    if (!isSameApi(url)) return nativeFetch(input, init);
    const withAuth = async () => {
      const token = await ensureFreshToken();
      const headers = new Headers(init.headers || (typeof input !== 'string' ? input.headers : undefined));
      if (token) headers.set('Authorization', `Bearer ${token}`);
      return nativeFetch(input, { ...init, headers });
    };
    let res = await withAuth();
    if (res.status === 401 && (await refreshSession())) res = await withAuth();
    if (res.status === 401 && onUnauthorized) onUnauthorized();
    return res;
  };
}

// Same-origin iframes (mapframe.html) read the token through this hook.
window.__seaLevelGetIdToken = () => getIdToken();
