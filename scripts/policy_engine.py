"""ShieldTrade Policy Engine — deterministic enforcement layer.

Reads rules from config/shieldtrade-policies.yaml and enforces them
against trade requests, role checks, and delegation tokens.

## Structured Models

The engine exposes two families of Pydantic models that satisfy the
hackathon requirement for "structured, interpretable intent and policy
representations" — not simple if-else checks:

  Intent models  (what an agent wants to do)
    TradeIntent      — the full intent of a trade request
    DelegationToken  — scoped authority token issued by risk_manager

  Policy schema models  (declarative rules loaded from YAML)
    ShieldTradePolicy  — top-level policy document
    TradingPolicy, OrderLimits, ApprovedTickers, ...

load_policy() validates the YAML file against ShieldTradePolicy at
startup, raising Pydantic ValidationError if the config is malformed.
validate_trade() coerces incoming request dicts into TradeIntent before
running checks so that every enforcement decision is grounded in a
typed, schema-validated intent object.

All output is valid JSON to stdout. No markdown, no debug prints.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import yaml
from filelock import FileLock
from pydantic import BaseModel, Field

# Auto-load .env so scripts work without manually sourcing it in the shell.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import supabase_logger


# ===========================================================================
# Intent Models — "what an agent wants to do"
# ===========================================================================

class DelegationToken(BaseModel):
    """Scoped authority token that risk_manager issues to trader.

    Every field is required so the engine can deterministically validate
    issuer, target, ticker scope, spending caps, and TTL expiry.
    """
    issued_by: str
    issued_to: str
    ticker: str
    max_usd: float
    max_shares: int
    issued_at: str  # ISO 8601 timestamp
    token_id: str
    # Optional audit / traceability fields
    side: Optional[str] = None
    recommendation_path: Optional[str] = None
    policy_snapshot_version: Optional[str] = None


class TradeIntent(BaseModel):
    """Structured intent model for a single trade request.

    Captures WHO is acting (agent), WHAT they want to do (tool + ticker +
    size), WHERE the request targets (domain), UNDER WHAT AUTHORITY they
    act (delegation), and WHAT ARGUMENTS they pass to the tool (tool_args).

    tool_args is checked for PII patterns (SSN, credit-card numbers,
    account numbers) declared in data_safety.no_pii_in_tool_args.patterns.
    A prompt-injected payload that smuggles account data into a market-data
    query is caught here before the tool call is allowed.
    """
    agent: str
    tool: str
    ticker: str = ""
    shares: int = 0
    amount_usd: float = 0.0
    domain: str = "paper-api.alpaca.markets"
    delegation: Optional[DelegationToken] = None
    tool_args: Optional[str] = None  # Free-form arguments; checked for PII


# ===========================================================================
# Policy Schema Models — declarative rules loaded from YAML
# ===========================================================================

class AgentRole(BaseModel):
    description: str = ""
    allowed_tools: List[str] = []
    denied_tools: List[str] = []
    requires_delegation: bool = False
    file_access: Dict[str, List[str]] = {}


class OrderLimits(BaseModel):
    per_order_max_usd: float
    daily_aggregate_max_usd: float
    per_order_max_shares: int
    enforcement: str = "block_and_log"


class ApprovedTickers(BaseModel):
    symbols: List[str]
    enforcement: str = "block_and_log"


class MarketHoursRestriction(BaseModel):
    enabled: bool = False
    start: str = "09:30"
    end: str = "16:00"
    timezone: str = "America/New_York"
    enforcement: str = "block_and_log"


class EarningsEvent(BaseModel):
    ticker: str
    date: str
    description: str = ""


class EarningsBlackout(BaseModel):
    enabled: bool = False
    window_before_minutes: int = 30
    window_after_minutes: int = 30
    enforcement: str = "block_and_log"
    events: List[EarningsEvent] = []


class TimeRestrictions(BaseModel):
    market_hours_only: MarketHoursRestriction = Field(default_factory=MarketHoursRestriction)
    earnings_blackout: EarningsBlackout = Field(default_factory=EarningsBlackout)


class PortfolioLimits(BaseModel):
    max_single_position_pct: float = 30.0
    min_cash_reserve_pct: float = 10.0
    enforcement: str = "block_and_log"


class TradingPolicy(BaseModel):
    order_limits: OrderLimits
    approved_tickers: ApprovedTickers
    time_restrictions: TimeRestrictions = Field(default_factory=TimeRestrictions)
    portfolio_limits: Optional[PortfolioLimits] = None


class TraderDelegationPolicy(BaseModel):
    required: bool = True
    max_shares_per_delegation: Optional[int] = None
    max_usd_per_delegation: Optional[float] = None
    expiry_minutes: int = 5
    must_match_recommendation: bool = True
    no_sub_delegation: bool = True
    from_agent: str = "risk_manager"
    to_agent: str = "trader"
    require_risk_approval: bool = True
    enforcement: str = "block_and_log"


class DelegationPolicy(BaseModel):
    trader_delegation: TraderDelegationPolicy


class NoExternalExfiltrationRule(BaseModel):
    description: str = ""
    allowed_domains: List[str] = []
    blocked_domains: List[str] = []
    blocked_tools: List[str] = []
    enforcement: str = "block_and_log"


class DataSafetyPolicy(BaseModel):
    no_external_exfiltration: NoExternalExfiltrationRule = Field(
        default_factory=NoExternalExfiltrationRule
    )
    # Additional rules (pii, credential access) accepted but not structurally enforced yet
    model_config = {"extra": "allow"}


class PolicyMetadata(BaseModel):
    version: str = "1.0.0"
    system: str = ""
    description: str = ""
    created_by: str = ""
    enforcement: str = "deterministic"


class ShieldTradePolicy(BaseModel):
    """Top-level policy document schema.

    Loaded and validated from config/shieldtrade-policies.yaml at startup.
    Each section (trading, delegation, data_safety, agent_roles) maps to a
    typed sub-model so that misconfigured YAML fails loudly rather than
    silently applying wrong defaults.
    """
    metadata: PolicyMetadata = Field(default_factory=PolicyMetadata)
    agent_roles: Dict[str, AgentRole] = {}
    trading: TradingPolicy
    delegation: DelegationPolicy
    data_safety: DataSafetyPolicy = Field(default_factory=DataSafetyPolicy)

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = Path(os.environ.get("SHIELDTRADE_POLICY_PATH", str(ROOT / "config" / "shieldtrade-policies.yaml")))
DAILY_SPEND_PATH = ROOT / "output" / "trade-logs" / "daily-spend.json"
DAILY_SPEND_LOCK = ROOT / "output" / "trade-logs" / "daily-spend.json.lock"


def load_policy() -> dict:
    """Load and validate shieldtrade-policies.yaml.

    The raw YAML is validated against ShieldTradePolicy (Pydantic schema)
    at load time, raising ValidationError immediately if the config is
    structurally invalid.  Returns a plain dict so existing callers and
    tests remain compatible.
    """
    with open(POLICY_PATH, "r") as f:
        raw = yaml.safe_load(f)
    # Schema validation: raises pydantic.ValidationError on bad config.
    ShieldTradePolicy.model_validate(raw)
    return raw


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_key() -> str:
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


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

def _result(passed: bool, check: str, detail: str, policy_ref: str = "") -> dict:
    """Build a check result object.

    Every result carries:
      - enforcement: "autonomous"  — block is deterministic, no human approval needed
      - policy_ref:  dot-path into shieldtrade-policies.yaml that drove this decision
                     (proves the rule comes from the declarative policy, not if/else logic)
    """
    r: dict = {
        "check": check,
        "result": "PASS" if passed else "FAIL",
        "detail": detail,
        "enforcement": "autonomous",
    }
    if policy_ref:
        r["policy_ref"] = policy_ref
    return r


def check_ticker(ticker: str, policy: dict) -> dict:
    allowed = policy.get("trading", {}).get("approved_tickers", {}).get("symbols", [])
    ref = "trading.approved_tickers.symbols"
    if ticker.upper() in allowed:
        return _result(True, "ticker", f"{ticker} is in the allowed list", ref)
    return _result(False, "ticker", f"{ticker} not in allowed list: {allowed}", ref)


def check_order_size(amount_usd: float, policy: dict) -> dict:
    limit = policy.get("trading", {}).get("order_limits", {}).get("per_order_max_usd", 0)
    ref = "trading.order_limits.per_order_max_usd"
    if amount_usd <= limit:
        return _result(True, "order_size", f"${amount_usd:.2f} within single-order limit ${limit}", ref)
    return _result(False, "order_size", f"${amount_usd:.2f} exceeds single-order limit ${limit}", ref)


def check_share_count(shares: int, policy: dict) -> dict:
    limit = policy.get("trading", {}).get("order_limits", {}).get("per_order_max_shares", 0)
    ref = "trading.order_limits.per_order_max_shares"
    if shares <= limit:
        return _result(True, "share_count", f"{shares} shares within position limit {limit}", ref)
    return _result(False, "share_count", f"{shares} shares exceeds position limit {limit}", ref)


def check_daily_limit(amount_usd: float, policy: dict) -> dict:
    limit = policy.get("trading", {}).get("order_limits", {}).get("daily_aggregate_max_usd", 0)
    current = _get_today_spend()
    projected = current + amount_usd
    ref = "trading.order_limits.daily_aggregate_max_usd"
    if projected <= limit:
        return _result(True, "daily_limit", f"Projected ${projected:.2f} within daily limit ${limit}", ref)
    return _result(
        False, "daily_limit",
        f"Projected ${projected:.2f} exceeds daily limit ${limit} (already spent ${current:.2f})",
        ref,
    )


def check_market_hours(policy: dict) -> dict:
    mh = policy.get("trading", {}).get("time_restrictions", {}).get("market_hours_only", {})
    ref = "trading.time_restrictions.market_hours_only"
    if not mh.get("enabled", False):
        return _result(True, "market_hours", "Market hours check disabled in policy", ref)

    tz_name = mh.get("timezone", "US/Eastern")
    try:
        tz = ZoneInfo(tz_name)
    except KeyError:
        return _result(False, "market_hours", f"Unknown timezone: {tz_name}", ref)

    now = datetime.now(tz)
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    current_minutes = hour * 60 + minute

    if weekday >= 5:
        return _result(False, "market_hours", f"Market closed: weekend ({now.strftime('%A')})", ref)

    market_open = 9 * 60 + 30   # 9:30 AM ET
    market_close = 16 * 60      # 4:00 PM ET

    if market_open <= current_minutes < market_close:
        return _result(True, "market_hours", f"Market open ({now.strftime('%H:%M %Z')})", ref)
    return _result(False, "market_hours", f"Market closed ({now.strftime('%H:%M %Z')})", ref)


def check_earnings_blackout(ticker: str, policy: dict) -> dict:
    eb = policy.get("trading", {}).get("time_restrictions", {}).get("earnings_blackout", {})
    ref = "trading.time_restrictions.earnings_blackout"
    if not eb.get("enabled", False):
        return _result(True, "earnings_blackout", "Earnings blackout check disabled in policy", ref)

    events = eb.get("events")
    if not isinstance(events, list):
        return _result(False, "earnings_blackout", "Earnings blackout events list missing or malformed — fail-closed", ref)

    before_min = eb.get("window_before_minutes", 30)
    after_min = eb.get("window_after_minutes", 30)
    tz = ZoneInfo("America/New_York")
    now = datetime.now(tz)

    for event in events:
        if event.get("ticker", "").upper() != ticker.upper():
            continue
        event_date_str = event.get("date")
        if not event_date_str:
            continue
        try:
            event_dt = datetime.fromisoformat(event_date_str).astimezone(tz)
        except (ValueError, TypeError):
            continue
        window_start = event_dt - timedelta(minutes=before_min)
        window_end = event_dt + timedelta(minutes=after_min)
        if window_start <= now <= window_end:
            return _result(
                False, "earnings_blackout",
                f"Earnings blackout active for {ticker}: event at {event_date_str}, "
                f"window {window_start.strftime('%Y-%m-%dT%H:%M %Z')} to {window_end.strftime('%Y-%m-%dT%H:%M %Z')}",
                ref,
            )

    return _result(True, "earnings_blackout", f"No active earnings blackout for {ticker}", ref)


def check_role_permission(agent: str, tool: str, policy: dict) -> dict:
    agents_cfg = policy.get("agent_roles", {})

    agent_cfg = agents_cfg.get(agent)
    if agent_cfg is None:
        return _result(False, "role_permission", f"Unknown agent: {agent}", "agent_roles")

    denied = agent_cfg.get("denied_tools", [])
    if tool in denied:
        return _result(
            False, "role_permission",
            f"Agent '{agent}' is denied tool '{tool}'",
            f"agent_roles.{agent}.denied_tools",
        )

    allowed = agent_cfg.get("allowed_tools", [])
    if tool in allowed:
        return _result(
            True, "role_permission",
            f"Agent '{agent}' is allowed tool '{tool}'",
            f"agent_roles.{agent}.allowed_tools",
        )

    return _result(
        False, "role_permission",
        f"Tool '{tool}' not in '{agent}' allowed list",
        f"agent_roles.{agent}.allowed_tools",
    )


def check_delegation(
    delegation: dict,
    policy: dict,
    *,
    shares: int | None = None,
    amount_usd: float | None = None,
) -> dict:
    """Validate a delegation token structure, TTL, and order caps.

    Expected delegation dict:
      - issued_by:  agent that issued (must be risk_manager)
      - issued_to:  target agent (must be trader)
      - ticker:     approved ticker
      - max_usd:    spending cap for this delegation
      - max_shares: share cap
      - issued_at:  ISO timestamp of issuance
      - token_id:   unique token identifier

    Optional keyword args:
      - shares:     actual requested shares (checked against max_shares cap)
      - amount_usd: actual requested notional (checked against max_usd cap)
    """
    deleg_cfg = policy.get("delegation", {}).get("trader_delegation", {})
    ref = "delegation.trader_delegation"

    if not delegation:
        return _result(False, "delegation", "No delegation token provided", ref)

    required_fields = ["issued_by", "issued_to", "ticker", "max_usd", "max_shares", "issued_at", "token_id"]
    missing = [f for f in required_fields if f not in delegation]
    if missing:
        return _result(False, "delegation", f"Missing fields: {missing}", ref)

    if deleg_cfg.get("require_risk_approval", True):
        if delegation["issued_by"] != "risk_manager":
            return _result(False, "delegation", f"Delegation must be issued by risk_manager, got '{delegation['issued_by']}'", ref)

    if delegation["issued_to"] != "trader":
        return _result(False, "delegation", f"Delegation must target trader, got '{delegation['issued_to']}'", ref)

    ttl = deleg_cfg.get("expiry_minutes", 5) * 60
    try:
        issued = datetime.fromisoformat(delegation["issued_at"])
        if issued.tzinfo is None:
            issued = issued.replace(tzinfo=timezone.utc)
        age = (_utc_now() - issued).total_seconds()
        if age > ttl:
            return _result(False, "delegation", f"Token expired: age {age:.0f}s exceeds TTL {ttl}s", f"{ref}.expiry_minutes")
        if age < 0:
            return _result(False, "delegation", f"Token issued in the future: {delegation['issued_at']}", ref)
    except (ValueError, TypeError) as e:
        return _result(False, "delegation", f"Invalid issued_at timestamp: {e}", ref)

    # YAML ceiling: token's own caps must not exceed policy-defined maximums
    yaml_max_shares = deleg_cfg.get("max_shares_per_delegation")
    yaml_max_usd = deleg_cfg.get("max_usd_per_delegation")
    if yaml_max_shares is not None and int(delegation["max_shares"]) > int(yaml_max_shares):
        return _result(
            False, "delegation",
            f"Delegation max_shares {delegation['max_shares']} exceeds policy ceiling {yaml_max_shares}",
            f"{ref}.max_shares_per_delegation",
        )
    if yaml_max_usd is not None and float(delegation["max_usd"]) > float(yaml_max_usd):
        return _result(
            False, "delegation",
            f"Delegation max_usd {delegation['max_usd']:.2f} exceeds policy ceiling {yaml_max_usd:.2f}",
            f"{ref}.max_usd_per_delegation",
        )

    # Cap enforcement: request must not exceed delegation limits
    if shares is not None and shares > delegation["max_shares"]:
        return _result(
            False, "delegation",
            f"Requested {shares} shares exceeds delegation cap {delegation['max_shares']}",
            ref,
        )
    if amount_usd is not None and amount_usd > delegation["max_usd"]:
        return _result(
            False, "delegation",
            f"Requested ${amount_usd:.2f} exceeds delegation cap ${delegation['max_usd']:.2f}",
            ref,
        )

    return _result(True, "delegation", f"Delegation token {delegation['token_id']} is valid (age {age:.0f}s)", ref)


def check_data_safety(domain: str, policy: dict) -> dict:
    """Block requests targeting unauthorized API endpoints.

    Fail-closed: a domain not explicitly in the allow-list is rejected.
    This catches prompt-injection attacks that try to reroute an order from
    paper-api.alpaca.markets to the live API or an attacker-controlled host.
    """
    network = policy.get("data_safety", {}).get("no_external_exfiltration", {})
    blocked = network.get("blocked_domains", [])
    allowed = network.get("allowed_domains", [])
    ref = "data_safety.no_external_exfiltration.allowed_domains"

    if domain in blocked:
        return _result(False, "data_safety", f"Domain '{domain}' is explicitly blocked", ref)
    if domain in allowed:
        return _result(True, "data_safety", f"Domain '{domain}' is allowed", ref)
    return _result(False, "data_safety", f"Domain '{domain}' not in allowed list — exfiltration blocked", ref)


def check_pii_in_tool_args(args: str, policy: dict) -> dict:
    """Scan free-form tool arguments for PII patterns declared in policy YAML.

    Patterns live under data_safety.no_pii_in_tool_args.patterns (regex strings).
    A prompt-injection payload that smuggles an SSN, credit-card number, or
    9-digit account number into a market-data query is blocked here before
    the tool is invoked.

    Fail-closed: if the patterns list is misconfigured (non-list), block.
    """
    pii_cfg = policy.get("data_safety", {}).get("no_pii_in_tool_args", {})
    patterns = pii_cfg.get("patterns")
    ref = "data_safety.no_pii_in_tool_args.patterns"
    if not isinstance(patterns, list):
        return _result(False, "pii_in_tool_args", "PII pattern list missing or malformed — fail-closed", ref)
    if not patterns:
        return _result(True, "pii_in_tool_args", "No PII patterns configured", ref)

    for pattern in patterns:
        try:
            if re.search(pattern, args):
                return _result(
                    False, "pii_in_tool_args",
                    f"PII detected in tool arguments (matched pattern: {pattern!r}) — call blocked",
                    ref,
                )
        except re.error:
            continue  # malformed pattern: skip, don't block on misconfiguration

    return _result(True, "pii_in_tool_args", "No PII detected in tool arguments", ref)


# ---------------------------------------------------------------------------
# aggregate validator
# ---------------------------------------------------------------------------

def validate_trade(
    request: "dict | TradeIntent",
    policy: dict,
    *,
    record_spend_if_allow: bool = True,
) -> dict:
    """Run all checks against a trade request.

    Accepts either a raw dict or a TradeIntent model.  Raw dicts are
    coerced into TradeIntent (with DelegationToken nested) so that every
    enforcement decision is grounded in a schema-validated intent object.

    Expected request fields:
      - agent:      requesting agent id
      - tool:       tool being invoked
      - ticker:     stock symbol
      - shares:     number of shares
      - amount_usd: dollar value of the order
      - domain:     target API domain
      - delegation: delegation token dict (optional, required for trader)

    If *record_spend_if_allow* is False, successful ALLOW does not mutate
    daily-spend.json (used for risk pre-checks and dry-run pipelines).
    """
    checks = []

    # Coerce raw dict into typed TradeIntent (schema-validated intent model).
    if isinstance(request, dict):
        intent = TradeIntent.model_validate(request)
    else:
        intent = request

    agent = intent.agent
    tool = intent.tool
    ticker = intent.ticker
    shares = intent.shares
    amount = intent.amount_usd
    domain = intent.domain
    # Preserve raw delegation dict for check_delegation (which accepts dict)
    delegation = request.get("delegation") if isinstance(request, dict) else (
        intent.delegation.model_dump() if intent.delegation else None
    )

    checks.append(check_role_permission(agent, tool, policy))
    # Market hours is scoped to execution roles/tools only.
    # The YAML declares applies_to_roles and applies_to_tools; the engine
    # reads them so the restriction is policy-driven, not hardcoded.
    _mh_cfg = (policy.get("trading", {})
               .get("time_restrictions", {})
               .get("market_hours_only", {}))
    _mh_roles = set(_mh_cfg.get("applies_to_roles", ["trader"]))
    _mh_tools = set(_mh_cfg.get("applies_to_tools",
                                ["place_order", "submit_order", "order"]))
    if agent in _mh_roles or tool in _mh_tools:
        checks.append(check_market_hours(policy))

    if ticker:
        checks.append(check_ticker(ticker, policy))
        checks.append(check_earnings_blackout(ticker, policy))
    if shares > 0:
        checks.append(check_share_count(shares, policy))
    if amount > 0:
        checks.append(check_order_size(amount, policy))
        checks.append(check_daily_limit(amount, policy))
    if domain:
        checks.append(check_data_safety(domain, policy))
    if intent.tool_args:
        checks.append(check_pii_in_tool_args(intent.tool_args, policy))
    if delegation is not None:
        checks.append(check_delegation(
            delegation, policy,
            shares=shares if shares > 0 else None,
            amount_usd=amount if amount > 0 else None,
        ))
    elif agent == "trader" and tool == "place_order":
        checks.append(_result(False, "delegation", "Trader must provide delegation token for place_order", "delegation.trader_delegation"))

    failed = [c for c in checks if c["result"] == "FAIL"]
    decision = "BLOCK" if failed else "ALLOW"

    if decision == "ALLOW" and amount > 0 and record_spend_if_allow:
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


def _cli_check_data_safety(args: list[str]) -> None:
    """check-data-safety <domain>

    Returns PASS if the domain is in the allowed list, FAIL otherwise.
    Use this to demonstrate that orders cannot be silently rerouted to
    unauthorized endpoints (e.g. live trading API instead of paper API).
    """
    if len(args) < 1:
        _print_json({"error": "Usage: check-data-safety <domain>"})
        sys.exit(1)
    policy = load_policy()
    _print_json(check_data_safety(args[0], policy))


def _cli_check_pii(args: list[str]) -> None:
    """check-pii <tool_args_string>

    Scans the given string for PII patterns declared in policy YAML.
    Use this to demonstrate that prompt-injection payloads carrying SSNs,
    credit-card numbers, or account numbers are caught before tool invocation.
    """
    if len(args) < 1:
        _print_json({"error": "Usage: check-pii '<tool_args_string>'"})
        sys.exit(1)
    policy = load_policy()
    _print_json(check_pii_in_tool_args(args[0], policy))


COMMANDS = {
    "check-trade": _cli_check_trade,
    "check-role": _cli_check_role,
    "check-delegation": _cli_check_delegation,
    "validate-all": _cli_validate_all,
    "check-data-safety": _cli_check_data_safety,
    "check-pii": _cli_check_pii,
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
