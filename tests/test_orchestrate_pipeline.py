"""Integration-style tests for scripts/orchestrate_pipeline.py."""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import orchestrate_pipeline as orch  # noqa: E402


@pytest.fixture
def orch_policy():
    return {
        "trading": {
            "order_limits": {
                "per_order_max_usd": 2500,
                "daily_aggregate_max_usd": 10000,
                "per_order_max_shares": 100,
            },
            "approved_tickers": {"symbols": ["AAPL", "MSFT"]},
            "time_restrictions": {"market_hours_only": {"enabled": False}},
        },
        "data_safety": {
            "no_external_exfiltration": {
                "allowed_domains": ["paper-api.alpaca.markets"],
                "blocked_domains": [],
            }
        },
        "delegation": {"trader_delegation": {"expiry_minutes": 30}},
        "agent_roles": {
            "risk_manager": {
                "allowed_tools": ["approve_trade"],
                "denied_tools": [],
            },
            "trader": {
                "allowed_tools": ["place_order"],
                "denied_tools": [],
            },
        },
    }


@pytest.fixture
def isolated_output_dirs(tmp_path, monkeypatch):
    root = tmp_path
    monkeypatch.setattr(orch, "ROOT", root)
    monkeypatch.setattr(orch, "REPORTS_DIR", root / "output" / "reports")
    monkeypatch.setattr(orch, "RISK_DIR", root / "output" / "risk-decisions")
    monkeypatch.setattr(orch, "TRADE_LOGS_DIR", root / "output" / "trade-logs")
    return root


def test_dry_run_pipeline_writes_artifacts(isolated_output_dirs, orch_policy):
    out = orch.run_pipeline(
        "AAPL",
        5,
        "buy",
        assume_price=100.0,
        dry_run=True,
        skip_analyst=False,
        policy=orch_policy,
    )
    assert out["ok"] is True
    assert out["dry_run"] is True
    root = isolated_output_dirs
    assert (root / out["report_path"]).exists()
    assert (root / out["delegation_path"]).exists()
    exec_p = root / out["execution_log_path"]
    assert exec_p.exists()
    body = json.loads(exec_p.read_text())
    assert body.get("dry_run") is True
    assert body["order"]["status"] == "dry_run"
    with open(root / out["delegation_path"]) as f:
        del_body = json.load(f)
    assert del_body["issued_by"] == "risk_manager"
    assert del_body["max_shares"] == 5


def test_risk_blocks_disallowed_ticker(isolated_output_dirs, orch_policy):
    orch_policy["trading"]["approved_tickers"]["symbols"] = ["MSFT"]
    out = orch.run_pipeline(
        "AAPL",
        2,
        "buy",
        assume_price=50.0,
        dry_run=True,
        skip_analyst=False,
        policy=orch_policy,
    )
    assert out["ok"] is False
    assert out["stopped_at"] == "risk"
    root = isolated_output_dirs
    assert (root / out["rejection_path"]).exists()


def test_oversized_order_blocked(isolated_output_dirs, orch_policy):
    """Risk stage blocks when order notional exceeds per_order_max_usd."""
    orch_policy["trading"]["order_limits"]["per_order_max_usd"] = 200
    # 5 shares @ $100 = $500 > $200 cap → risk stage BLOCK
    out = orch.run_pipeline(
        "AAPL",
        5,
        "buy",
        assume_price=100.0,
        dry_run=True,
        skip_analyst=False,
        policy=orch_policy,
    )
    assert out["ok"] is False
    assert out["stopped_at"] == "risk"
    root = isolated_output_dirs
    assert (root / out["rejection_path"]).exists()
    rej = json.loads((root / out["rejection_path"]).read_text())
    assert rej["decision"] == "BLOCK"
    assert any("order_size" in str(r) or "$500" in str(r) or "500" in str(r) for r in rej["blocked_reasons"])


def test_expired_delegation_blocked(isolated_output_dirs, orch_policy):
    """Trader stage blocks when delegation token is expired."""
    orch_policy["delegation"]["trader_delegation"]["expiry_minutes"] = 1
    expired_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

    original_build = orch.build_delegation

    def build_with_expired_token(*args, **kwargs):
        tok = original_build(*args, **kwargs)
        tok["issued_at"] = expired_at
        return tok

    with patch("scripts.orchestrate_pipeline.build_delegation", side_effect=build_with_expired_token):
        out = orch.run_pipeline(
            "AAPL",
            5,
            "buy",
            assume_price=100.0,
            dry_run=True,
            skip_analyst=False,
            policy=orch_policy,
        )
    assert out["ok"] is False
    assert out["stopped_at"] == "trader_delegation"
    root = isolated_output_dirs
    assert (root / out["rejection_path"]).exists()
    rej = json.loads((root / out["rejection_path"]).read_text())
    assert rej["decision"] == "BLOCK"
    assert any("expired" in r.lower() for r in rej["blocked_reasons"])


