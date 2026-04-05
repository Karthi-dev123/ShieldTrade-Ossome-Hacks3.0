"""Tests for scripts/armoriq_stub.py — ArmorIQ intent token integration.

These tests exercise the HMAC fallback path (no real API key → demo key is used).
The real ArmorIQ IAP path is tested only when ARMORIQ_API_KEY is set and the
bridge is reachable (not suitable for offline CI).
"""

import base64
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import armoriq_stub


# Use a non-live key so tests run offline and hit the HMAC fallback
_TEST_KEY = "test-secret-key-for-unit-tests"


@pytest.fixture(autouse=True)
def force_hmac_fallback(monkeypatch):
    """Ensure tests use HMAC fallback by setting a non-live key and disabling bridge."""
    monkeypatch.setenv("ARMORIQ_API_KEY", _TEST_KEY)
    # Patch _USE_REAL_API to False so bridge is not invoked in unit tests
    monkeypatch.setattr(armoriq_stub, "_USE_REAL_API", False)


def test_issue_returns_json():
    token = armoriq_stub.issue("AAPL", 5, "buy", "check_abc123")
    data = json.loads(token)
    assert data["symbol"] == "AAPL"
    assert data["qty"] == 5
    assert data["side"] == "buy"
    assert data["policy_check_id"] == "check_abc123"
    assert data["source"] == "hmac_fallback"
    assert "_hmac_token" in data


def test_issue_and_verify_round_trip():
    token = armoriq_stub.issue("AAPL", 5, "buy", "check_abc123")
    payload = armoriq_stub.verify(token)
    assert payload["symbol"] == "AAPL"
    assert payload["qty"] == 5
    assert payload["side"] == "buy"
    assert payload["policy_check_id"] == "check_abc123"
    assert "iss" in payload


def test_issue_without_policy_check_id():
    token = armoriq_stub.issue("MSFT", 10, "sell")
    payload = armoriq_stub.verify(token)
    assert payload["symbol"] == "MSFT"
    assert "policy_check_id" not in payload


def test_symbol_uppercased():
    token = armoriq_stub.issue("aapl", 1, "buy")
    payload = armoriq_stub.verify(token)
    assert payload["symbol"] == "AAPL"


def test_invalid_hmac_signature_rejected():
    token = armoriq_stub.issue("AAPL", 5, "buy")
    data = json.loads(token)
    # Corrupt the signature in the embedded _hmac_token
    parts = data["_hmac_token"].split(".")
    assert len(parts) == 3
    data["_hmac_token"] = f"{parts[0]}.{parts[1]}.{'aa' * 32}"
    bad_token = json.dumps(data)
    with pytest.raises(ValueError, match="signature invalid"):
        armoriq_stub.verify(bad_token)


def test_tampered_payload_rejected():
    """Changing the HMAC payload invalidates the signature."""
    token = armoriq_stub.issue("AAPL", 5, "buy")
    data = json.loads(token)
    h, p, sig = data["_hmac_token"].split(".")
    pad = 4 - len(p) % 4
    raw = base64.urlsafe_b64decode(p + "=" * (pad if pad != 4 else 0))
    payload = json.loads(raw)
    payload["qty"] = 999
    new_p = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    data["_hmac_token"] = f"{h}.{new_p}.{sig}"
    bad_token = json.dumps(data)
    with pytest.raises(ValueError, match="signature invalid"):
        armoriq_stub.verify(bad_token)


def test_malformed_token_rejected():
    """Non-JSON token raises ValueError."""
    with pytest.raises(ValueError):
        armoriq_stub.verify("not-valid-json-at-all")


def test_malformed_hmac_parts_rejected():
    """JSON token with bad _hmac_token format raises ValueError."""
    bad = json.dumps({"_hmac_token": "only.two"})
    with pytest.raises(ValueError, match="Malformed"):
        armoriq_stub.verify(bad)


def test_expired_token_rejected():
    """Expired HMAC token raises ValueError — inject an already-past exp."""
    token = armoriq_stub.issue("AAPL", 1, "buy")
    data = json.loads(token)
    h, p, _ = data["_hmac_token"].split(".")
    # Decode, set exp in the past, re-sign with the test key
    pad = 4 - len(p) % 4
    payload = json.loads(base64.urlsafe_b64decode(p + "=" * (pad if pad != 4 else 0)))
    payload["exp"] = int(time.time()) - 10  # already expired
    import hashlib, hmac as _hmac
    new_p = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    sig = _hmac.new(_TEST_KEY.encode(), f"{h}.{new_p}".encode(), hashlib.sha256).hexdigest()
    data["_hmac_token"] = f"{h}.{new_p}.{sig}"
    expired_token = json.dumps(data)
    with pytest.raises(ValueError, match="expired"):
        armoriq_stub.verify(expired_token)


def test_missing_key_uses_demo_fallback(monkeypatch):
    """Without ARMORIQ_API_KEY the stub uses a demo key and still issues tokens."""
    monkeypatch.delenv("ARMORIQ_API_KEY", raising=False)
    monkeypatch.setattr(armoriq_stub, "_USE_REAL_API", False)
    # Should not raise — uses built-in fallback key
    token = armoriq_stub.issue("AAPL", 1, "buy")
    data = json.loads(token)
    assert data["symbol"] == "AAPL"
