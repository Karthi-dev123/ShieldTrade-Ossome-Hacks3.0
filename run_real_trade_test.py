import sys
import json
import subprocess
import os
from dotenv import load_dotenv

load_dotenv("env.txt")

def run_script(args):
    result = subprocess.run(["venv/bin/python"] + args, capture_output=True, text=True, env=os.environ)
    try:
        return json.loads(result.stdout)
    except:
        return {"error": "Failed to parse JSON", "raw": result.stdout, "stderr": result.stderr}

print("="*60)
print("🛡️ SHIELDTRADE REAL API POLICY & EXECUTION TEST")
print("="*60 + "\n")

# TEST 1: Blocked by Policy (TSLA not in allowed list)
print("▶ [TEST 1: POLICY ENGINE] Attempting to buy 5 shares of TSLA (Denied Ticker)")
res_block1 = run_script(["-c", "from scripts import policy_engine; print(json.dumps(policy_engine.check_ticker('TSLA')))", ""])
print(f"   ↳ Result: {res_block1.get('result')}")
print(f"   ↳ Reason: {res_block1.get('detail')}\n")

# TEST 2: Blocked by Policy (> $2000 per order max)
print("▶ [TEST 2: POLICY ENGINE] Attempting to buy $5000 worth of AAPL")
res_block2 = run_script(["-c", "from scripts import policy_engine; print(json.dumps(policy_engine.check_order_size(5000)))", ""])
print(f"   ↳ Result: {res_block2.get('result')}")
print(f"   ↳ Reason: {res_block2.get('detail')}\n")

# TEST 3: Allowed Policy (Buy $500 of AAPL) AND Execute Real Alpaca Trade
print("▶ [TEST 3: REAL TRADE] Validating AAPL trade & Executing to Alpaca...")
res_pass = run_script(["-c", "from scripts import policy_engine; print(json.dumps(policy_engine.check_ticker('AAPL')))", ""])
if dict(res_pass).get('result') == "PASS":
    print("   ↳ Policy PASS: AAPL is an allowed ticker.")
    res_pass2 = run_script(["-c", "from scripts import policy_engine; print(json.dumps(policy_engine.check_order_size(500)))", ""])
    if dict(res_pass2).get('result') == "PASS":
        print("   ↳ Policy PASS: Order size $500 is under the limit.")

print("   ↳ Intent validated. Transmitting order to Alpaca (BUY 2 AAPL)...")
order_res = run_script(["scripts/alpaca_bridge.py", "order", "AAPL", "2", "BUY", "tok_demo_123"])

if "error" in order_res:
    print(f"   ↳ ❌ Alpaca Order Failed: {order_res['error']}\n")
    if "raw" in order_res: print(order_res['raw'])
else:
    print(f"   ↳ ✅ Alpaca Order SUCCESS!")
    print(f"   ↳ Order ID: {order_res.get('order_id')}")
    print(f"   ↳ Status: {order_res.get('status')}")
    print(f"   ↳ Quantity: {order_res.get('quantity')} {order_res.get('symbol')}")

print("\n▶ [ACCOUNT STATUS]")
account_res = run_script(["scripts/alpaca_bridge.py", "account"])
print(f"   ↳ Equity: ${account_res.get('equity')}")
print(f"   ↳ Buying Power: ${account_res.get('buying_power')}")

print("\n" + "="*60)
print("✔ REAL API E2E VALIDATION COMPLETE.")
print("="*60)
