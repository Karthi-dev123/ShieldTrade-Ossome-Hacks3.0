# ShieldTrade — Troubleshooting Guide

Quick reference for the most common startup, runtime, and test failures. Each section lists the symptom, the cause, and the exact fix.

---

## 1. Services Won't Start

### Port 4000 already in use
```
Error: listen EADDRINUSE: address already in use :::4000
```
**Cause:** A previous proxy process is still running.  
**Fix:** `start-all.py` detects and reuses an existing process on port 4000. If you want a clean restart:
```bash
lsof -ti :4000 | xargs kill -9
python scripts/start-all.py
```

### Port 18789 already in use
Same pattern for the OpenClaw gateway:
```bash
lsof -ti :18789 | xargs kill -9
python scripts/start-all.py
```

### `python scripts/start-all.py` exits immediately
**Cause:** Missing Node.js dependencies (`node_modules` not present).  
**Fix:**
```bash
npm install
python scripts/start-all.py
```

---

## 2. Ollama / Proxy Issues

### `curl http://localhost:4000/v1/models` returns an error or empty list
**Cause:** Ollama is not running, or `OLLAMA_BASE_URL` points to the wrong host.  
**Fix:**
1. Start Ollama: `ollama serve` (separate terminal)
2. Verify it responds: `curl http://localhost:11434/v1/models`
3. Check `.env`: `OLLAMA_BASE_URL=http://localhost:11434`
4. Restart the proxy: `python scripts/start-all.py`

### Chat completions hang or return `"Ollama API stream ended without a final response"`
**Cause:** The local model returned a streaming response without a `[DONE]` sentinel.  
**Fix:** This is handled automatically by `scripts/proxy.js` — the proxy injects `data: [DONE]\n\n` when the Ollama stream closes without it. If you still see this, ensure the proxy was restarted after the latest code pull:
```bash
lsof -ti :4000 | xargs kill -9
python scripts/start-all.py
```

### Model not found / wrong model name
**Cause:** `OLLAMA_MODEL` in `.env` names a model that hasn't been pulled.  
**Fix:**
```bash
ollama pull qwen3:30b-a3b     # or whatever OLLAMA_MODEL is set to
```
Verify with: `ollama list`

---

## 3. OpenClaw Gateway Issues

### `openclaw: command not found`
**Fix:**
```bash
npm install -g @openclaw/cli
# or run via npx:
npx openclaw health
```

### `openclaw health` returns 401 Unauthorized
**Cause:** Wrong or missing gateway token.  
**Fix:** The token lives in `config/openclaw.json` under `gateway.auth.token`. Export it:
```bash
export OPENCLAW_GATEWAY_TOKEN=$(python -c "import json; c=json.load(open('config/openclaw.json')); print(c['gateway']['auth']['token'])")
OPENCLAW_CONFIG_PATH="$PWD/config/openclaw.json" openclaw health
```

### Gateway starts but agents get no response
**Cause:** Gateway is up but the proxy (port 4000) is down, so LLM calls fail silently.  
**Fix:** Verify both services: `curl http://localhost:4000/v1/models` and `openclaw health`.

---

## 4. Pipeline Errors

### `Missing required env var: ALPACA_API_KEY`
**Cause:** Live order path requires Alpaca credentials.  
**Fix:** Add to `.env`:
```
ALPACA_API_KEY=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
ARMORIQ_API_KEY=any_non_empty_string
```
Or use `--dry-run` to skip Alpaca entirely:
```bash
python scripts/orchestrate_pipeline.py AAPL --shares 5 --assume-price 100 --dry-run
```

### `Missing required env var: ARMORIQ_API_KEY`
**Cause:** `alpaca_bridge.cmd_order()` requires this to be set before issuing an ArmorIQ intent token.  
**Fix:** Set any non-empty value in `.env`:
```
ARMORIQ_API_KEY=local-stub-secret
```
This is intentionally not a real external service — it signs tokens locally via HMAC-SHA256.

### Pipeline blocked at `risk` stage — `market_hours` check FAIL
```json
{ "check": "market_hours", "result": "FAIL", "detail": "Market closed (18:45 EDT)" }
```
**Cause:** `market_hours_only.enabled: true` in `config/shieldtrade-policies.yaml` blocks trades outside 09:30–16:00 ET Mon–Fri.  
**Fix (for testing/demo):** Use `--dry-run` — the policy check still runs and logs ALLOW/BLOCK, but no real order is placed. Market hours check applies identically in dry-run mode:
```bash
python scripts/orchestrate_pipeline.py AAPL --shares 5 --assume-price 100 --dry-run
```
To disable market hours enforcement temporarily (not recommended for production demo), set `enabled: false` in the YAML.

