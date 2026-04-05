#!/usr/bin/env python3
"""ShieldTrade deterministic Analyst → Risk → Trader pipeline.

Writes artifacts under output/reports, output/risk-decisions, output/trade-logs
per docs/contracts.md. Uses policy_engine and alpaca_bridge in-process.

Risk-stage policy checks do not record daily spend; only the final trader
validation (live mode) records spend on ALLOW.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

# Auto-load .env so the script works without manually sourcing it.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(ROOT / ".env", override=False)
except Exception:
    pass
REPORTS_DIR = ROOT / "output" / "reports"
RISK_DIR = ROOT / "output" / "risk-decisions"
TRADE_LOGS_DIR = ROOT / "output" / "trade-logs"
POLICY_DOMAIN = "paper-api.alpaca.markets"

sys.path.insert(0, str(SCRIPT_DIR))
import alpaca_bridge  # noqa: E402
import armoriq_stub   # noqa: E402
import policy_engine  # noqa: E402


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mid_price_from_quote(q: dict) -> float:
    ask, bid = q.get("ask_price"), q.get("bid_price")
    if ask is not None and bid is not None:
        return (float(ask) + float(bid)) / 2.0
    if ask is not None:
        return float(ask)
    if bid is not None:
        return float(bid)
    raise ValueError("Quote has no usable bid/ask price")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _write_rejection(stage: str, ticker: str, blocked_reasons: list[str]) -> Path:
    ts = _utc_now_iso().replace(":", "").split("+")[0]
    path = RISK_DIR / f"rejection-{ticker.upper()}-{ts}.json"
    _write_json(
        path,
        {
            "stage": stage,
            "ticker": ticker.upper(),
            "decision": "BLOCK",
            "blocked_reasons": blocked_reasons,
            "timestamp": _utc_now_iso(),
        },
    )
    return path


def stage_analyst_write_report(
    ticker: str,
    *,
    price: float,
    side: str,
    shares: int,
) -> Path:
    """Write output/reports/{TICKER}-recommendation.json (contracts §1)."""
    rec_side = "buy" if side.lower() == "buy" else "sell"
    rec = "BUY" if rec_side == "buy" else "SELL"
    data = {
        "schema_version": "1.0",
        "ticker": ticker.upper(),
        "recommendation": rec,
        "confidence": 0.7,
        "reasoning": "Pipeline orchestrator: price from quote or --assume-price.",
        "current_price": round(price, 4),
        "proposed_side": rec_side,
        "proposed_shares": shares,
        "timestamp": _utc_now_iso(),
    }
    path = REPORTS_DIR / f"{ticker.upper()}-recommendation.json"
    _write_json(path, data)
    return path


def stage_analyst_fetch_price(ticker: str, assume_price: float | None) -> float:
    if assume_price is not None and assume_price > 0:
        return float(assume_price)
    q = alpaca_bridge.cmd_quote(ticker)
    return _mid_price_from_quote(q)


def build_delegation(
    ticker: str,
    *,
    max_shares: int,
    max_usd: float,
    side: str,
    recommendation_path: str,
    policy: dict | None = None,
) -> dict:
    if policy is not None:
        deleg_cfg = policy.get("delegation", {}).get("trader_delegation", {})
        yaml_max_shares = deleg_cfg.get("max_shares_per_delegation")
        yaml_max_usd = deleg_cfg.get("max_usd_per_delegation")
        if yaml_max_shares is not None:
            max_shares = min(int(max_shares), int(yaml_max_shares))
        if yaml_max_usd is not None:
            max_usd = min(float(max_usd), float(yaml_max_usd))
    token_id = f"del_{ticker.lower()}_{uuid.uuid4().hex[:12]}"
    return {
        "issued_by": "risk_manager",
        "issued_to": "trader",
        "ticker": ticker.upper(),
        "max_usd": round(float(max_usd), 2),
        "max_shares": int(max_shares),
        "issued_at": _utc_now_iso(),
        "token_id": token_id,
        "side": side.lower(),
        "recommendation_path": recommendation_path,
    }


def enforce_delegation_caps(
    delegation: dict, ticker: str, shares: int, amount_usd: float
) -> str | None:
    if delegation.get("ticker", "").upper() != ticker.upper():
        return "Delegation ticker does not match pipeline ticker"
    if shares > int(delegation["max_shares"]):
        return f"Requested shares {shares} exceed delegation max_shares {delegation['max_shares']}"
    if amount_usd > float(delegation["max_usd"]) + 1e-6:
        return f"Requested notional {amount_usd:.2f} exceeds delegation max_usd {delegation['max_usd']}"
    return None


def run_pipeline(
    ticker: str,
    shares: int,
    side: str,
    *,
    assume_price: float | None,
    dry_run: bool,
    skip_analyst: bool,
    policy: dict | None = None,
) -> dict:
    ticker = ticker.upper()
    side_l = side.lower()
    if side_l not in ("buy", "sell"):
        raise ValueError("side must be buy or sell")

    policy = policy if policy is not None else policy_engine.load_policy()

    # --- Analyst (or load existing report for price/shares hints) ---
    report_path = REPORTS_DIR / f"{ticker}-recommendation.json"
    if skip_analyst:
        if not report_path.exists():
            raise FileNotFoundError(f"Missing report (--skip-analyst): {report_path}")
        with open(report_path) as f:
            report = json.load(f)
        if report.get("ticker", "").upper() != ticker:
            raise ValueError("Report ticker does not match CLI ticker")
        price = float(report.get("current_price") or assume_price or 0)
        if price <= 0:
            price = stage_analyst_fetch_price(ticker, assume_price)
        eff_shares = shares if shares > 0 else int(report.get("proposed_shares") or 0)
        if eff_shares <= 0:
            raise ValueError("shares must be positive (or set proposed_shares in report)")
    else:
        price = stage_analyst_fetch_price(ticker, assume_price)
        eff_shares = shares
        if eff_shares <= 0:
            raise ValueError("shares must be positive")
        report_path = stage_analyst_write_report(
            ticker, price=price, side=side_l, shares=eff_shares
        )

    amount_usd = round(price * eff_shares, 2)
    rel_report = str(report_path.relative_to(ROOT))

    # --- Risk: policy check without recording spend ---
    risk_req = {
        "agent": "risk_manager",
        "tool": "approve_trade",
        "ticker": ticker,
        "shares": eff_shares,
        "amount_usd": amount_usd,
        "domain": POLICY_DOMAIN,
    }
    risk_res = policy_engine.validate_trade(
        risk_req, policy, record_spend_if_allow=False
    )
    if risk_res["decision"] != "ALLOW":
        rej = _write_rejection("risk", ticker, risk_res["blocked_reasons"])
        return {
            "ok": False,
            "stopped_at": "risk",
            "policy": risk_res,
            "rejection_path": str(rej.relative_to(ROOT)),
        }

    delegation = build_delegation(
        ticker,
        max_shares=eff_shares,
        max_usd=amount_usd,
        side=side_l,
        recommendation_path=rel_report,
        policy=policy,
    )
    del_path = RISK_DIR / f"delegation-{ticker}-{delegation['token_id']}.json"
    _write_json(del_path, delegation)

    # --- Trader: delegation structural check ---
    dcheck = policy_engine.check_delegation(delegation, policy)
    if dcheck["result"] != "PASS":
        rej = _write_rejection("trader", ticker, [dcheck["detail"]])
        return {
            "ok": False,
            "stopped_at": "trader_delegation",
            "delegation_check": dcheck,
            "delegation_path": str(del_path.relative_to(ROOT)),
            "rejection_path": str(rej.relative_to(ROOT)),
        }

    cap_err = enforce_delegation_caps(delegation, ticker, eff_shares, amount_usd)
    if cap_err:
        rej = _write_rejection("trader", ticker, [cap_err])
        return {
            "ok": False,
            "stopped_at": "trader_caps",
            "detail": cap_err,
            "delegation_path": str(del_path.relative_to(ROOT)),
            "rejection_path": str(rej.relative_to(ROOT)),
        }

    trade_req = {
        "agent": "trader",
        "tool": "place_order",
        "ticker": ticker,
        "shares": eff_shares,
        "amount_usd": amount_usd,
        "domain": POLICY_DOMAIN,
        "delegation": delegation,
    }
    spend_ok = not dry_run
    trader_res = policy_engine.validate_trade(
        trade_req, policy, record_spend_if_allow=spend_ok
    )
    if trader_res["decision"] != "ALLOW":
        rej = _write_rejection("trader", ticker, trader_res["blocked_reasons"])
        return {
            "ok": False,
            "stopped_at": "trader_policy",
            "policy": trader_res,
            "delegation_path": str(del_path.relative_to(ROOT)),
            "rejection_path": str(rej.relative_to(ROOT)),
        }

    policy_check_id = trader_res.get("policy_check_id")
    ts_slug = _utc_now_iso().replace(":", "").replace("+00:00", "Z")
    exec_path = TRADE_LOGS_DIR / f"execution-{ticker}-{ts_slug}.json"

    if dry_run:
        # Issue a real ArmorIQ intent token even in dry-run so it shows in the dashboard.
        try:
            _intent_token_str = armoriq_stub.issue(
                ticker, eff_shares, side_l,
                policy_check_id=str(policy_check_id) if policy_check_id else None,
            )
            _intent_token = json.loads(_intent_token_str)
        except Exception as _exc:
            _intent_token = {"error": str(_exc), "source": "unavailable"}

        log_body = {
            "schema_version": "1.0",
            "timestamp": _utc_now_iso(),
            "delegation_token_id": delegation["token_id"],
            "policy_check_id": policy_check_id,
            "dry_run": True,
            "armoriq_token": _intent_token,
            "order": {
                "status": "dry_run",
                "symbol": ticker,
                "qty": str(eff_shares),
                "side": side_l,
                "note": "Alpaca submit_order skipped (--dry-run)",
            },
        }
        _write_json(exec_path, log_body)
        return {
            "ok": True,
            "dry_run": True,
            "report_path": rel_report,
            "delegation_path": str(del_path.relative_to(ROOT)),
            "execution_log_path": str(exec_path.relative_to(ROOT)),
            "risk_policy": risk_res,
            "trader_policy": trader_res,
            "armoriq_token": _intent_token,
        }

    order = alpaca_bridge.cmd_order(
        ticker, eff_shares, side_l, policy_check_id=str(policy_check_id) if policy_check_id else None
    )
    log_body = {
        "schema_version": "1.0",
        "timestamp": _utc_now_iso(),
        "delegation_token_id": delegation["token_id"],
        "policy_check_id": policy_check_id,
        "order": order,
    }
    _write_json(exec_path, log_body)
    return {
        "ok": True,
        "dry_run": False,
        "report_path": rel_report,
        "delegation_path": str(del_path.relative_to(ROOT)),
        "execution_log_path": str(exec_path.relative_to(ROOT)),
        "risk_policy": risk_res,
        "trader_policy": trader_res,
        "order": order,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("ticker", help="Symbol, e.g. AAPL")
    p.add_argument(
        "--shares",
        type=int,
        default=0,
        help="Share count (required unless --skip-analyst and report has proposed_shares)",
    )
    p.add_argument("--side", choices=("buy", "sell"), default="buy")
    p.add_argument(
        "--assume-price",
        type=float,
        default=None,
        help="Skip Alpaca quote; use this USD price (handy for CI / no keys)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Run policy + write execution log without Alpaca order or daily-spend write",
    )
    p.add_argument(
        "--skip-analyst",
        action="store_true",
        help="Do not overwrite report; read output/reports/{TICKER}-recommendation.json",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="Use config/demo-policy.yaml (market hours disabled); no shell setup needed",
    )
    args = p.parse_args()

    if args.demo:
        import os as _os
        demo_policy = ROOT / "config" / "demo-policy.yaml"
        if demo_policy.exists():
            _os.environ["SHIELDTRADE_POLICY_PATH"] = str(demo_policy)
            policy_engine.POLICY_PATH = demo_policy
    try:
        out = run_pipeline(
            args.ticker,
            args.shares,
            args.side,
            assume_price=args.assume_price,
            dry_run=args.dry_run,
            skip_analyst=args.skip_analyst,
        )
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)
    print(json.dumps(out, indent=2))
    sys.exit(0 if out.get("ok") else 2)


if __name__ == "__main__":
    main()
