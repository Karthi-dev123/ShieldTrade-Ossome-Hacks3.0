"""ShieldTrade Policy Engine — deterministic enforcement layer.

Reads rules from config/shieldtrade-policies.yaml and enforces them
against trade requests, role checks, and delegation tokens.

All output is valid JSON to stdout. No markdown, no debug prints.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from filelock import FileLock

import supabase_logger

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "config" / "shieldtrade-policies.yaml"
DAILY_SPEND_PATH = ROOT / "output" / "trade-logs" / "daily-spend.json"
DAILY_SPEND_LOCK = ROOT / "output" / "trade-logs" / "daily-spend.json.lock"


def load_policy() -> dict:
    with open(POLICY_PATH, "r") as f:
        return yaml.safe_load(f)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_key() -> str:
    return _utc_now().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# daily-spend.json management (filelock-guarded)
# ---------------------------------------------------------------------------

def _read_daily_spend() -> dict:
    """Read daily spend ledger under file lock."""
    lock = FileLock(str(DAILY_SPEND_LOCK), timeout=5)
    with lock:
        if not DAILY_SPEND_PATH.exists():
            return {}
        with open(DAILY_SPEND_PATH, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}


def _write_daily_spend(data: dict) -> None:
    """Write daily spend ledger under file lock."""
    lock = FileLock(str(DAILY_SPEND_LOCK), timeout=5)
    with lock:
        DAILY_SPEND_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DAILY_SPEND_PATH, "w") as f:
            json.dump(data, f, indent=2)


def _get_today_spend() -> float:
    ledger = _read_daily_spend()
    return ledger.get(_today_key(), 0.0)


def _record_spend(amount: float) -> float:
    """Add amount to today's spend and return new total."""
    lock = FileLock(str(DAILY_SPEND_LOCK), timeout=5)
    with lock:
        if DAILY_SPEND_PATH.exists():
            with open(DAILY_SPEND_PATH, "r") as f:
                try:
                    ledger = json.load(f)
                except json.JSONDecodeError:
                    ledger = {}
        else:
            ledger = {}

        key = _today_key()
        ledger[key] = ledger.get(key, 0.0) + amount

        DAILY_SPEND_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DAILY_SPEND_PATH, "w") as f:
            json.dump(ledger, f, indent=2)

        return ledger[key]


# ---------------------------------------------------------------------------
# validation functions
# ---------------------------------------------------------------------------

