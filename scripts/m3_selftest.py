#!/usr/bin/env python3
import sys
from pathlib import Path

repo = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo / "scripts"))

import yaml
import policy_engine as pe


def run():
    yaml.safe_load((repo / "config" / "shieldtrade-policies.yaml").read_text(encoding="utf-8"))

    tests = []

    result = pe.validate_trade({"symbol": "AAPL", "qty": 10, "side": "buy", "price": 150}, "trader")
    tests.append(("T1 valid trade", result["all_passed"] and result["decision"] == "ALLOW"))

    result = pe.validate_trade({"symbol": "TSLA", "qty": 5, "side": "buy", "price": 250}, "trader")
    tests.append(("T2 unapproved ticker", (not result["all_passed"]) and ("ticker_approved" in result["failed_checks"])))

    result = pe.validate_trade({"symbol": "NVDA", "qty": 50, "side": "buy", "price": 130}, "trader")
    tests.append(("T3 over per-order usd", (not result["all_passed"]) and ("order_size_limit" in result["failed_checks"])))

    result = pe.check_role_permission("analyst", "place_order")
    tests.append(("T4 analyst blocked", result["passed"] is False))

    result = pe.check_role_permission("trader", "place_order")
    tests.append(("T5 trader allowed", result["passed"] is True))

    result = pe.check_role_permission("risk_manager", "market_data_fetch")
    tests.append(("T6 risk manager blocked", result["passed"] is False))

    delegation = {
        "status": "APPROVED",
        "to_agent": "trader",
        "approved_action": {"symbol": "AAPL", "max_quantity": 10},
        "expires_at": "2099-12-31T23:59:59Z",
    }

    result = pe.check_delegation(delegation, {"symbol": "AAPL", "qty": 10})
    tests.append(("T7 delegation valid", result["all_passed"] is True))

    result = pe.check_delegation(delegation, {"symbol": "AAPL", "qty": 50})
    tests.append((
        "T8 delegation qty fail",
        (not result["all_passed"]) and any(c["check"] == "delegation_quantity_limit" and not c["passed"] for c in result["checks"]),
    ))

    result = pe.check_delegation(delegation, {"symbol": "MSFT", "qty": 5})
    tests.append((
        "T9 delegation symbol fail",
        (not result["all_passed"]) and any(c["check"] == "delegation_symbol_match" and not c["passed"] for c in result["checks"]),
    ))

    expired = {
        "status": "APPROVED",
        "to_agent": "trader",
        "approved_action": {"symbol": "AAPL", "max_quantity": 10},
        "expires_at": "2020-01-01T00:00:00Z",
    }
    result = pe.check_delegation(expired, {"symbol": "AAPL", "qty": 5})
    tests.append((
        "T10 delegation expired fail",
        (not result["all_passed"]) and any(c["check"] == "delegation_not_expired" and not c["passed"] for c in result["checks"]),
    ))

    failed = []
    for name, passed in tests:
        print(f"{name}: {'PASS' if passed else 'FAIL'}")
        if not passed:
            failed.append(name)

    print(f"ALL_PASS={len(failed) == 0}")
    if failed:
        print("FAILED=" + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
