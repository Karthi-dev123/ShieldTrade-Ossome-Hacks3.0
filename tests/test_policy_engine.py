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
        "global": {
            "denied_tools": ["shell"],
            "network": {
                "allowed_domains": ["paper-api.alpaca.markets"],
                "blocked_domains": ["api.alpaca.markets"]
            }
        },
        "market_hours": {"enabled": False},
        "trading": {
            "allowed_tickers": ["AAPL", "MSFT"],
            "max_position_size": 100,
            "max_daily_spend_usd": 10000,
            "max_single_order_usd": 2500
        },
        "delegation": {
            "token_ttl_seconds": 300,
            "require_risk_approval": True,
            "max_concurrent_tokens": 3
        },
        "agents": {
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