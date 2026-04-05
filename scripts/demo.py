#!/usr/bin/env python3
"""ShieldTrade demonstration script.

Shows two live integrations in sequence:
  1. ArmorIQ  — real intent token issued and visible in the ArmorIQ dashboard
  2. OpenClaw — agent list + analyst agent health-check via local gateway

Run:
    python scripts/demo.py
    python scripts/demo.py --ticker MSFT --shares 3
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Load .env so API keys are available without manual export
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except Exception:
    pass


# ── ANSI colours ──────────────────────────────────────────────────────────────
def _g(s):  return f"\033[92m{s}\033[0m"   # green
def _b(s):  return f"\033[94m{s}\033[0m"   # blue
def _y(s):  return f"\033[93m{s}\033[0m"   # yellow
def _r(s):  return f"\033[91m{s}\033[0m"   # red
def _bold(s): return f"\033[1m{s}\033[0m"


def _banner(title: str) -> None:
    print("\n" + "─" * 60)
    print(_bold(f"  {title}"))
    print("─" * 60)


def _ok(msg):  print(_g(f"  ✓ {msg}"))
def _info(msg): print(_b(f"  ℹ {msg}"))
def _warn(msg): print(_y(f"  ⚠ {msg}"))
def _fail(msg): print(_r(f"  ✗ {msg}"))


# ── Demo 1: ArmorIQ ───────────────────────────────────────────────────────────

def demo_armoriq(ticker: str, shares: int, side: str = "buy") -> dict | None:
    _banner("DEMO 1 — ArmorIQ Intent Analysis Platform")

    _info("Importing armoriq_stub …")
    import armoriq_stub

    if not armoriq_stub._USE_REAL_API:
        _warn("ARMORIQ_API_KEY not set or bridge missing — falling back to HMAC stub.")
        _warn("Set ARMORIQ_API_KEY in .env and ensure Node.js is available for real tokens.")
    else:
        _ok(f"Real API enabled (key: {armoriq_stub._ARMORIQ_API_KEY[:12]}…)")

    _info(f"Issuing intent token: {side.upper()} {shares} × {ticker} …")
    t0 = time.time()
    try:
        token_str = armoriq_stub.issue(ticker, shares, side)
        elapsed = time.time() - t0
        token = json.loads(token_str)
    except Exception as exc:
        _fail(f"Token issuance failed: {exc}")
        return None

    source = token.get("source", "unknown")
    if source == "armoriq_iap":
        _ok(f"Real ArmorIQ token issued in {elapsed:.2f}s")
        _ok(f"  token_id  : {token.get('token_id', 'n/a')}")
        _ok(f"  plan_id   : {token.get('plan_id', 'n/a')}")
        _ok(f"  expires_at: {token.get('expires_at', 'n/a')}")
        _ok(f"  step_count: {token.get('step_count', 'n/a')}")
        print()
        print(_bold("  ▶ Check the ArmorIQ dashboard to see this token logged:"))
        print(f"    https://app.armoriq.ai  (or customer-api.armoriq.ai/dashboard)")
        print(f"    Agent: shieldtrade-trader  |  Goal: {side.upper()} {shares} shares of {ticker}")
    else:
        _warn(f"HMAC fallback used (source={source}). Real API call not made.")
        _warn("No entry will appear in the ArmorIQ dashboard for this run.")

    print()
    _info("Full token payload:")
    # Print without the raw field (too long)
    display = {k: v for k, v in token.items() if k != "raw"}
    print(json.dumps(display, indent=2))
    return token


# ── Demo 2: OpenClaw ──────────────────────────────────────────────────────────

def demo_openclaw() -> bool:
    _banner("DEMO 2 — OpenClaw Agent Framework")

    gateway_token = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "d17d4ab08c80922f2bff84cedcad95e54b75e7c2d16ebb01")
    config_path   = str(ROOT / "config" / "openclaw.json")

    env = {
        **os.environ,
        "OPENCLAW_CONFIG_PATH": config_path,
        "OPENCLAW_GATEWAY_TOKEN": gateway_token,
    }

    # ── Health check ──────────────────────────────────────────────────────────
    _info("Checking OpenClaw gateway health …")
    health = subprocess.run(
        ["openclaw", "health"],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=15,
    )
    if health.returncode == 0:
        _ok("Gateway healthy")
        for line in health.stdout.strip().splitlines():
            print(f"    {line}")
    else:
        _warn(f"Gateway health check failed (exit {health.returncode})")
        _warn(health.stderr[:200] or health.stdout[:200])

    # ── Agents list ───────────────────────────────────────────────────────────
    _info("Listing registered OpenClaw agents …")
    agents = subprocess.run(
        ["openclaw", "agents", "list"],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=15,
    )
    if agents.returncode == 0:
        _ok("Registered agents:")
        for line in agents.stdout.strip().splitlines():
            print(f"    {line}")
    else:
        _warn("Could not list agents — gateway may not be running.")
        _warn("Start with: python scripts/start-all.py")

    # ── Quick analyst agent probe ─────────────────────────────────────────────
    _info("Sending a quick message to shieldtrade-analyst …")
    _info("(This calls the local LLM via proxy → Ollama. May take 10–60 s.)")
    agent_proc = subprocess.run(
        ["openclaw", "agent", "--local",
         "--agent", "shieldtrade-analyst",
         "Reply with exactly: ANALYST_OK"],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120,
    )
    out = (agent_proc.stdout + agent_proc.stderr).strip()
    if agent_proc.returncode == 0 and out:
        _ok("Analyst agent responded:")
        for line in out.splitlines()[:10]:
            print(f"    {line}")
        return True
    else:
        _warn(f"Agent call exit={agent_proc.returncode}")
        for line in out.splitlines()[:8]:
            print(f"    {line}")
        _warn("Tip: ensure 'python scripts/start-all.py' is running and Ollama is up.")
        return False


# ── Demo 3: Full pipeline (with ArmorIQ token) ────────────────────────────────

def demo_pipeline(ticker: str, shares: int, assume_price: float) -> None:
    _banner("DEMO 3 — Full Analyst → Risk → Trader Pipeline (dry-run)")
    _info(f"Running: {ticker}  {shares} shares  @ ${assume_price:.2f}  (dry-run, demo policy)")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "orchestrate_pipeline.py"),
         ticker, "--shares", str(shares),
         "--assume-price", str(assume_price),
         "--dry-run", "--demo"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=60,
    )

    try:
        out = json.loads(result.stdout)
    except Exception:
        _fail("Pipeline output was not JSON:")
        print(result.stdout[:500])
        print(result.stderr[:300])
        return

    if out.get("ok"):
        _ok("Pipeline completed — ALLOW")
        _ok(f"  report    : {out.get('report_path')}")
        _ok(f"  delegation: {out.get('delegation_path')}")
        _ok(f"  exec log  : {out.get('execution_log_path')}")
        tok = out.get("armoriq_token", {})
        src = tok.get("source", "unknown")
        if src == "armoriq_iap":
            _ok(f"  ArmorIQ   : token_id={tok.get('token_id')} (real — visible in dashboard)")
        else:
            _warn(f"  ArmorIQ   : {src} (HMAC fallback — not visible in dashboard)")
    else:
        _fail(f"Pipeline blocked at: {out.get('stopped_at')}")
        decision = out.get("policy", {})
        for check in decision.get("checks", []):
            if check.get("result") == "FAIL":
                _fail(f"  FAIL: {check.get('check')} — {check.get('detail')}")

    if result.stderr:
        for line in result.stderr.splitlines():
            if line.strip() and "[supabase" not in line:
                print(_y(f"  stderr: {line}"))


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="ShieldTrade demo script")
    p.add_argument("--ticker", default="AAPL")
    p.add_argument("--shares", type=int, default=5)
    p.add_argument("--price",  type=float, default=150.0)
    p.add_argument("--skip-openclaw", action="store_true", help="Skip OpenClaw demo (faster)")
    p.add_argument("--skip-pipeline", action="store_true", help="Skip pipeline demo")
    args = p.parse_args()

    print(_bold("\n🛡️  ShieldTrade — Live Integration Demo"))
    print("  ArmorIQ + OpenClaw + deterministic policy enforcement\n")

    # 1. ArmorIQ
    demo_armoriq(args.ticker, args.shares)

    # 2. OpenClaw
    if not args.skip_openclaw:
        demo_openclaw()
    else:
        _info("OpenClaw demo skipped (--skip-openclaw)")

    # 3. Full pipeline
    if not args.skip_pipeline:
        demo_pipeline(args.ticker, args.shares, args.price)
    else:
        _info("Pipeline demo skipped (--skip-pipeline)")

    _banner("Demo complete")
    print(_g("  All integrations verified. Check:"))
    print("  • ArmorIQ dashboard : https://app.armoriq.ai")
    print("  • output/trade-logs : execution log with ArmorIQ token embedded")
    print("  • output/reports    : analyst recommendation")
    print()


if __name__ == "__main__":
    main()
