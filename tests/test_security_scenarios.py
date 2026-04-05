"""Security scenario tests — prompt injection, data exfiltration, scope escalation.

These tests correspond directly to the PS judging criteria:
  - Enforcement Strength: violations deterministically blocked without human intervention
  - Use Case Depth: genuine risks (unauthorized trades, data exfiltration, scope escalation)

Each test represents a realistic attack vector documented by Microsoft/Cisco in the PS context.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import policy_engine


@pytest.fixture
def policy():
    """Minimal policy fixture with all security-relevant sections enabled."""
    return {
        "agent_roles": {
            "analyst": {
                "allowed_tools": ["market_data_fetch", "write_report", "recommend_trade"],
                "denied_tools": ["place_order", "shell", "web_fetch"],
            },
            "trader": {
                "allowed_tools": ["place_order", "get_positions", "get_account"],
                "denied_tools": ["market_data_fetch", "write_report", "shell", "web_fetch"],
            },
        },
        "trading": {
            "order_limits": {
                "per_order_max_usd": 2000,
                "daily_aggregate_max_usd": 10000,
                "per_order_max_shares": 100,
            },
            "approved_tickers": {"symbols": ["AAPL", "MSFT"]},
            "time_restrictions": {"market_hours_only": {"enabled": False}},
        },
        "data_safety": {
            "no_pii_in_tool_args": {
                "patterns": [
                    r"\d{3}-\d{2}-\d{4}",   # SSN
                    r"\d{16}",               # Credit card
                    r"\d{9}",               # 9-digit account number
                ]
            },
            "no_external_exfiltration": {
                "allowed_domains": ["paper-api.alpaca.markets", "data.alpaca.markets"],
                "blocked_domains": [],
            },
        },
        "delegation": {"trader_delegation": {"expiry_minutes": 5}},
    }


# ---------------------------------------------------------------------------
# Scenario 1: Prompt injection → denied tool call
# An injected prompt inside market data tells the analyst agent to execute
# a shell command. The role check blocks this regardless of LLM output.
# ---------------------------------------------------------------------------

def test_prompt_injection_shell_call_blocked(policy):
    """Analyst calling 'shell' is unconditionally denied."""
    result = policy_engine.check_role_permission("analyst", "shell", policy)
    assert result["result"] == "FAIL"
    assert "denied" in result["detail"].lower()


# ---------------------------------------------------------------------------
# Scenario 2: Cross-agent scope escalation
# A trader agent (after potential compromise) tries to write a research
# report — a tool reserved for the analyst. The role check blocks this.
# ---------------------------------------------------------------------------

def test_cross_agent_scope_escalation_blocked(policy):
    """Trader calling 'write_report' is denied — analyst-only tool."""
    result = policy_engine.check_role_permission("trader", "write_report", policy)
    assert result["result"] == "FAIL"
    assert "denied" in result["detail"].lower()


# ---------------------------------------------------------------------------
# Scenario 3: Data exfiltration via live trading API
# An injected prompt re-routes the paper order to api.alpaca.markets (the
# real money endpoint). The data_safety check catches this — only
# paper-api.alpaca.markets is in the allow-list.
# ---------------------------------------------------------------------------

def test_data_exfiltration_live_api_blocked(policy):
    """Order routed to live Alpaca API is blocked by data_safety domain check."""
    result = policy_engine.check_data_safety("api.alpaca.markets", policy)
    assert result["result"] == "FAIL"
    assert "api.alpaca.markets" in result["detail"]


def test_data_exfiltration_unknown_host_blocked(policy):
    """Order routed to an unknown external host is blocked (fail-closed)."""
    result = policy_engine.check_data_safety("attacker-exfil.example.com", policy)
    assert result["result"] == "FAIL"
    assert "not in allowed list" in result["detail"]


# ---------------------------------------------------------------------------
# Scenario 4: PII injection in tool arguments
# A malicious market-data feed embeds an SSN into the analyst's query.
# The pii_in_tool_args check intercepts this before the tool is invoked.
# ---------------------------------------------------------------------------

def test_pii_ssn_in_tool_args_blocked(policy):
    """SSN pattern in tool_args is caught by PII check."""
    result = policy_engine.check_pii_in_tool_args(
        "Fetch earnings for account holder 123-45-6789", policy
    )
    assert result["result"] == "FAIL"
    assert "PII detected" in result["detail"]


def test_pii_credit_card_in_tool_args_blocked(policy):
    """16-digit credit card number in tool_args is blocked."""
    result = policy_engine.check_pii_in_tool_args(
        "Authorize payment for card 4532015112830366", policy
    )
    assert result["result"] == "FAIL"
    assert "PII detected" in result["detail"]


def test_clean_tool_args_pass(policy):
    """Legitimate query with no PII passes the check."""
    result = policy_engine.check_pii_in_tool_args(
        "Fetch 30-day price bars for AAPL", policy
    )
    assert result["result"] == "PASS"


# ---------------------------------------------------------------------------
# Scenario 5: Full validate_trade with injected domain (end-to-end)
# Shows that validate_trade catches the exfiltration attempt even when the
# request looks otherwise valid (correct agent, tool, ticker, size).
# ---------------------------------------------------------------------------

def test_validate_trade_blocks_exfiltration_domain(policy):
    """validate_trade blocks a trader request routed to the live API."""
    request = {
        "agent": "trader",
        "tool": "place_order",
        "ticker": "AAPL",
        "shares": 5,
        "amount_usd": 500.0,
        "domain": "api.alpaca.markets",  # live API — not allowed
    }
    result = policy_engine.validate_trade(request, policy, record_spend_if_allow=False)
    assert result["decision"] == "BLOCK"
    data_safety_check = next(
        (c for c in result["checks"] if c["check"] == "data_safety"), None
    )
    assert data_safety_check is not None
    assert data_safety_check["result"] == "FAIL"


# ---------------------------------------------------------------------------
# Scenario 6: Full validate_trade with PII-injected tool_args (end-to-end)
# ---------------------------------------------------------------------------

def test_validate_trade_blocks_pii_in_tool_args(policy):
    """validate_trade blocks a request whose tool_args contain an SSN."""
    request = {
        "agent": "analyst",
        "tool": "market_data_fetch",
        "ticker": "AAPL",
        "shares": 0,
        "amount_usd": 0.0,
        "domain": "data.alpaca.markets",
        "tool_args": "Summarize portfolio for SSN 123-45-6789",
    }
    result = policy_engine.validate_trade(request, policy, record_spend_if_allow=False)
    assert result["decision"] == "BLOCK"
    pii_check = next(
        (c for c in result["checks"] if c["check"] == "pii_in_tool_args"), None
    )
    assert pii_check is not None
    assert pii_check["result"] == "FAIL"
