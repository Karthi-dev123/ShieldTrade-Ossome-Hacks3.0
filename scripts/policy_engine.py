#!/usr/bin/env python3
"""
ShieldTrade — Policy Enforcement Engine
========================================
Evaluates trade requests against the declarative YAML policy model.
Returns structured PASS/FAIL results for every constraint.

Usage:
  python3 policy_engine.py check-trade '{"symbol":"AAPL","qty":10,"side":"buy","price":152.0}'
  python3 policy_engine.py check-role analyst place_order
  python3 policy_engine.py check-delegation '{"delegation_json..."}' '{"request_json..."}'
  python3 policy_engine.py validate-all '{"trade_json"}' analyst
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

import yaml

POLICY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "config",
    "shieldtrade-policies.yaml",
)

with open(POLICY_PATH, "r", encoding="utf-8") as policy_file:
    POLICY = yaml.safe_load(policy_file)

DAILY_SPEND_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "output",
    "trade-logs",
    "daily-spend.json",
)


def get_daily_spend():
    try:
        with open(DAILY_SPEND_FILE, "r", encoding="utf-8") as spend_file:
            data = json.load(spend_file)
            if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
                return float(data.get("total_usd", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        pass
    return 0.0


def update_daily_spend(amount):
    current = get_daily_spend()
    data = {"date": datetime.now().strftime("%Y-%m-%d"), "total_usd": current + amount}
    os.makedirs(os.path.dirname(DAILY_SPEND_FILE), exist_ok=True)
    with open(DAILY_SPEND_FILE, "w", encoding="utf-8") as spend_file:
        json.dump(data, spend_file, indent=2)


def check_ticker(symbol):
    approved = POLICY["trading"]["approved_tickers"]["symbols"]
    passed = symbol.upper() in approved
    return {
        "check": "ticker_approved",
        "passed": passed,
        "detail": f"{symbol} {'is' if passed else 'is NOT'} in approved list {approved}",
    }


def check_order_size(qty, price):
    limit = POLICY["trading"]["order_limits"]["per_order_max_usd"]
    total = qty * price
    passed = total <= limit
    return {
        "check": "order_size_limit",
        "passed": passed,
        "detail": f"${total:.2f} {'<=' if passed else '>'} ${limit} limit",
    }


def check_share_count(qty):
    limit = POLICY["trading"]["order_limits"]["per_order_max_shares"]
    passed = qty <= limit
    return {
        "check": "share_count_limit",
        "passed": passed,
        "detail": f"{qty} shares {'<=' if passed else '>'} {limit} limit",
    }


def check_daily_limit(additional_usd):
    limit = POLICY["trading"]["order_limits"]["daily_aggregate_max_usd"]
    current = get_daily_spend()
    new_total = current + additional_usd
    passed = new_total <= limit
    return {
        "check": "daily_aggregate_limit",
        "passed": passed,
        "detail": f"Daily total ${new_total:.2f} (${current:.2f} + ${additional_usd:.2f}) {'<=' if passed else '>'} ${limit} limit",
    }


def check_market_hours():
    config = POLICY["trading"]["time_restrictions"]["market_hours_only"]
    if not config.get("enabled", True):
        return {"check": "market_hours", "passed": True, "detail": "Check disabled"}

    try:
        from zoneinfo import ZoneInfo

        now_et = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return {
            "check": "market_hours",
            "passed": True,
            "detail": "Timezone data unavailable; market hours check skipped",
        }
    current_time = now_et.strftime("%H:%M")

    start = config["start"]
    end = config["end"]
    passed = start <= current_time <= end

    return {
        "check": "market_hours",
        "passed": passed,
        "detail": f"Current time {current_time} ET {'within' if passed else 'outside'} {start}-{end}",
    }


def check_role_permission(agent_role, tool_name):
    role_config = POLICY["agent_roles"].get(agent_role)
    if not role_config:
        return {
            "check": "role_permission",
            "passed": False,
            "detail": f"Unknown agent role: {agent_role}",
        }

    denied = role_config.get("denied_tools", [])
    allowed = role_config.get("allowed_tools", [])

    if tool_name in denied:
        return {
            "check": "role_permission",
            "passed": False,
            "detail": f"Tool '{tool_name}' is in {agent_role}'s denied_tools list",
        }

    if tool_name in allowed:
        return {
            "check": "role_permission",
            "passed": True,
            "detail": f"Tool '{tool_name}' is in {agent_role}'s allowed_tools list",
        }

    return {
        "check": "role_permission",
        "passed": False,
        "detail": f"Tool '{tool_name}' not found in {agent_role}'s allowed_tools",
    }


def check_delegation(delegation, request):
    checks = []

    status_ok = delegation.get("status") == "APPROVED"
    checks.append({"check": "delegation_status", "passed": status_ok, "detail": f"Status: {delegation.get('status')}"})

    try:
        expires = datetime.fromisoformat(delegation["expires_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        not_expired = now < expires
    except (KeyError, ValueError):
        not_expired = False
    checks.append({"check": "delegation_not_expired", "passed": not_expired, "detail": f"Expires: {delegation.get('expires_at', 'missing')}"})

    approved_action = delegation.get("approved_action", {})
    symbol_match = request.get("symbol", "").upper() == approved_action.get("symbol", "").upper()
    checks.append(
        {
            "check": "delegation_symbol_match",
            "passed": symbol_match,
            "detail": f"Requested {request.get('symbol')} vs delegated {approved_action.get('symbol')}",
        }
    )

    req_qty = float(request.get("qty", 0))
    max_qty = float(approved_action.get("max_quantity", 0))
    qty_ok = req_qty <= max_qty
    checks.append(
        {
            "check": "delegation_quantity_limit",
            "passed": qty_ok,
            "detail": f"Requested {req_qty} <= max {max_qty}: {'yes' if qty_ok else 'NO'}",
        }
    )

    to_agent_ok = delegation.get("to_agent") == "trader"
    checks.append({"check": "delegation_target_agent", "passed": to_agent_ok, "detail": f"to_agent: {delegation.get('to_agent')}"})

    return {"all_passed": all(c["passed"] for c in checks), "checks": checks}


def check_data_safety(tool_args_string):
    patterns = POLICY["data_safety"]["no_pii_in_tool_args"]["patterns"]
    found = []
    for pattern in patterns:
        if re.search(pattern, tool_args_string):
            found.append(pattern)

    passed = len(found) == 0
    return {
        "check": "data_safety_pii",
        "passed": passed,
        "detail": f"PII patterns {'not found' if passed else 'FOUND: ' + str(found)}",
    }


def validate_trade(trade, agent_role="trader"):
    symbol = trade.get("symbol", "").upper()
    qty = float(trade.get("qty", 0))
    price = float(trade.get("price", 0))
    side = trade.get("side", "buy")
    total_usd = qty * price

    results = {
        "trade": {"symbol": symbol, "qty": qty, "price": price, "side": side, "estimated_cost": total_usd},
        "agent": agent_role,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": [],
    }

    results["checks"].append(check_role_permission(agent_role, "place_order"))
    results["checks"].append(check_ticker(symbol))
    results["checks"].append(check_order_size(qty, price))
    results["checks"].append(check_share_count(qty))
    results["checks"].append(check_daily_limit(total_usd))
    results["checks"].append(check_market_hours())
    results["checks"].append(check_data_safety(json.dumps(trade)))

    results["all_passed"] = all(c["passed"] for c in results["checks"])
    results["decision"] = "ALLOW" if results["all_passed"] else "BLOCK"
    results["failed_checks"] = [c["check"] for c in results["checks"] if not c["passed"]]

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "error": "Usage: policy_engine.py <command> [args]",
                    "commands": {
                        "check-trade": "Validate a trade: '{\"symbol\":\"AAPL\",\"qty\":10,\"side\":\"buy\",\"price\":150}'",
                        "check-role": "Check role permission: <role> <tool>",
                        "check-delegation": "Validate delegation: '<delegation_json>' '<request_json>'",
                        "validate-all": "Full validation: '<trade_json>' <agent_role>",
                    },
                },
                indent=2,
            )
        )
        sys.exit(1)

    cmd = sys.argv[1]

    try:
        if cmd == "check-trade":
            trade = json.loads(sys.argv[2])
            role = sys.argv[3] if len(sys.argv) > 3 else "trader"
            result = validate_trade(trade, role)
            if result.get("all_passed"):
                update_daily_spend(result["trade"].get("estimated_cost", 0))

        elif cmd == "check-role":
            role = sys.argv[2]
            tool = sys.argv[3]
            result = check_role_permission(role, tool)

        elif cmd == "check-delegation":
            delegation_json = json.loads(sys.argv[2])
            request_json = json.loads(sys.argv[3])
            result = check_delegation(delegation_json, request_json)

        elif cmd == "validate-all":
            trade = json.loads(sys.argv[2])
            role = sys.argv[3] if len(sys.argv) > 3 else "trader"
            result = validate_trade(trade, role)

        else:
            result = {"error": f"Unknown command: {cmd}"}

        print(json.dumps(result, indent=2))

    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)
