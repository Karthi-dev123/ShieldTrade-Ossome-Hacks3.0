import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
import os

# Add scripts directory to path to import policy_engine
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import policy_engine

@pytest.fixture
def mock_policy():
    return {
        "trading": {
            "order_limits": {
                "per_order_max_usd": 2500,
                "daily_aggregate_max_usd": 10000,
                "per_order_max_shares": 100
            },
            "approved_tickers": {"symbols": ["AAPL", "MSFT"]},
            "time_restrictions": {
                "market_hours_only": {"enabled": False}
            }
        },
        "data_safety": {
            "no_external_exfiltration": {
                "allowed_domains": ["paper-api.alpaca.markets"],
                "blocked_domains": ["api.alpaca.markets"]
            }
        },
        "delegation": {
            "trader_delegation": {
                "expiry_minutes": 5
            }
        },
        "agent_roles": {
            "trader": {
                "allowed_tools": ["place_order"],
                "denied_tools": ["shell"]
            }
        }
    }

def test_check_ticker_allowed(mock_policy):
    res = policy_engine.check_ticker("AAPL", mock_policy)
    assert res["result"] == "PASS"

def test_check_ticker_blocked(mock_policy):
    res = policy_engine.check_ticker("TSLA", mock_policy)
    assert res["result"] == "FAIL"
    assert "not in allowed list" in res["detail"]

def test_check_order_size_allowed(mock_policy):
    res = policy_engine.check_order_size(2000, mock_policy)
    assert res["result"] == "PASS"

def test_check_order_size_blocked(mock_policy):
    res = policy_engine.check_order_size(3000, mock_policy)
    assert res["result"] == "FAIL"

@patch('scripts.policy_engine._get_today_spend', return_value=8000)
def test_check_daily_limit_allowed(mock_get_spend, mock_policy):
    res = policy_engine.check_daily_limit(1500, mock_policy)
    assert res["result"] == "PASS"

@patch('scripts.policy_engine._get_today_spend', return_value=8000)
def test_check_daily_limit_blocked(mock_get_spend, mock_policy):
    res = policy_engine.check_daily_limit(2500, mock_policy)
    assert res["result"] == "FAIL"

def test_check_delegation_missing(mock_policy):
    res = policy_engine.check_delegation({}, mock_policy)
    assert res["result"] == "FAIL"
    assert "No delegation token" in res["detail"]

def test_check_delegation_expired(mock_policy):
    past_time = (datetime.now(timezone.utc) - timedelta(seconds=400)).isoformat()
    delegation = {
        "issued_by": "risk_manager",
        "issued_to": "trader",
        "ticker": "AAPL",
        "max_usd": 1000,
        "max_shares": 10,
        "issued_at": past_time,
        "token_id": "tok_123"
    }
    res = policy_engine.check_delegation(delegation, mock_policy)
    assert res["result"] == "FAIL"
    assert "expired" in res["detail"]

@patch('scripts.policy_engine._record_spend')
@patch('scripts.policy_engine._get_today_spend', return_value=0)
def test_validate_trade_allow_without_recording_spend(mock_get_spend, mock_rec_spend, mock_policy):
    delegation = {
        "issued_by": "risk_manager",
        "issued_to": "trader",
        "ticker": "AAPL",
        "max_usd": 2500,
        "max_shares": 10,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "token_id": "tok_x",
    }
    request = {
        "agent": "trader",
        "tool": "place_order",
        "ticker": "AAPL",
        "shares": 5,
        "amount_usd": 500.0,
        "domain": "paper-api.alpaca.markets",
        "delegation": delegation,
    }
    mock_policy.setdefault("agent_roles", {})["trader"] = {
        "allowed_tools": ["place_order"],
        "denied_tools": [],
    }
    res = policy_engine.validate_trade(request, mock_policy, record_spend_if_allow=False)
    assert res["decision"] == "ALLOW"
    mock_rec_spend.assert_not_called()


@patch('scripts.policy_engine._record_spend')
@patch('scripts.policy_engine._get_today_spend', return_value=0)
def test_validate_trade_no_token_blocked(mock_get_spend, mock_rec_spend, mock_policy):
    request = {
        "agent": "trader",
        "tool": "place_order",
        "ticker": "AAPL",
        "amount_usd": 1000
    }
    res = policy_engine.validate_trade(request, mock_policy)
    assert res["decision"] == "BLOCK"
    assert any("Trader must provide delegation token" in r for r in res["blocked_reasons"])


def _valid_delegation(max_shares=10, max_usd=1000.0):
    return {
        "issued_by": "risk_manager",
        "issued_to": "trader",
        "ticker": "AAPL",
        "max_usd": max_usd,
        "max_shares": max_shares,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "token_id": "tok_cap_test",
    }


def test_check_delegation_exceeds_max_shares(mock_policy):
    delegation = _valid_delegation(max_shares=5)
    res = policy_engine.check_delegation(delegation, mock_policy, shares=10)
    assert res["result"] == "FAIL"
    assert "exceeds delegation cap" in res["detail"]
    assert "10 shares" in res["detail"]


