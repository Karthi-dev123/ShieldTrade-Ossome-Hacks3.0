#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from alpaca.trading.client import TradingClient
except Exception:
    TradingClient = None


def run_cmd(args):
    proc = subprocess.run(args, capture_output=True, text=True)
    output = (proc.stdout or proc.stderr or "").strip()
    try:
        payload = json.loads(output)
    except Exception:
        payload = {"raw_output": output}
    return proc.returncode, payload


def get_order_count():
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key or TradingClient is None:
        return None
    client = TradingClient(api_key, secret_key, paper=True)
    return len(client.get_orders())


def main():
    repo = Path(__file__).resolve().parent.parent
    policy_script = repo / "scripts" / "policy_engine.py"

    scenarios = [
        {
            "name": "blocked_unapproved_ticker",
            "cmd": [
                sys.executable,
                str(policy_script),
                "check-trade",
                json.dumps({"symbol": "TSLA", "qty": 5, "side": "buy", "price": 250}),
                "trader",
            ],
            "expected_failed_check": "ticker_approved",
        },
        {
            "name": "blocked_order_size",
            "cmd": [
                sys.executable,
                str(policy_script),
                "check-trade",
                json.dumps({"symbol": "NVDA", "qty": 50, "side": "buy", "price": 130}),
                "trader",
            ],
            "expected_failed_check": "order_size_limit",
        },
        {
            "name": "blocked_share_count",
            "cmd": [
                sys.executable,
                str(policy_script),
                "check-trade",
                json.dumps({"symbol": "AAPL", "qty": 101, "side": "buy", "price": 10}),
                "trader",
            ],
            "expected_failed_check": "share_count_limit",
        },
        {
            "name": "blocked_pii_payload",
            "cmd": [
                sys.executable,
                str(policy_script),
                "check-trade",
                json.dumps({"symbol": "AAPL", "qty": 10, "side": "buy", "price": 150, "ssn": "123-45-6789"}),
                "trader",
            ],
            "expected_failed_check": "data_safety_pii",
        },
    ]

    before_orders = get_order_count()

    results = []
    for scenario in scenarios:
        code, payload = run_cmd(scenario["cmd"])
        failed_checks = payload.get("failed_checks", []) if isinstance(payload, dict) else []
        blocked = isinstance(payload, dict) and payload.get("decision") == "BLOCK"
        expected_hit = scenario["expected_failed_check"] in failed_checks
        results.append(
            {
                "scenario": scenario["name"],
                "exit_code": code,
                "blocked": blocked,
                "expected_failed_check": scenario["expected_failed_check"],
                "failed_checks": failed_checks,
                "pass": blocked and expected_hit,
            }
        )

    after_orders = get_order_count()
    alpaca_drop_confirmed = None
    if before_orders is not None and after_orders is not None:
        alpaca_drop_confirmed = before_orders == after_orders

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "all_passed": all(r["pass"] for r in results),
        "scenarios": results,
        "alpaca_orders_before": before_orders,
        "alpaca_orders_after": after_orders,
        "alpaca_drop_confirmed": alpaca_drop_confirmed,
    }

    out_dir = repo / "output" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "gateway-validation.json"
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
