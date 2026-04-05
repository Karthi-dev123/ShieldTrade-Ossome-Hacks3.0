# ShieldTrade contracts (canonical)

This document is the **schema freeze** for machine-readable handoffs between Analyst → Risk Manager → Trader and for calls into `scripts/policy_engine.py` and `scripts/alpaca_bridge.py`. Field names and CLI shapes match the **current code** in those scripts.

## Artifact locations

| Stage        | Directory                 | Filename pattern (suggested)        |
|-------------|---------------------------|-------------------------------------|
| Analyst     | `output/reports/`         | `{TICKER}-recommendation.json`      |
| Risk        | `output/risk-decisions/`  | `delegation-{TICKER}-{token_id}.json` |
| Trader      | `output/trade-logs/`      | `execution-{TICKER}-{ISO_TIMESTAMP}.json` |

Directories are created by writers as needed (policy engine already ensures `output/trade-logs/` for daily spend).

---

## 1. Analyst recommendation (`output/reports/*.json`)

Produced by the analyst stage. Consumed by risk when approving a proposed size and caps.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | recommended | e.g. `"1.0"` |
| `ticker` | string | yes | Uppercase symbol, must be in policy allow-list |
| `recommendation` | string | yes | e.g. `BUY`, `SELL`, `HOLD` |
| `confidence` | number | optional | 0–1 |
| `reasoning` | string | optional | Human or model rationale |
| `current_price` | number | optional | From market data at analysis time |
| `proposed_side` | string | optional | `buy` or `sell` (defaults from `recommendation` in orchestration) |
| `proposed_shares` | integer | optional | Suggested size for risk to cap (risk may reduce) |
| `timestamp` | string (ISO 8601) | yes | UTC recommended |

### Example

```json
{
  "schema_version": "1.0",
  "ticker": "AAPL",
  "recommendation": "BUY",
  "confidence": 0.75,
  "reasoning": "Uptrend with volume confirmation on 30d bars.",
  "current_price": 198.5,
  "proposed_side": "buy",
  "proposed_shares": 5,
  "timestamp": "2026-04-04T12:00:00+00:00"
}
```

---

## 2. Delegation token (`output/risk-decisions/*.json`)

**Must** match what `policy_engine.check_delegation()` validates. This is the only supported delegation shape for automation and tests.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issued_by` | string | yes | Must be `"risk_manager"` when `require_risk_approval` is true in policy |
| `issued_to` | string | yes | Must be `"trader"` |
| `ticker` | string | yes | Symbol for the delegated order |
| `max_usd` | number | yes | Notional cap for this delegation (policy file may add further caps) |
| `max_shares` | integer | yes | Share cap for this delegation |
| `issued_at` | string (ISO 8601) | yes | Issuance time; used with `delegation.trader_delegation.expiry_minutes` |
| `token_id` | string | yes | Unique id (UUID or stable id for audit) |

Optional extensions (ignored by `check_delegation` today but useful for audit):

| Field | Type | Description |
|-------|------|-------------|
| `side` | string | `buy` or `sell` |
| `recommendation_path` | string | Path to analyst JSON that was approved |
| `policy_snapshot_version` | string | e.g. policy `metadata.version` |

### Example

```json
{
  "issued_by": "risk_manager",
  "issued_to": "trader",
  "ticker": "AAPL",
  "max_usd": 1000,
  "max_shares": 5,
  "issued_at": "2026-04-04T12:05:00+00:00",
  "token_id": "del_aapl_550e8400",
  "side": "buy",
  "recommendation_path": "output/reports/AAPL-recommendation.json"
}
```

---

## 3. Trade request (input to `validate-all`)

Passed as a **single JSON object** (stringified) to:

`python scripts/policy_engine.py validate-all '<json>'`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent` | string | yes | e.g. `analyst`, `risk_manager`, `trader` |
| `tool` | string | yes | Must match `allowed_tools` / not be in `denied_tools` per `config/shieldtrade-policies.yaml` |
| `ticker` | string | when trading | Symbol |
| `shares` | integer | when sizing | Share count (triggers share limit checks if positive) |
| `amount_usd` | number | when sizing | Notional (triggers per-order and daily checks if positive) |
| `domain` | string | optional | API host; default in CLI is `paper-api.alpaca.markets` |
| `delegation` | object | required for `trader` + `place_order` | Same shape as §2 |

### Example (trader placing order)

```json
{
  "agent": "trader",
  "tool": "place_order",
  "ticker": "AAPL",
  "shares": 5,
  "amount_usd": 990.0,
  "domain": "paper-api.alpaca.markets",
  "delegation": {
    "issued_by": "risk_manager",
    "issued_to": "trader",
    "ticker": "AAPL",
    "max_usd": 1000,
    "max_shares": 5,
    "issued_at": "2026-04-04T12:05:00+00:00",
    "token_id": "del_aapl_550e8400"
  }
}
```

---

## 4. Policy engine JSON outputs

### 4.1 Single check (`check-role`, `check-delegation`, or one check from code)

```json
{
  "check": "delegation",
  "result": "PASS",
  "detail": "Delegation token del_aapl_550e8400 is valid (age 42s)"
}
```

### 4.2 Full trade validation (`check-trade`, `validate-all`)

Top-level fields emitted by `validate_trade()`:

| Field | Type | Description |
|-------|------|-------------|
| `decision` | string | `ALLOW` or `BLOCK` |
| `timestamp` | string | ISO UTC |
| `agent` | string | From request |
| `tool` | string | From request |
| `ticker` | string | From request |
| `checks` | array | List of `{check, result, detail}` |
| `blocked_reasons` | array of string | Details for failed checks |
| `policy_check_id` | string or null | Audit id from logger |