def _result(passed: bool, check: str, detail: str) -> dict:
    return {
        "check": check,
        "result": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def check_ticker(ticker: str, policy: dict) -> dict:
    allowed = policy.get("trading", {}).get("allowed_tickers", [])
    if ticker.upper() in allowed:
        return _result(True, "ticker", f"{ticker} is in the allowed list")
    return _result(False, "ticker", f"{ticker} not in allowed list: {allowed}")


def check_order_size(amount_usd: float, policy: dict) -> dict:
    limit = policy.get("trading", {}).get("max_single_order_usd", 0)
    if amount_usd <= limit:
        return _result(True, "order_size", f"${amount_usd:.2f} within single-order limit ${limit}")
    return _result(False, "order_size", f"${amount_usd:.2f} exceeds single-order limit ${limit}")


def check_share_count(shares: int, policy: dict) -> dict:
    limit = policy.get("trading", {}).get("max_position_size", 0)
    if shares <= limit:
        return _result(True, "share_count", f"{shares} shares within position limit {limit}")
    return _result(False, "share_count", f"{shares} shares exceeds position limit {limit}")


def check_daily_limit(amount_usd: float, policy: dict) -> dict:
    limit = policy.get("trading", {}).get("max_daily_spend_usd", 0)
    current = _get_today_spend()
    projected = current + amount_usd
    if projected <= limit:
        return _result(True, "daily_limit", f"Projected ${projected:.2f} within daily limit ${limit}")
    return _result(
        False, "daily_limit",
        f"Projected ${projected:.2f} exceeds daily limit ${limit} (already spent ${current:.2f})"
    )


def check_market_hours(policy: dict) -> dict:
    mh = policy.get("market_hours", {})
    if not mh.get("enabled", False):
        return _result(True, "market_hours", "Market hours check disabled in policy")

    tz_name = mh.get("timezone", "US/Eastern")
    try:
        tz = ZoneInfo(tz_name)
    except KeyError:
        return _result(False, "market_hours", f"Unknown timezone: {tz_name}")

    now = datetime.now(tz)
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    current_minutes = hour * 60 + minute

    if weekday >= 5:
        return _result(False, "market_hours", f"Market closed: weekend ({now.strftime('%A')})")

    market_open = 9 * 60 + 30   # 9:30 AM ET
    market_close = 16 * 60      # 4:00 PM ET

    if market_open <= current_minutes < market_close:
        return _result(True, "market_hours", f"Market open ({now.strftime('%H:%M %Z')})")
    return _result(False, "market_hours", f"Market closed ({now.strftime('%H:%M %Z')})")


def check_role_permission(agent: str, tool: str, policy: dict) -> dict:
    agents_cfg = policy.get("agents", {})
    global_denied = policy.get("global", {}).get("denied_tools", [])

    if tool in global_denied:
        return _result(False, "role_permission", f"Tool '{tool}' is globally denied")

    agent_cfg = agents_cfg.get(agent)
    if agent_cfg is None:
        return _result(False, "role_permission", f"Unknown agent: {agent}")

    denied = agent_cfg.get("denied_tools", [])
    if tool in denied:
        return _result(False, "role_permission", f"Agent '{agent}' is denied tool '{tool}'")

    allowed = agent_cfg.get("allowed_tools", [])
    if tool in allowed:
        return _result(True, "role_permission", f"Agent '{agent}' is allowed tool '{tool}'")

    return _result(False, "role_permission", f"Tool '{tool}' not in '{agent}' allowed list")


def check_delegation(delegation: dict, policy: dict) -> dict:
    """Validate a delegation token structure and constraints.

    Expected delegation dict:
      - issued_by:  agent that issued (must be risk_manager)
      - issued_to:  target agent (must be trader)
      - ticker:     approved ticker
      - max_usd:    spending cap for this delegation
      - max_shares: share cap
      - issued_at:  ISO timestamp of issuance
      - token_id:   unique token identifier
    """
    deleg_cfg = policy.get("delegation", {})

    if not delegation:
        return _result(False, "delegation", "No delegation token provided")

    required_fields = ["issued_by", "issued_to", "ticker", "max_usd", "max_shares", "issued_at", "token_id"]
    missing = [f for f in required_fields if f not in delegation]
    if missing:
        return _result(False, "delegation", f"Missing fields: {missing}")

    if deleg_cfg.get("require_risk_approval", True):
        if delegation["issued_by"] != "risk_manager":
            return _result(False, "delegation", f"Delegation must be issued by risk_manager, got '{delegation['issued_by']}'")

    if delegation["issued_to"] != "trader":
        return _result(False, "delegation", f"Delegation must target trader, got '{delegation['issued_to']}'")

    ttl = deleg_cfg.get("token_ttl_seconds", 300)
    try:
        issued = datetime.fromisoformat(delegation["issued_at"])
        if issued.tzinfo is None:
            issued = issued.replace(tzinfo=timezone.utc)
        age = (_utc_now() - issued).total_seconds()
        if age > ttl:
            return _result(False, "delegation", f"Token expired: age {age:.0f}s exceeds TTL {ttl}s")
        if age < 0:
            return _result(False, "delegation", f"Token issued in the future: {delegation['issued_at']}")
    except (ValueError, TypeError) as e:
        return _result(False, "delegation", f"Invalid issued_at timestamp: {e}")

    return _result(True, "delegation", f"Delegation token {delegation['token_id']} is valid (age {age:.0f}s)")


def check_data_safety(domain: str, policy: dict) -> dict:
    network = policy.get("global", {}).get("network", {})
    blocked = network.get("blocked_domains", [])
    allowed = network.get("allowed_domains", [])

    if domain in blocked:
        return _result(False, "data_safety", f"Domain '{domain}' is blocked")
    if domain in allowed:
        return _result(True, "data_safety", f"Domain '{domain}' is allowed")
    return _result(False, "data_safety", f"Domain '{domain}' not in allowed list")


# ---------------------------------------------------------------------------
# aggregate validator
# ---------------------------------------------------------------------------

def validate_trade(request: dict, policy: dict) -> dict:
    """Run all checks against a trade request.

    Expected request dict:
      - agent:      requesting agent id
      - tool:       tool being invoked
      - ticker:     stock symbol
      - shares:     number of shares
      - amount_usd: dollar value of the order
      - domain:     target API domain
      - delegation: delegation token dict (optional, required for trader)
    """
    checks = []

    agent = request.get("agent", "unknown")
    tool = request.get("tool", "unknown")
    ticker = request.get("ticker", "")
    shares = request.get("shares", 0)
    amount = request.get("amount_usd", 0.0)
    domain = request.get("domain", "")
    delegation = request.get("delegation")

    checks.append(check_role_permission(agent, tool, policy))
    checks.append(check_market_hours(policy))

    if ticker:
        checks.append(check_ticker(ticker, policy))
    if shares > 0:
        checks.append(check_share_count(shares, policy))
    if amount > 0:
        checks.append(check_order_size(amount, policy))
        checks.append(check_daily_limit(amount, policy))
    if domain:
        checks.append(check_data_safety(domain, policy))
    if delegation is not None:
        checks.append(check_delegation(delegation, policy))
    elif agent == "trader" and tool == "place_order":
        checks.append(_result(False, "delegation", "Trader must provide delegation token for place_order"))

    failed = [c for c in checks if c["result"] == "FAIL"]
    decision = "BLOCK" if failed else "ALLOW"

    if decision == "ALLOW" and amount > 0:
        _record_spend(amount)

    result = {
        "decision": decision,
        "timestamp": _utc_now().isoformat(),
        "agent": agent,
        "tool": tool,
        "ticker": ticker,
        "checks": checks,
        "blocked_reasons": [c["detail"] for c in failed] if failed else [],
    }

    row_id = supabase_logger.log("policy_checks", {
        "decision": result["decision"],
        "agent": result["agent"],
        "tool": result["tool"],
        "ticker": result["ticker"],
        "checks": result["checks"],
        "blocked_reasons": result["blocked_reasons"],
        "timestamp": result["timestamp"],
    })

    # Expose the audit row id so callers can link trade_events back to this check.
    result["policy_check_id"] = row_id
    return result


# ---------------------------------------------------------------------------
# CLI dispatcher
# ---------------------------------------------------------------------------

def _print_json(obj: dict) -> None:
    print(json.dumps(obj, indent=2))


def _cli_check_trade(args: list[str]) -> None:
    """check-trade <agent> <tool> <ticker> <shares> <amount_usd> [domain]"""
    if len(args) < 5:
        _print_json({"error": "Usage: check-trade <agent> <tool> <ticker> <shares> <amount_usd> [domain]"})
        sys.exit(1)

    policy = load_policy()
    request = {
        "agent": args[0],
        "tool": args[1],
        "ticker": args[2],
        "shares": int(args[3]),
        "amount_usd": float(args[4]),
        "domain": args[5] if len(args) > 5 else "paper-api.alpaca.markets",
    }
    _print_json(validate_trade(request, policy))


def _cli_check_role(args: list[str]) -> None:
    """check-role <agent> <tool>"""
    if len(args) < 2:
        _print_json({"error": "Usage: check-role <agent> <tool>"})
        sys.exit(1)

    policy = load_policy()
    _print_json(check_role_permission(args[0], args[1], policy))


def _cli_check_delegation(args: list[str]) -> None:
    """check-delegation <json_string>"""
    if len(args) < 1:
        _print_json({"error": "Usage: check-delegation '<json_string>'"})
        sys.exit(1)

    policy = load_policy()
    try:
        delegation = json.loads(args[0])
    except json.JSONDecodeError as e:
        _print_json({"error": f"Invalid JSON: {e}"})
        sys.exit(1)

    _print_json(check_delegation(delegation, policy))


def _cli_validate_all(args: list[str]) -> None:
    """validate-all <json_string>

    Accepts a full trade request as JSON, runs all checks.
    """
    if len(args) < 1:
        _print_json({"error": "Usage: validate-all '<json_request_json>'"})
        sys.exit(1)

    policy = load_policy()
    try:
        request = json.loads(args[0])
    except json.JSONDecodeError as e:
        _print_json({"error": f"Invalid JSON: {e}"})
        sys.exit(1)

    _print_json(validate_trade(request, policy))


COMMANDS = {
    "check-trade": _cli_check_trade,
    "check-role": _cli_check_role,
    "check-delegation": _cli_check_delegation,
    "validate-all": _cli_validate_all,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        _print_json({
            "error": "Unknown command",
            "usage": {cmd: fn.__doc__.strip() for cmd, fn in COMMANDS.items()},
        })
        sys.exit(1)

    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
