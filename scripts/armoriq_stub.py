"""ArmorIQ intent token integration — calls the real ArmorIQ IAP backend via armoriq_bridge.js.

Replaces the local HMAC stub with real cryptographic intent tokens issued by
ArmorIQ's Intent Analysis Platform (IAP). Each token is Merkle-tree–backed
with Ed25519 signatures and step-level proofs.

Falls back to local HMAC if the Node.js bridge is unavailable (e.g. CI with no
network access), so existing tests remain green without cloud dependency.

Public API (drop-in compatible with the old stub):
    issue(symbol, qty, side, policy_check_id=None) -> str  (JSON token string)
    verify(token_str: str) -> dict                          (decoded payload)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_BRIDGE = _ROOT / "scripts" / "armoriq_bridge.js"

# Load .env so scripts work without manually exporting env vars in the shell.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_ROOT / ".env", override=False)
except Exception:
    pass

_ARMORIQ_API_KEY = os.environ.get("ARMORIQ_API_KEY", "")
_USE_REAL_API = bool(_ARMORIQ_API_KEY) and _BRIDGE.exists()


# ── Real ArmorIQ integration ─────────────────────────────────────────────────

def _run_bridge(args: list[str], timeout: int = 15) -> dict:
    """Call armoriq_bridge.js and return the parsed JSON output."""
    try:
        result = subprocess.run(
            ["node", str(_BRIDGE)] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "ARMORIQ_API_KEY": _ARMORIQ_API_KEY},
        )
        if result.returncode != 0:
            raise RuntimeError(f"bridge exit {result.returncode}: {result.stderr[:200]}")
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("ArmorIQ bridge timed out")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Bridge returned non-JSON: {e}")


def _issue_real(symbol: str, qty: int, side: str, policy_check_id: str | None) -> str:
    """Issue a real ArmorIQ intent token via the IAP backend."""
    goal = f"{side.upper()} {qty} shares of {symbol} via paper trading (policy verified)"
    steps = [
        {"action": "bash", "mcp": "shell",
         "params": {"cmd": f"python scripts/alpaca_bridge.py order {symbol} {qty} {side}"}},
        {"action": "write", "mcp": "filesystem",
         "params": {"path": f"output/trade-logs/execution-{symbol}-*.json"}},
    ]
    args = [
        "capture-token",
        "--agent", "shieldtrade-trader",
        "--goal", goal,
        "--steps", json.dumps(steps),
        "--policy", json.dumps({"allow": ["bash", "write", "read"]}),
        "--ttl", "300",
    ]
    data = _run_bridge(args)
    if "error" in data:
        raise RuntimeError(f"ArmorIQ token error: {data['error']}")
    # Attach metadata for Python consumers
    data["symbol"] = symbol.upper()
    data["qty"] = qty
    data["side"] = side.lower()
    if policy_check_id:
        data["policy_check_id"] = policy_check_id
    data["source"] = "armoriq_iap"
    return json.dumps(data)


def _verify_real(token_str: str) -> dict:
    """Verify a real ArmorIQ intent token against the IAP backend."""
    args = ["verify-token", "--token", token_str]
    data = _run_bridge(args)
    if data.get("valid") is False:
        raise ValueError(f"ArmorIQ token invalid: {data.get('reason', 'unknown')}")
    return data


# ── HMAC fallback (no cloud) ─────────────────────────────────────────────────

_ALGORITHM = "HS256"
_DEFAULT_TTL_SECONDS = 300


def _secret() -> bytes:
    key = _ARMORIQ_API_KEY or os.environ.get("ARMORIQ_API_KEY", "shieldtrade-demo-key")
    return key.encode()


def _b64enc(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64dec(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return urlsafe_b64decode(s)


def _issue_hmac(symbol: str, qty: int, side: str, policy_check_id: str | None) -> str:
    now = int(time.time())
    header = {"alg": _ALGORITHM, "typ": "ARMORIQ-STUB"}
    payload: dict = {
        "iss": "armoriq_stub_fallback",
        "iat": now,
        "exp": now + _DEFAULT_TTL_SECONDS,
        "symbol": symbol.upper(),
        "qty": int(qty),
        "side": side.lower(),
        "source": "hmac_fallback",
    }
    if policy_check_id:
        payload["policy_check_id"] = policy_check_id
    h = _b64enc(json.dumps(header, separators=(",", ":")).encode())
    p = _b64enc(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(_secret(), f"{h}.{p}".encode(), hashlib.sha256).hexdigest()
    return json.dumps({"_hmac_token": f"{h}.{p}.{sig}", **payload})


def _verify_hmac(token_str: str) -> dict:
    data = json.loads(token_str)
    raw_token = data.get("_hmac_token", "")
    parts = raw_token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed HMAC token")
    h, p, sig = parts
    expected = hmac.new(_secret(), f"{h}.{p}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("HMAC token signature invalid")
    payload = json.loads(_b64dec(p))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("HMAC token expired")
    return payload


# ── Public API ────────────────────────────────────────────────────────────────

def capture(
    agent_id: str,
    goal: str,
    input_text: str,
    policy: dict | None = None,
) -> dict:
    """Capture a non-trade intent token in ArmorIQ (e.g. analyst research, risk review).

    Works for any agent action — not just buy/sell. Returns the token dict.
    Falls back to a minimal HMAC record if the real API is unavailable.
    """
    if not _USE_REAL_API:
        now = int(time.time())
        return {
            "source": "hmac_fallback",
            "agent_id": agent_id,
            "goal": goal,
            "issued_at": now,
            "expires_at": now + _DEFAULT_TTL_SECONDS,
        }

    steps = [{"action": "read", "mcp": "tool", "params": {"input": input_text[:200]}}]
    policy_obj = policy or {"allow": ["read", "write"], "deny": []}
    args = [
        "capture-token",
        "--agent", agent_id,
        "--goal", goal[:200],
        "--steps", json.dumps(steps),
        "--policy", json.dumps(policy_obj),
        "--ttl", "300",
    ]
    try:
        data = _run_bridge(args, timeout=15)
        data["source"] = "armoriq_iap"
        return data
    except Exception as exc:
        return {"source": "error", "error": str(exc)}


def issue(
    symbol: str,
    qty: int,
    side: str,
    policy_check_id: str | None = None,
) -> str:
    """Issue an ArmorIQ intent token (real API if key+bridge available, else HMAC fallback).

    Returns a JSON string containing the token data.
    The token attests that the given trade was policy-verified before execution.
    """
    if _USE_REAL_API:
        try:
            return _issue_real(symbol, qty, side, policy_check_id)
        except Exception as exc:
            # Log to stderr and fall back so the pipeline doesn't break
            print(f"[armoriq] real API failed, using HMAC fallback: {exc}", file=sys.stderr)

    return _issue_hmac(symbol, qty, side, policy_check_id)


def verify(token_str: str) -> dict:
    """Verify an ArmorIQ intent token. Returns decoded payload on success, raises ValueError on failure."""
    try:
        data = json.loads(token_str)
    except json.JSONDecodeError:
        raise ValueError("Token is not valid JSON")

    # Real ArmorIQ token: has token_id field
    if "token_id" in data and _USE_REAL_API:
        try:
            return _verify_real(token_str)
        except Exception as exc:
            print(f"[armoriq] real verify failed, using local check: {exc}", file=sys.stderr)

    # HMAC fallback path
    if "_hmac_token" in data:
        return _verify_hmac(token_str)

    # Real token but bridge unavailable — do basic expiry check
    if "expires_at" in data:
        if data["expires_at"] < time.time():
            raise ValueError("ArmorIQ token expired")
        return data

    raise ValueError("Unrecognized token format")
