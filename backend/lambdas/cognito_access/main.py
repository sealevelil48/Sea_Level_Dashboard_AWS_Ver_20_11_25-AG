"""
Cognito Lambda trigger: only approved accounts can sign up / sign in.

Wire to the user pool as both PreSignUp and PreTokenGeneration, so removing someone from the
allowlist takes effect at their next sign-in or token refresh (≤ 1 hour).

Allowlist (SSM Parameter Store, StringList, editable without redeploying):
  /sealevel/<env>/allowed-users = "mapi.gov.il, @client-company.co.il, alice@gmail.com"
  - "@domain" or "domain"  → everyone with a verified address at that domain
  - "user@domain"          → that one address
Admins (ADMIN_EMAILS) are always allowed. Future: replace the SSM list with a CRM lookup.
"""
import logging
import os
import time

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_CACHE = {"value": None, "at": 0.0}
_TTL = 60


def _allowlist():
    if _CACHE["value"] is None or time.time() - _CACHE["at"] > _TTL:
        import boto3
        raw = boto3.client("ssm").get_parameter(Name=os.environ["ALLOWLIST_PARAM"])["Parameter"]["Value"]
        _CACHE.update(value=[e.strip().lower() for e in raw.split(",") if e.strip()], at=time.time())
    return _CACHE["value"]


def is_allowed(email: str, entries) -> bool:
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    admins = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    if email in admins:
        return True
    domain = email.split("@", 1)[1]
    for entry in entries:
        if "@" in entry and not entry.startswith("@"):
            if email == entry:
                return True
        elif domain == entry.lstrip("@"):
            return True
    return False


def handler(event, context):
    attrs = event.get("request", {}).get("userAttributes", {})
    email = attrs.get("email", "")
    source = event.get("triggerSource", "")
    if not is_allowed(email, _allowlist()):
        logger.info("Access denied (%s) for domain %s", source, email.split("@")[-1] if "@" in email else "?")
        raise Exception("This account is not approved for the Sea Level Dashboard. Contact the Israel Mapping Center.")
    if source.startswith("PreSignUp"):
        # Federated Google accounts arrive verified; don't send Cognito confirmation emails.
        event["response"]["autoConfirmUser"] = True
        if attrs.get("email"):
            event["response"]["autoVerifyEmail"] = True
    return event
