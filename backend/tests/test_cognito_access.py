import pytest

from lambdas.cognito_access.main import is_allowed

LIST = ["mapi.gov.il", "@client.co.il", "alice@gmail.com"]


@pytest.mark.parametrize("email,ok", [
    ("benp@mapi.gov.il", True),          # admin, always
    ("someone@mapi.gov.il", True),       # allowed domain
    ("x@client.co.il", True),            # allowed domain with @
    ("alice@gmail.com", True),           # single address
    ("ALICE@Gmail.com", True),           # case-insensitive
    ("bob@gmail.com", False),            # other gmail
    ("x@evil-mapi.gov.il", False),       # suffix trick
    ("x@mapi.gov.il.evil.com", False),   # suffix trick
    ("", False), ("not-an-email", False),
])
def test_allowlist(monkeypatch, email, ok):
    monkeypatch.setenv("ADMIN_EMAILS", "benp@mapi.gov.il")
    assert is_allowed(email, LIST) is ok
