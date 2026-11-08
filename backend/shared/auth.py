"""
Authentication / authorization for the Sea Level Dashboard.

Identity comes from Amazon Cognito (Google is the identity provider).

  * On AWS, API Gateway's Cognito authorizer validates the ID token before the
    Lambda runs and passes the claims in
    event["requestContext"]["authorizer"]["claims"].
  * When running the FastAPI app locally / on-prem, `verify_bearer_token`
    validates the token itself against the user pool's JWKS and the app puts
    the claims into the same place, so handlers see one shape everywhere.

Environment:
  AUTH_MODE              cognito (default) | disabled  (disabled = local dev only)
  COGNITO_REGION         e.g. il-central-1
  COGNITO_USER_POOL_ID   e.g. il-central-1_AbCdEf
  COGNITO_APP_CLIENT_ID  the SPA app client id (ID token "aud")
  ADMIN_EMAILS           comma-separated, e.g. benp@mapi.gov.il
  ADMIN_GROUP            Cognito group that also grants admin (default "admin")
  ALLOW_INSECURE_LOCAL_CALIBRATION  "true" lets calibration run with AUTH_MODE=disabled (dev DB only)
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def auth_mode() -> str:
    return _env("AUTH_MODE", "cognito").lower()


def admin_emails() -> set:
    return {e.strip().lower() for e in _env("ADMIN_EMAILS").split(",") if e.strip()}


@dataclass
class Identity:
    sub: str
    email: str
    email_verified: bool
    groups: List[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        if not self.email_verified:
            return False
        return self.email.lower() in admin_emails() or _env("ADMIN_GROUP", "admin") in self.groups

    def to_public(self) -> Dict[str, Any]:
        return {"email": self.email, "is_admin": self.is_admin, "groups": self.groups}


def _parse_groups(raw: Any) -> List[str]:
    """cognito:groups arrives as a list (JWT) or a string like "[admin, x]" / "admin,x" (API GW REST)."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(g) for g in raw]
    s = str(raw).strip().strip("[]")
    return [g.strip() for g in s.replace(",", " ").split() if g.strip()]


def identity_from_claims(claims: Optional[Dict[str, Any]]) -> Optional[Identity]:
    if not claims or not claims.get("sub"):
        return None
    verified = claims.get("email_verified")
    # Federated Google users: Cognito maps email_verified as string "true"
    verified = verified is True or str(verified).lower() == "true"
    return Identity(
        sub=str(claims["sub"]),
        email=str(claims.get("email", "")).lower(),
        email_verified=verified,
        groups=_parse_groups(claims.get("cognito:groups")),
    )


def identity_from_event(event: Dict[str, Any]) -> Optional[Identity]:
    """Read the caller identity placed by API Gateway (or by the local FastAPI adapter)."""
    if auth_mode() == "disabled":
        return Identity(sub="local-dev", email="local-dev@localhost", email_verified=True,
                        groups=["admin"] if _env("ALLOW_INSECURE_LOCAL_CALIBRATION").lower() == "true" else [])
    ctx = (event or {}).get("requestContext") or {}
    authorizer = ctx.get("authorizer") or {}
    claims = authorizer.get("claims") or (authorizer.get("jwt") or {}).get("claims")
    return identity_from_claims(claims)


# ---------------------------------------------------------------------------
# Token verification (used when the app runs outside API Gateway)
# ---------------------------------------------------------------------------
_JWKS_CACHE: Dict[str, Any] = {"keys": None, "fetched": 0.0}
_JWKS_TTL = 3600


def _issuer() -> str:
    return f"https://cognito-idp.{_env('COGNITO_REGION')}.amazonaws.com/{_env('COGNITO_USER_POOL_ID')}"


def _jwks() -> List[Dict[str, Any]]:
    now = time.time()
    if _JWKS_CACHE["keys"] is None or now - _JWKS_CACHE["fetched"] > _JWKS_TTL:
        with urllib.request.urlopen(f"{_issuer()}/.well-known/jwks.json", timeout=5) as resp:
            _JWKS_CACHE["keys"] = json.loads(resp.read())["keys"]
            _JWKS_CACHE["fetched"] = now
    return _JWKS_CACHE["keys"]


class AuthError(Exception):
    pass


def verify_bearer_token(authorization_header: Optional[str]) -> Dict[str, Any]:
    """Validate a Cognito ID token (signature, issuer, audience, expiry, token_use). Returns claims."""
    from jose import jwt  # python-jose

    if not authorization_header or not authorization_header.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    token = authorization_header.split(" ", 1)[1].strip()
    if not _env("COGNITO_USER_POOL_ID") or not _env("COGNITO_APP_CLIENT_ID"):
        raise AuthError("auth not configured")
    try:
        header = jwt.get_unverified_header(token)
        key = next((k for k in _jwks() if k.get("kid") == header.get("kid")), None)
        if key is None:
            _JWKS_CACHE["keys"] = None  # key rotation: refetch once
            key = next((k for k in _jwks() if k.get("kid") == header.get("kid")), None)
        if key is None:
            raise AuthError("unknown signing key")
        claims = jwt.decode(
            token, key, algorithms=["RS256"],
            audience=_env("COGNITO_APP_CLIENT_ID"), issuer=_issuer(),
            options={"verify_at_hash": False},
        )
    except AuthError:
        raise
    except Exception as exc:  # signature/expiry/claims errors
        raise AuthError(f"invalid token: {type(exc).__name__}") from exc
    if claims.get("token_use") != "id":
        raise AuthError("ID token required")
    return claims