def test_quantity_exceeds_delegation_blocked(isolated_output_dirs, orch_policy):
    """Trader stage blocks when requested shares exceed delegation max_shares cap."""
    original_build = orch.build_delegation

    def build_with_capped_shares(*args, **kwargs):
        tok = original_build(*args, **kwargs)
        tok["max_shares"] = 3  # cap lower than requested 5
        return tok

    with patch("scripts.orchestrate_pipeline.build_delegation", side_effect=build_with_capped_shares):
        out = orch.run_pipeline(
            "AAPL",
            5,
            "buy",
            assume_price=100.0,
            dry_run=True,
            skip_analyst=False,
            policy=orch_policy,
        )
    assert out["ok"] is False
    assert out["stopped_at"] == "trader_caps"
    root = isolated_output_dirs
    assert (root / out["rejection_path"]).exists()
    rej = json.loads((root / out["rejection_path"]).read_text())
    assert rej["decision"] == "BLOCK"
    assert any("5" in r and "3" in r for r in rej["blocked_reasons"])


def test_no_delegation_token_blocked(isolated_output_dirs, orch_policy):
    """Trader stage blocks when delegation is structurally invalid (required fields missing)."""
    # Must include token_id so the orchestrator can construct the file path,
    # but omit the required issued_by/issued_to/ticker/max_usd/max_shares/issued_at
    # so check_delegation fails with "Missing fields".
    with patch("scripts.orchestrate_pipeline.build_delegation", return_value={"token_id": "del_stub_no_fields"}):
        out = orch.run_pipeline(
            "AAPL",
            5,
            "buy",
            assume_price=100.0,
            dry_run=True,
            skip_analyst=False,
            policy=orch_policy,
        )
    assert out["ok"] is False
    assert out["stopped_at"] == "trader_delegation"
    root = isolated_output_dirs
    assert (root / out["rejection_path"]).exists()
    rej = json.loads((root / out["rejection_path"]).read_text())
    assert rej["decision"] == "BLOCK"
    assert any("Missing fields" in r or "delegation" in r.lower() for r in rej["blocked_reasons"])


def test_build_delegation_caps_to_yaml_ceiling(orch_policy):
    """build_delegation respects max_shares_per_delegation / max_usd_per_delegation from YAML."""
    orch_policy["delegation"]["trader_delegation"]["max_shares_per_delegation"] = 3
    orch_policy["delegation"]["trader_delegation"]["max_usd_per_delegation"] = 200.0
    delegation = orch.build_delegation(
        "AAPL",
        max_shares=10,
        max_usd=1000.0,
        side="buy",
        recommendation_path="output/reports/AAPL-recommendation.json",
        policy=orch_policy,
    )
    assert delegation["max_shares"] == 3
    assert delegation["max_usd"] == 200.0


def test_build_delegation_no_policy_uncapped():
    """build_delegation without a policy passes values through unchanged."""
    delegation = orch.build_delegation(
        "AAPL",
        max_shares=50,
        max_usd=5000.0,
        side="buy",
        recommendation_path="output/reports/AAPL-recommendation.json",
        policy=None,
    )
    assert delegation["max_shares"] == 50
    assert delegation["max_usd"] == 5000.0


@patch("scripts.orchestrate_pipeline.alpaca_bridge.cmd_order")
def test_live_submits_order_when_not_dry_run(
    mock_order, isolated_output_dirs, orch_policy
):
    mock_order.return_value = {
        "order_id": "test-order-1",
        "symbol": "AAPL",
        "qty": "3",
        "side": "buy",
        "type": "market",
        "status": "accepted",
        "submitted_at": "2026-04-04T00:00:00+00:00",
        "time_in_force": "day",
    }
    with patch("scripts.orchestrate_pipeline.policy_engine._record_spend") as mock_spend:
        out = orch.run_pipeline(
            "AAPL",
            3,
            "buy",
            assume_price=90.0,
            dry_run=False,
            skip_analyst=False,
            policy=orch_policy,
        )
    assert out["ok"] is True
    assert out.get("dry_run") is False
    mock_order.assert_called_once()
    mock_spend.assert_called()
    root = isolated_output_dirs
    body = json.loads((root / out["execution_log_path"]).read_text())
    assert body["order"]["order_id"] == "test-order-1"
    assert "dry_run" not in body or body.get("dry_run") is not True
