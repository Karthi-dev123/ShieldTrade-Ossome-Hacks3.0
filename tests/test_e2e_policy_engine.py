"""ShieldTrade E2E Policy Engine Tests — ArmorIQ Integration

End-to-end tests validating the full ArmorIQ-enforced policy pipeline.

ArmorIQ is the zero-trust security backbone of ShieldTrade. It provides:
  - Intent Tokens: Cryptographic proof that each agent action was pre-declared
  - Merkle Proof Verification: Each tool call is checked against the signed plan
  - Fail-Closed Architecture: If verification fails, ALL actions are BLOCKED

This test suite validates the LOCAL policy enforcement layer that feeds into
ArmorIQ's cryptographic verification. The policy engine runs deterministic
checks (no LLM) and reports ALLOW/BLOCK decisions to the ArmorIQ audit trail
via Supabase.

Test categories:
  1. ArmorIQ Delegation Token Lifecycle (issue, validate, expire, reject)
  2. Agent Role Boundaries (ArmorIQ-enforced tool permissions)
  3. Trading Constraints (ticker, size, daily limits)
  4. Data Safety & Network Restrictions
  5. Full E2E Trade Pipeline (ALLOW + BLOCK paths with ArmorIQ audit)
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts import policy_engine


# ─── Fixture: realistic policy matching config/shieldtrade-policies.yaml ──────

@pytest.fixture
def policy():
    """Return a policy dict matching the real YAML structure.

    This policy drives the ArmorIQ enforcement rules:
    - Which agents can invoke which tools
    - Trading limits that ArmorIQ enforces deterministically
    - Delegation requirements (Risk Manager → Trader only)
    """
    return {
        "metadata": {
            "version": "1.0.0",
            "system": "ShieldTrade",
            "enforcement": "deterministic",
        },
        "agent_roles": {
            "analyst": {
                "allowed_tools": ["market_data_fetch", "write_report", "recommend_trade"],
                "denied_tools": ["place_order", "get_account", "shell", "web_fetch"],
            },
            "risk_manager": {
                "allowed_tools": ["read_portfolio", "check_limits", "approve_trade", "reject_trade"],
                "denied_tools": ["place_order", "market_data_fetch", "shell"],
            },
            "trader": {
                "allowed_tools": ["place_order", "get_positions", "get_account"],
                "denied_tools": ["market_data_fetch", "write_report", "shell", "web_fetch"],
            },
        },
        "trading": {
            "approved_tickers": {
                "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
            },
            "order_limits": {
                "per_order_max_usd": 2000,
                "daily_aggregate_max_usd": 1_000_000,
                "per_order_max_shares": 100,
            },
            "time_restrictions": {
                "market_hours_only": {
                    "enabled": True,
                    "start": "09:30",
                    "end": "16:00",
                    "timezone": "America/New_York",
                },
            },
        },
        "data_safety": {
            "no_external_exfiltration": {
                "allowed_domains": ["paper-api.alpaca.markets", "data.alpaca.markets"],
                "blocked_domains": [],
            },
        },
        "delegation": {
            "trader_delegation": {
                "require_risk_approval": True,
                "expiry_minutes": 5,
                "from_agent": "risk_manager",
                "to_agent": "trader",
            },
        },
    }


def _fresh_delegation(ticker="AAPL", max_usd=1000, max_shares=10):
    """Create a valid ArmorIQ delegation token (simulates Risk Manager issuance).

    In production, this token is cryptographically signed by ArmorIQ with:
    - Ed25519 signature binding the token to the issuing agent
    - Plan hash linking back to the approved intent
    - 5-minute TTL enforced server-side
    """
    return {
        "issued_by": "risk_manager",
        "issued_to": "trader",
        "ticker": ticker,
        "max_usd": max_usd,
        "max_shares": max_shares,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "token_id": "tok_test_001",
    }


def _expired_delegation():
    """Create an expired ArmorIQ delegation token (10 minutes old).

    ArmorIQ enforces strict TTL — tokens older than expiry_minutes
    (default: 5 min) are rejected even if structurally valid.
    """
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    return {
        "issued_by": "risk_manager",
        "issued_to": "trader",
        "ticker": "AAPL",
        "max_usd": 1000,
        "max_shares": 10,
        "issued_at": past.isoformat(),
        "token_id": "tok_expired_001",
    }


# ─── ArmorIQ Delegation Token Lifecycle ──────────────────────────────────────

class TestArmorIQDelegationTokens:
    """Tests for ArmorIQ's delegation token system.

    ArmorIQ requires that the Trader agent holds a valid, time-bound
    delegation token issued exclusively by the Risk Manager. This prevents:
    - Unauthorized trade execution (no token = BLOCK)
    - Stale approvals (expired token = BLOCK)
    - Privilege escalation (wrong issuer = BLOCK)
    - Scope creep (token bound to specific ticker/amount)
    """

    def test_valid_token_passes_armoriq_verification(self, policy):
        """A fresh token from risk_manager to trader passes ArmorIQ check."""
        result = policy_engine.check_delegation(_fresh_delegation(), policy)
        assert result["result"] == "PASS"
        assert result["check"] == "delegation"

    def test_empty_token_blocked_by_armoriq(self, policy):
        """ArmorIQ blocks actions with no delegation token."""
        result = policy_engine.check_delegation({}, policy)
        assert result["result"] == "FAIL"
        assert "No delegation token" in result["detail"]

    def test_expired_token_rejected_by_armoriq(self, policy):
        """ArmorIQ enforces TTL — expired tokens are rejected."""
        result = policy_engine.check_delegation(_expired_delegation(), policy)
        assert result["result"] == "FAIL"
        assert "expired" in result["detail"].lower()

    def test_wrong_issuer_rejected_by_armoriq(self, policy):
        """ArmorIQ only accepts tokens issued by risk_manager."""
        token = _fresh_delegation()
        token["issued_by"] = "analyst"  # Analyst cannot issue delegation
        result = policy_engine.check_delegation(token, policy)
        assert result["result"] == "FAIL"
        assert "risk_manager" in result["detail"]

    def test_wrong_target_rejected_by_armoriq(self, policy):
        """ArmorIQ only accepts tokens targeting the trader agent."""
        token = _fresh_delegation()
        token["issued_to"] = "analyst"  # Cannot delegate to analyst
        result = policy_engine.check_delegation(token, policy)
        assert result["result"] == "FAIL"

    def test_missing_fields_rejected_by_armoriq(self, policy):
        """ArmorIQ requires complete token structure — partial tokens fail."""
        result = policy_engine.check_delegation({"issued_by": "risk_manager"}, policy)
        assert result["result"] == "FAIL"
        assert "Missing fields" in result["detail"]


# ─── ArmorIQ Agent Role Enforcement ──────────────────────────────────────────

class TestArmorIQAgentRoles:
    """Tests for ArmorIQ's role-based access control.

    ArmorIQ enforces strict agent boundaries declared in the policy YAML.
    Each agent has explicit allow/deny lists. This prevents:
    - Analyst from placing orders (separation of analysis and execution)
    - Trader from writing reports (can only execute approved trades)
    - Any agent from accessing shell or web_fetch (sandbox escape)
    """

    def test_analyst_allowed_to_write_report(self, policy):
        result = policy_engine.check_role_permission("analyst", "write_report", policy)
        assert result["result"] == "PASS"

    def test_analyst_blocked_from_placing_orders(self, policy):
        """ArmorIQ prevents Analyst from executing trades — separation of concerns."""
        result = policy_engine.check_role_permission("analyst", "place_order", policy)
        assert result["result"] == "FAIL"
        assert "denied" in result["detail"].lower()

    def test_trader_allowed_to_place_order(self, policy):
        result = policy_engine.check_role_permission("trader", "place_order", policy)
        assert result["result"] == "PASS"

    def test_trader_blocked_from_writing_reports(self, policy):
        """ArmorIQ prevents Trader from generating recommendations."""
        result = policy_engine.check_role_permission("trader", "write_report", policy)
        assert result["result"] == "FAIL"

    def test_unknown_agent_blocked_by_armoriq(self, policy):
        """ArmorIQ rejects unregistered agents — zero-trust."""
        result = policy_engine.check_role_permission("hacker", "place_order", policy)
        assert result["result"] == "FAIL"
        assert "Unknown agent" in result["detail"]

    def test_risk_manager_cannot_directly_trade(self, policy):
        """ArmorIQ enforces that Risk Manager can only approve, not execute."""
        result = policy_engine.check_role_permission("risk_manager", "place_order", policy)
        assert result["result"] == "FAIL"


# ─── ArmorIQ Trading Constraint Enforcement ──────────────────────────────────

class TestArmorIQTradingConstraints:
    """Tests for ArmorIQ-enforced trading limits.

    These constraints are declared in the policy YAML and enforced
    deterministically (no LLM interpretation). ArmorIQ logs every
    check result to the Supabase audit trail.
    """

    def test_approved_ticker_passes(self, policy):
        result = policy_engine.check_ticker("AAPL", policy)
        assert result["result"] == "PASS"

    def test_unapproved_ticker_blocked(self, policy):
        """ArmorIQ blocks tickers not in the approved list."""
        result = policy_engine.check_ticker("TSLA", policy)
        assert result["result"] == "FAIL"

    def test_ticker_check_is_case_insensitive(self, policy):
        result = policy_engine.check_ticker("aapl", policy)
        assert result["result"] == "PASS"

    def test_order_within_usd_limit(self, policy):
        result = policy_engine.check_order_size(1500.0, policy)
        assert result["result"] == "PASS"

    def test_order_at_exact_usd_limit(self, policy):
        result = policy_engine.check_order_size(2000.0, policy)
        assert result["result"] == "PASS"

    def test_order_over_usd_limit_blocked(self, policy):
        """ArmorIQ enforces per-order USD cap."""
        result = policy_engine.check_order_size(2500.0, policy)
        assert result["result"] == "FAIL"

    def test_share_count_within_limit(self, policy):
        result = policy_engine.check_share_count(50, policy)
        assert result["result"] == "PASS"

    def test_share_count_over_limit_blocked(self, policy):
        """ArmorIQ enforces per-order share cap."""
        result = policy_engine.check_share_count(150, policy)
        assert result["result"] == "FAIL"

    @patch("scripts.policy_engine._get_today_spend", return_value=0)
    def test_daily_limit_fresh_day(self, mock_spend, policy):
        result = policy_engine.check_daily_limit(1000.0, policy)
        assert result["result"] == "PASS"

    @patch("scripts.policy_engine._get_today_spend", return_value=999_500)
    def test_daily_limit_near_cap(self, mock_spend, policy):
        result = policy_engine.check_daily_limit(500.0, policy)
        assert result["result"] == "PASS"

    @patch("scripts.policy_engine._get_today_spend", return_value=999_500)
    def test_daily_limit_exceeded_blocked(self, mock_spend, policy):
        """ArmorIQ enforces daily aggregate USD cap."""
        result = policy_engine.check_daily_limit(501.0, policy)
        assert result["result"] == "FAIL"


# ─── ArmorIQ Data Safety & Network Restrictions ─────────────────────────────

class TestArmorIQDataSafety:
    """Tests for ArmorIQ network exfiltration prevention.

    ArmorIQ restricts outbound network calls to a strict allowlist.
    Only paper-api.alpaca.markets and data.alpaca.markets are permitted.
    """

    def test_alpaca_paper_api_allowed(self, policy):
        result = policy_engine.check_data_safety("paper-api.alpaca.markets", policy)
        assert result["result"] == "PASS"

    def test_alpaca_data_api_allowed(self, policy):
        result = policy_engine.check_data_safety("data.alpaca.markets", policy)
        assert result["result"] == "PASS"

    def test_unknown_domain_blocked(self, policy):
        """ArmorIQ blocks data exfiltration to unauthorized endpoints."""
        result = policy_engine.check_data_safety("evil.example.com", policy)
        assert result["result"] == "FAIL"


# ─── Full ArmorIQ E2E Trade Pipeline ─────────────────────────────────────────

class TestArmorIQE2ETradePipeline:
    """End-to-end tests through the full ArmorIQ-enforced trade validation.

    These tests exercise the complete validate_trade() pipeline, which:
    1. Checks agent role permissions (ArmorIQ RBAC)
    2. Validates market hours
    3. Checks ticker against approved list
    4. Enforces order size limits
    5. Validates delegation token (ArmorIQ cryptographic check)
    6. Logs decision to Supabase audit trail
    7. Returns ALLOW or BLOCK (fail-closed)
    """

    @patch("scripts.policy_engine.supabase_logger")
    @patch("scripts.policy_engine._record_spend", return_value=1000.0)
    @patch("scripts.policy_engine._get_today_spend", return_value=0)
    def test_full_pipeline_allow(self, mock_spend, mock_record, mock_logger, policy):
        """Happy path: all ArmorIQ checks pass → trade ALLOWED."""
        mock_logger.log.return_value = "audit-uuid-001"
        request = {
            "agent": "trader",
            "tool": "place_order",
            "ticker": "AAPL",
            "shares": 10,
            "amount_usd": 1500.0,
            "domain": "paper-api.alpaca.markets",
            "delegation": _fresh_delegation(),
        }
        result = policy_engine.validate_trade(request, policy)
        assert result["decision"] == "ALLOW"
        assert len(result["blocked_reasons"]) == 0
        assert result["agent"] == "trader"
        # Verify Supabase audit was called
        mock_logger.log.assert_called_once()

    @patch("scripts.policy_engine.supabase_logger")
    @patch("scripts.policy_engine._get_today_spend", return_value=0)
    def test_missing_delegation_blocked_by_armoriq(self, mock_spend, mock_logger, policy):
        """ArmorIQ blocks Trader without a delegation token."""
        mock_logger.log.return_value = "audit-uuid-002"
        request = {
            "agent": "trader",
            "tool": "place_order",
            "ticker": "AAPL",
            "shares": 10,
            "amount_usd": 1000.0,
        }
        result = policy_engine.validate_trade(request, policy)
        assert result["decision"] == "BLOCK"
        assert any("delegation" in r.lower() for r in result["blocked_reasons"])

    @patch("scripts.policy_engine.supabase_logger")
    @patch("scripts.policy_engine._get_today_spend", return_value=0)
    def test_unapproved_ticker_blocked_by_armoriq(self, mock_spend, mock_logger, policy):
        """ArmorIQ blocks trades for tickers outside the approved list."""
        mock_logger.log.return_value = "audit-uuid-003"
        request = {
            "agent": "trader",
            "tool": "place_order",
            "ticker": "TSLA",
            "shares": 10,
            "amount_usd": 500.0,
            "delegation": _fresh_delegation(ticker="TSLA"),
        }
        result = policy_engine.validate_trade(request, policy)
        assert result["decision"] == "BLOCK"
        assert any("TSLA" in r for r in result["blocked_reasons"])

    @patch("scripts.policy_engine.supabase_logger")
    @patch("scripts.policy_engine._get_today_spend", return_value=0)
    def test_oversized_order_blocked_by_armoriq(self, mock_spend, mock_logger, policy):
        """ArmorIQ enforces per-order USD cap at the policy level."""
        mock_logger.log.return_value = "audit-uuid-004"
        request = {
            "agent": "trader",
            "tool": "place_order",
            "ticker": "AAPL",
            "shares": 10,
            "amount_usd": 5000.0,
            "delegation": _fresh_delegation(max_usd=5000),
        }
        result = policy_engine.validate_trade(request, policy)
        assert result["decision"] == "BLOCK"
        assert any("exceeds" in r.lower() for r in result["blocked_reasons"])

    @patch("scripts.policy_engine.supabase_logger")
    @patch("scripts.policy_engine._get_today_spend", return_value=0)
    def test_analyst_trade_attempt_blocked_by_armoriq(self, mock_spend, mock_logger, policy):
        """ArmorIQ enforces role boundaries — Analyst cannot trade."""
        mock_logger.log.return_value = "audit-uuid-005"
        request = {
            "agent": "analyst",
            "tool": "place_order",
            "ticker": "AAPL",
            "shares": 10,
            "amount_usd": 1000.0,
        }
        result = policy_engine.validate_trade(request, policy)
        assert result["decision"] == "BLOCK"

    @patch("scripts.policy_engine.supabase_logger")
    @patch("scripts.policy_engine._get_today_spend", return_value=0)
    def test_expired_delegation_blocked_by_armoriq(self, mock_spend, mock_logger, policy):
        """ArmorIQ rejects expired delegation tokens (TTL enforcement)."""
        mock_logger.log.return_value = "audit-uuid-006"
        request = {
            "agent": "trader",
            "tool": "place_order",
            "ticker": "AAPL",
            "shares": 10,
            "amount_usd": 1000.0,
            "domain": "paper-api.alpaca.markets",
            "delegation": _expired_delegation(),
        }
        result = policy_engine.validate_trade(request, policy)
        assert result["decision"] == "BLOCK"
        assert any("expired" in r.lower() for r in result["blocked_reasons"])

    @patch("scripts.policy_engine.supabase_logger")
    @patch("scripts.policy_engine._record_spend", return_value=1000.0)
    @patch("scripts.policy_engine._get_today_spend", return_value=0)
    def test_armoriq_audit_trail_populated(self, mock_spend, mock_record, mock_logger, policy):
        """Every decision writes to Supabase audit trail via ArmorIQ."""
        mock_logger.log.return_value = "audit-uuid-007"
        request = {
            "agent": "trader",
            "tool": "place_order",
            "ticker": "AAPL",
            "shares": 5,
            "amount_usd": 800.0,
            "domain": "paper-api.alpaca.markets",
            "delegation": _fresh_delegation(),
        }
        result = policy_engine.validate_trade(request, policy)
        assert result["decision"] == "ALLOW"
        # Confirm the policy_check_id links back to the Supabase audit record
        assert result.get("policy_check_id") == "audit-uuid-007"
        # Confirm supabase_logger.log was called with correct table
        call_args = mock_logger.log.call_args
        assert call_args[0][0] == "policy_checks"
