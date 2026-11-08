/**
 * Runtime configuration (values are baked in at build time by CRA).
 *
 * REACT_APP_API_URL:
 *   - unset  → local dev default (http://127.0.0.1:30886)
 *   - ""     → same origin (AWS: CloudFront routes /api/* to API Gateway)
 *   - URL    → explicit backend
 * Never put secrets in REACT_APP_* variables — they are readable in the bundle.
 */
const env = process.env;

export const API_BASE_URL =
  env.REACT_APP_API_URL !== undefined ? env.REACT_APP_API_URL.replace(/\/$/, '') : 'http://127.0.0.1:30886';

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
