/**
 * Runtime configuration (values are baked in at build time by CRA).
 *
 * REACT_APP_API_URL:
 *   - unset  → local dev default (http://127.0.0.1:30886)
 *   - ""     → same origin (AWS: CloudFront routes /api/* to API Gateway)
 *   - URL    → explicit backend
 *   - "auto" → same host the page was opened from, port REACT_APP_API_PORT (default 30886) — on-prem:
 *              works for every address the server is reached by (public IP, LAN name, localhost)
 * Never put secrets in REACT_APP_* variables — they are readable in the bundle.
 */
const env = process.env;
const resolveApiUrl = () => {
  const v = env.REACT_APP_API_URL;
  if (v === undefined) return 'http://127.0.0.1:30886';
  if (v === 'auto') {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:${env.REACT_APP_API_PORT || '30886'}`;
  }
  return v.replace(/\/$/, '');
};

export const API_BASE_URL = resolveApiUrl();

export const AUTH = {
  // "cognito" (default) or "disabled" (local development only)
  mode: (env.REACT_APP_AUTH_MODE || 'cognito').toLowerCase(),
  // Cognito Hosted UI domain, e.g. https://sealevel-prod.auth.il-central-1.amazoncognito.com
  domain: (env.REACT_APP_COGNITO_DOMAIN || '').replace(/\/$/, ''),
  clientId: env.REACT_APP_COGNITO_CLIENT_ID || '',
  // Identity provider name configured in Cognito ("Google")
  identityProvider: env.REACT_APP_COGNITO_IDP || 'Google',
  scopes: 'openid email profile',
};

export const isSameApi = (url) => {
  if (typeof url !== 'string') return false;
  if (API_BASE_URL === '') return url.startsWith('/api/') || url.startsWith(`${window.location.origin}/api/`);
  return url.startsWith(API_BASE_URL);
};