### Pipeline blocked at `risk` stage — `earnings_blackout` check FAIL
**Cause:** `earnings_blackout.enabled: true` and current time is within the 30-minute window around a listed earnings event.  
**Fix:** This is correct policy behavior. To test outside a blackout window, use a date outside the event window, or set `enabled: false` in `config/shieldtrade-policies.yaml` (default is `false`).

### Pipeline blocked — `ticker not in allowed list`
**Cause:** The ticker isn't in `trading.approved_tickers.symbols` in the YAML.  
**Allowed tickers:** AAPL, MSFT, GOOGL, AMZN, NVDA  
**Fix:** Use an approved ticker, or add the ticker to the YAML allow-list.

### Pipeline blocked — `order_size` check FAIL
**Cause:** `shares × price > per_order_max_usd` (default: $2,000).  
**Example:** 60 shares × $100 = $6,000 > $2,000 cap.  
**Fix:** Reduce shares, or increase `per_order_max_usd` in the YAML for testing.

### Delegation token expired mid-test
**Cause:** `delegation.trader_delegation.expiry_minutes: 5` — tokens expire after 5 minutes.  
**Fix:** This is working as designed. Re-run the pipeline to generate a fresh token. In tests, use `expiry_minutes: 30` in your mock policy fixture.

### Delegation max_shares or max_usd exceeds policy ceiling
```
"Delegation max_shares 150 exceeds policy ceiling 100"
```
**Cause:** `build_delegation()` caps at issuance; `check_delegation()` also enforces the YAML ceiling on any incoming token.  
**Fix:** Reduce `--shares` to stay within `delegation.trader_delegation.max_shares_per_delegation` (default: 100) and `max_usd_per_delegation` (default: $2,000).

---

## 5. Daily Spend Issues

### Trade blocked — `daily_limit` check FAIL even after restart
**Cause:** `output/trade-logs/daily-spend.json` persists across runs and accumulates spend for the current Eastern-time date.  
**Fix:** Delete the ledger to reset:
```bash
rm output/trade-logs/daily-spend.json
```

### Daily spend bucket seems off by one day
**Cause (historical):** Pre-Phase 4 builds used UTC for the date bucket; the fix uses `America/New_York` (ET).  
**Fix:** Ensure you are running the latest `scripts/policy_engine.py`. Verify with `python -m pytest tests -q`.

---

## 6. Test Failures

### `ModuleNotFoundError: No module named 'yaml'` / `'filelock'` / `'alpaca'`
**Fix:**
```bash
pip install -r requirements.txt
```

### Tests fail with `No module named 'scripts.policy_engine'`
**Cause:** Tests must be run from the repo root, not from inside `tests/`.  
**Fix:**
```bash
cd /path/to/ShieldTrade-Ossome-Hacks3.0
python -m pytest tests -q
```

### `test_armoriq_*` tests fail with `EnvironmentError: Missing required env var: ARMORIQ_API_KEY`
**Cause:** The test fixture uses `monkeypatch.setenv` — this only works when running through pytest.  
**Fix:** Run via pytest, not by importing the module directly:
```bash
python -m pytest tests/test_armoriq_stub.py -v
```

### Unexpected BLOCK in test — `market_hours` FAIL
**Cause:** Your mock policy fixture doesn't disable market hours.  
**Fix:** Add to your mock policy:
```python
"time_restrictions": {"market_hours_only": {"enabled": False}}
```

---

## 7. Output Artifacts

### `output/` directory is empty / artifacts not appearing
**Cause:** Pipeline exited before writing (check the JSON return for `"ok": false` and `"stopped_at"`).  
**Fix:** Read the `blocked_reasons` in the output and address the failing check.

### `FileNotFoundError` when using `--skip-analyst`
**Cause:** No existing report for that ticker at `output/reports/{TICKER}-recommendation.json`.  
**Fix:** Run without `--skip-analyst` first to generate the report, then use the flag on subsequent runs.

---

## 8. Quick Health Check Sequence

Run these in order to confirm the full stack is working:

```bash
# 1. Python dependencies
python -c "import yaml, filelock, alpaca; print('deps ok')"

# 2. Policy engine loads
python -c "from scripts import policy_engine; p = policy_engine.load_policy(); print('policy ok:', p['metadata']['version'])"

# 3. Proxy responds
curl -s http://localhost:4000/v1/models | python -m json.tool | head -5

# 4. Deterministic pipeline (no credentials needed)
python scripts/orchestrate_pipeline.py AAPL --shares 5 --assume-price 100 --dry-run

# 5. Full test suite
python -m pytest tests -q
```

Expected final line: `41 passed`