**Note:** On `ALLOW` with positive `amount_usd`, the engine records spend in `output/trade-logs/daily-spend.json`.

---

## 5. Trade execution log (`output/trade-logs/execution-*.json`)

Written by the trader stage after a successful bridge call. Aligns with `alpaca_bridge.cmd_order` response plus audit fields.

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | e.g. `"1.0"` |
| `timestamp` | string | ISO UTC when logged |
| `delegation_token_id` | string | From delegation `token_id` |
| `policy_check_id` | string (optional) | From last `validate_trade` / `check-trade` result |
| `armoriq_token` | string (optional) | HMAC-SHA256 signed intent token from `armoriq_stub.sign_intent()`; attached to every paper order by `alpaca_bridge.cmd_order()` |
| `order` | object | Alpaca bridge result: `order_id`, `symbol`, `qty`, `side`, `type`, `status`, `submitted_at`, `time_in_force` |

### Example

```json
{
  "schema_version": "1.0",
  "timestamp": "2026-04-04T12:06:30+00:00",
  "delegation_token_id": "del_aapl_550e8400",
  "policy_check_id": "row_abc123",
  "armoriq_token": "v1.eyJ0aWNrZXIiOiJBQVBMIiwi….<hmac>",
  "order": {
    "order_id": "…",
    "symbol": "AAPL",
    "qty": "5",
    "side": "buy",
    "type": "market",
    "status": "accepted",
    "submitted_at": "2026-04-04T12:06:29+00:00",
    "time_in_force": "day"
  }
}
```

---

## 6. CLI reference (repo root)

### `scripts/policy_engine.py`

| Command | Arguments | Notes |
|---------|-----------|--------|
| `check-trade` | `<agent> <tool> <ticker> <shares> <amount_usd> [domain]` | Positional only; domain defaults to paper API host |
| `check-role` | `<agent> <tool>` | Emits one check object |
| `check-delegation` | `'<json>'` | One JSON object string |
| `validate-all` | `'<json>'` | Full request object (§3) |

Examples:

```bash
python scripts/policy_engine.py check-role risk_manager approve_trade
python scripts/policy_engine.py check-trade risk_manager approve_trade AAPL 5 990.00
python scripts/policy_engine.py check-delegation '{"issued_by":"risk_manager","issued_to":"trader","ticker":"AAPL","max_usd":1000,"max_shares":5,"issued_at":"2026-04-04T12:05:00+00:00","token_id":"del_1"}'
```

### `scripts/alpaca_bridge.py`

| Command | Arguments |
|---------|-----------|
| `account` | (none) |
| `positions` | (none) |
| `quote` | `<SYMBOL>` |
| `bars` | `<SYMBOL> [TIMEFRAME] [LIMIT]` |
| `order` | `<SYMBOL> <QTY> <SIDE> [POLICY_CHECK_ID]` |

Examples:

```bash
python scripts/alpaca_bridge.py quote AAPL
python scripts/alpaca_bridge.py bars AAPL 1Day 30
python scripts/alpaca_bridge.py order AAPL 5 buy
```

### `scripts/orchestrate_pipeline.py`

End-to-end Analyst → Risk → Trader using the schemas above. Risk-stage `validate_trade` runs with **no daily-spend write**; trader-stage records spend on `ALLOW` unless `--dry-run`.

```bash
python scripts/orchestrate_pipeline.py AAPL --shares 5 --assume-price 100 --dry-run
python scripts/orchestrate_pipeline.py AAPL --shares 5   # live quote + paper order if policy allows
```

Execution logs from `--dry-run` include `"dry_run": true` and an `order` object with `"status": "dry_run"`.

---

## 7. Implementation notes

### Delegation cap enforcement (implemented)

`check_delegation()` enforces **two tiers** of caps:

1. **YAML ceiling check** — the token's own `max_shares` / `max_usd` must not exceed `delegation.trader_delegation.max_shares_per_delegation` / `max_usd_per_delegation` from policy YAML.  A token issued above the ceiling is rejected at validation time.
2. **Request cap check** — the actual requested `shares` / `amount_usd` must not exceed the token's own `max_shares` / `max_usd`.

`build_delegation()` in `orchestrate_pipeline.py` also caps delegation values at issuance against the same YAML ceilings so that an over-scoped token is never written to disk.

### ArmorIQ intent tokens (implemented)

`scripts/armoriq_stub.py` issues HMAC-SHA256 signed intent tokens.  `alpaca_bridge.cmd_order()` attaches the token to every paper order.  The token appears in trade execution logs as `armoriq_token` (see §5).

### Tool name alignment

Policy YAML maps abstract tool names (`approve_trade`, `market_data_fetch`, `place_order`, …).  CLI callers and agent skills must pass the **exact strings** that appear under `agent_roles.*.allowed_tools` / `denied_tools`.  See `skills/shieldtrade-*/SKILL.md` for per-agent examples.

### Remaining limitations

- Earnings blackout event list in YAML is static (hardcoded dates); it is not auto-updated from a live earnings calendar.
- `validate_trade` does not check `shares <= delegation.max_shares` inside the aggregate validator when `delegation` is provided via a raw dict CLI call without the `shares` kwarg — callers must pass `shares=` explicitly to `check_delegation` for that check to fire.

When behavior changes, update this file and the tests under `tests/`.
