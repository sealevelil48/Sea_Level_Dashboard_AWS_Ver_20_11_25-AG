"""API protection: every data route needs a valid Cognito ID token; admin routes need the admin."""
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

POOL, CLIENT_ID, REGION = "il-central-1_TEST", "test-client", "il-central-1"
ISS = f"https://cognito-idp.{REGION}.amazonaws.com/{POOL}"


@pytest.fixture(scope="module")
def keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    public_jwk = jwk.construct(pub, "RS256").to_dict()
    public_jwk.update(kid="k1", use="sig", alg="RS256")
    public_jwk = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in public_jwk.items()}
    return pem, public_jwk


@pytest.fixture(scope="module")
def client(keys, monkeypatch_module):
    monkeypatch_module.setenv("AUTH_MODE", "cognito")
    monkeypatch_module.setenv("COGNITO_REGION", REGION)
    monkeypatch_module.setenv("COGNITO_USER_POOL_ID", POOL)
    monkeypatch_module.setenv("COGNITO_APP_CLIENT_ID", CLIENT_ID)
    from shared import auth
    auth._JWKS_CACHE.update(keys=[keys[1]], fetched=time.time() + 10_000)
    from fastapi.testclient import TestClient
    import app as app_module
    return TestClient(app_module.app)


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def token(keys, email="client@example.com", **overrides):
    claims = {"sub": email, "email": email, "email_verified": True, "aud": CLIENT_ID, "iss": ISS,
              "token_use": "id", "exp": int(time.time()) + 600, "iat": int(time.time())}
    claims.update(overrides)
    return jwt.encode(claims, keys[0], algorithm="RS256", headers={"kid": "k1"})


def H(t):
    return {"Authorization": f"Bearer {t}"}


def test_health_is_public(client):
    assert client.get("/api/health").status_code == 200


def test_mapframes_are_public(client):
    assert client.get("/api/mapframe").status_code == 200
    assert client.get("/api/mariners-mapframe").status_code == 200


@pytest.mark.parametrize("path", ["/api/me", "/api/stations", "/api/data", "/api/stations/map", "/api/live-data",
                                  "/api/analytics", "/api/sea-forecast", "/api/ims-warnings"])
def test_data_routes_require_token(client, path):
    assert client.get(path).status_code == 401


def test_rejects_bad_tokens(client, keys):
    assert client.get("/api/me", headers=H(token(keys, exp=int(time.time()) - 5))).status_code == 401   # expired
    assert client.get("/api/me", headers=H(token(keys, aud="other-app"))).status_code == 401            # wrong client
    assert client.get("/api/me", headers=H(token(keys, iss="https://evil"))).status_code == 401         # wrong issuer
    assert client.get("/api/me", headers=H(token(keys, token_use="access"))).status_code == 401         # access token
    forged = token(keys)[:-4] + "AAAA"
    assert client.get("/api/me", headers=H(forged)).status_code == 401                                   # bad signature


def test_client_user_signed_in_but_not_admin(client, keys):
    r = client.get("/api/me", headers=H(token(keys)))
    assert r.status_code == 200 and r.json()["is_admin"] is False
    assert client.post("/api/calibration/preview", json={}, headers=H(token(keys))).status_code == 403
    assert client.post("/api/cache/clear", headers=H(token(keys))).status_code == 403
    assert client.get("/api/metrics", headers=H(token(keys))).status_code == 403


def test_admin(client, keys):
    t = token(keys, email="benp@mapi.gov.il")
    assert client.get("/api/me", headers=H(t)).json()["is_admin"] is True
    # Admin email with unverified address is NOT admin
    assert client.get("/api/me", headers=H(token(keys, email="benp@mapi.gov.il", email_verified=False))).json()["is_admin"] is False


def test_calibration_rejects_non_json(client, keys):
    t = token(keys, email="benp@mapi.gov.il")
    r = client.post("/api/calibration/preview", content="x", headers={**H(t), "Content-Type": "text/plain"})
    assert r.status_code == 415


def test_docs_disabled_by_default(client):
    assert client.get("/api/docs").status_code in (401, 404)
    assert client.get("/docs").status_code == 404


def test_lambda_event_claims_are_trusted_only_from_api_gateway(client):
    """A client cannot smuggle claims: outside Lambda the app always verifies the bearer token."""
    r = client.get("/api/me", headers={"X-Claims": '{"email":"benp@mapi.gov.il"}'})
    assert r.status_code == 401


def test_signed_in_user_gets_corrected_data(client, keys, database):
    r = client.get("/api/data", params={"station": "Haifa", "start_date": "2026-10-08", "end_date": "2026-10-09"},
                   headers=H(token(keys)))
    assert r.status_code == 200, r.text


def test_export_requires_sign_in(client):
    assert client.get("/api/export").status_code == 401


def test_export_csv_direct_on_prem(client, keys, database):
    r = client.get("/api/export", params={"station": "Haifa", "start_date": "2026-10-08", "end_date": "2026-10-09",
                                          "fmt": "csv"}, headers=H(token(keys)))
    assert r.status_code == 200, r.text
    assert "attachment" in r.headers["content-disposition"]
    assert "Tab_DateTime" in r.content.decode("utf-8-sig").splitlines()[0]


def test_export_rejects_bad_format(client, keys):
    assert client.get("/api/export", params={"fmt": "exe"}, headers=H(token(keys))).status_code == 422