def test_check_delegation_exceeds_max_usd(mock_policy):
    delegation = _valid_delegation(max_usd=500.0)
    res = policy_engine.check_delegation(delegation, mock_policy, amount_usd=600.0)
    assert res["result"] == "FAIL"
    assert "exceeds delegation cap" in res["detail"]
    assert "$600.00" in res["detail"]


def test_check_delegation_within_caps(mock_policy):
    delegation = _valid_delegation(max_shares=10, max_usd=1000.0)
    res = policy_engine.check_delegation(delegation, mock_policy, shares=5, amount_usd=500.0)
    assert res["result"] == "PASS"


# ---------------------------------------------------------------------------
# Step 1 — delegation YAML ceiling tests
# ---------------------------------------------------------------------------

def test_check_delegation_exceeds_yaml_ceiling_shares(mock_policy):
    """Token max_shares above the policy ceiling is rejected."""
    mock_policy["delegation"]["trader_delegation"]["max_shares_per_delegation"] = 50
    delegation = _valid_delegation(max_shares=100)
    res = policy_engine.check_delegation(delegation, mock_policy)
    assert res["result"] == "FAIL"
    assert "exceeds policy ceiling" in res["detail"]
    assert "50" in res["detail"]


def test_check_delegation_exceeds_yaml_ceiling_usd(mock_policy):
    """Token max_usd above the policy ceiling is rejected."""
    mock_policy["delegation"]["trader_delegation"]["max_usd_per_delegation"] = 500
    delegation = _valid_delegation(max_usd=1500.0)
    res = policy_engine.check_delegation(delegation, mock_policy)
    assert res["result"] == "FAIL"
    assert "exceeds policy ceiling" in res["detail"]
    assert "500" in res["detail"]


def test_check_delegation_at_yaml_ceiling_passes(mock_policy):
    """Token exactly at the policy ceiling is accepted."""
    mock_policy["delegation"]["trader_delegation"]["max_shares_per_delegation"] = 10
    mock_policy["delegation"]["trader_delegation"]["max_usd_per_delegation"] = 1000.0
    delegation = _valid_delegation(max_shares=10, max_usd=1000.0)
    res = policy_engine.check_delegation(delegation, mock_policy)
    assert res["result"] == "PASS"


# ---------------------------------------------------------------------------
# Step 3 — earnings blackout tests
# ---------------------------------------------------------------------------

def test_earnings_blackout_disabled(mock_policy):
    mock_policy["trading"]["time_restrictions"]["earnings_blackout"] = {"enabled": False}
    res = policy_engine.check_earnings_blackout("AAPL", mock_policy)
    assert res["result"] == "PASS"
    assert "disabled" in res["detail"]


def test_earnings_blackout_no_event_for_ticker(mock_policy):
    mock_policy["trading"]["time_restrictions"]["earnings_blackout"] = {
        "enabled": True,
        "window_before_minutes": 30,
        "window_after_minutes": 30,
        "events": [{"ticker": "MSFT", "date": "2026-12-31T17:00:00-05:00"}],
    }
    res = policy_engine.check_earnings_blackout("AAPL", mock_policy)
    assert res["result"] == "PASS"


def test_earnings_blackout_in_window(mock_policy):
    """Blackout window is active when now falls between window_start and window_end."""
    from datetime import datetime, timezone
    event_time = datetime.now(timezone.utc).isoformat()
    mock_policy["trading"]["time_restrictions"]["earnings_blackout"] = {
        "enabled": True,
        "window_before_minutes": 60,
        "window_after_minutes": 60,
        "events": [{"ticker": "AAPL", "date": event_time}],
    }
    res = policy_engine.check_earnings_blackout("AAPL", mock_policy)
    assert res["result"] == "FAIL"
    assert "blackout" in res["detail"].lower()


def test_earnings_blackout_outside_window(mock_policy):
    mock_policy["trading"]["time_restrictions"]["earnings_blackout"] = {
        "enabled": True,
        "window_before_minutes": 30,
        "window_after_minutes": 30,
        "events": [{"ticker": "AAPL", "date": "2026-12-31T17:00:00-05:00"}],
    }
    res = policy_engine.check_earnings_blackout("AAPL", mock_policy)
    assert res["result"] == "PASS"


def test_earnings_blackout_missing_events_fails_closed(mock_policy):
    """Missing events list → fail-closed when blackout is enabled."""
    mock_policy["trading"]["time_restrictions"]["earnings_blackout"] = {
        "enabled": True,
        "window_before_minutes": 30,
        "window_after_minutes": 30,
        # no "events" key
    }
    res = policy_engine.check_earnings_blackout("AAPL", mock_policy)
    assert res["result"] == "FAIL"
    assert "fail-closed" in res["detail"].lower()


# ---------------------------------------------------------------------------
# Step 4 — daily-spend timezone test
# ---------------------------------------------------------------------------

def test_today_key_uses_eastern_timezone():
    """_today_key() must match today's date in ET, not UTC."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    et_today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    assert policy_engine._today_key() == et_today