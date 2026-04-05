#!/usr/bin/env node
/**
 * ArmorIQ Bridge — CLI wrapper around the @armoriq/sdk for Python integration.
 *
 * Exposes real ArmorIQ intent token generation and verification as subcommands
 * callable from Python scripts via subprocess.  All output is valid JSON to stdout.
 *
 * Commands:
 *   capture-token  --agent <id> --goal <text> --steps <json> [--policy <json>] [--ttl <s>]
 *   verify-token   --token <json_str>
 *   delegate       --ticker <T> --shares <n> --max-usd <usd> [--side buy|sell]
 *
 * Exit 0 = success, exit 1 = error (prints {"error": "<msg>"} to stdout).
 */
"use strict";

const path = require("path");
const SDK_PATH = path.join(
  "/Users/karthikeyadevaraj/.nvm/versions/node/v24.14.1/lib/node_modules/@armoriq/sdk/dist/client.js"
);

const ARMORIQ_API_KEY =
  process.env.ARMORIQ_API_KEY ||
  "ak_live_54f21675be146901a5dee498b75d1ff08d4cd91b1cdfb9cfa40f82db66b51a21";
const DEFAULT_USER_ID = "shieldtrade-user";
const DEFAULT_CONTEXT = "shieldtrade";

// Silence the SDK's noisy console.log calls by overriding temporarily
const _origLog = console.log;
console.log = () => {};
const { ArmorIQClient } = require(SDK_PATH);
console.log = _origLog;

function makeClient(agentId) {
  // Also silence SDK init log
  const _l = console.log;
  console.log = () => {};
  const client = new ArmorIQClient({
    apiKey: ARMORIQ_API_KEY,
    userId: DEFAULT_USER_ID,
    agentId: agentId || "shieldtrade-pipeline",
    contextId: DEFAULT_CONTEXT,
  });
  console.log = _l;
  return client;
}

function ok(data) {
  process.stdout.write(JSON.stringify(data) + "\n");
  process.exit(0);
}

function fail(msg) {
  process.stdout.write(JSON.stringify({ error: msg }) + "\n");
  process.exit(1);
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) {
      const key = argv[i].slice(2);
      const val = argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[++i] : true;
      args[key] = val;
    }
  }
  return args;
}

// ── capture-token ────────────────────────────────────────────────────────────

async function cmdCaptureToken(args) {
  const agentId = args["agent"] || "shieldtrade-pipeline";
  const goal = args["goal"];
  if (!goal) return fail("--goal is required");

  let steps = [];
  if (args["steps"]) {
    try { steps = JSON.parse(args["steps"]); } catch { return fail("--steps must be valid JSON"); }
  }

  let policy = { allow: ["bash", "write", "read", "web_fetch"] };
  if (args["policy"]) {
    try { policy = JSON.parse(args["policy"]); } catch { return fail("--policy must be valid JSON"); }
  }

  const ttl = parseInt(args["ttl"] || "300", 10);

  const client = makeClient(agentId);

  // Silence noisy SDK console during API calls
  const _l = console.log;
  console.log = () => {};
  try {
    const planCapture = client.capturePlan("proxy/local-ollama", goal, {
      goal,
      steps: steps.length > 0 ? steps : [{ action: "bash", mcp: "shell", params: { goal } }],
    });

    const token = await client.getIntentToken(planCapture, policy, ttl);
    console.log = _l;
    ok({
      token_id: token.tokenId,
      plan_id: token.planId,
      plan_hash: token.planHash,
      composite_identity: token.compositeIdentity,
      issued_at: token.issuedAt,
      expires_at: token.expiresAt,
      policy,
      agent_id: agentId,
      goal,
      step_count: steps.length,
      raw: token,
    });
  } catch (e) {
    console.log = _l;
    fail(`Intent token issuance failed: ${e.message}`);
  }
}

// ── verify-token ─────────────────────────────────────────────────────────────

async function cmdVerifyToken(args) {
  const tokenStr = args["token"];
  if (!tokenStr) return fail("--token is required");

  let tokenData;
  try { tokenData = JSON.parse(tokenStr); } catch { return fail("--token must be valid JSON"); }

  const agentId = tokenData.agent_id || "shieldtrade-pipeline";
  const client = makeClient(agentId);

  const _l = console.log; console.log = () => {};
  try {
    const result = await client.verifyToken(tokenData.raw || tokenData);
    console.log = _l;
    ok({ valid: true, token_id: tokenData.token_id, plan_id: tokenData.plan_id, result });
  } catch (e) {
    console.log = _l;
    // Token verification failure is a valid outcome, not a crash
    ok({ valid: false, token_id: tokenData.token_id, reason: e.message });
  }
}

// ── delegate ─────────────────────────────────────────────────────────────────

async function cmdDelegate(args) {
  const ticker  = (args["ticker"] || "").toUpperCase();
  const shares  = parseInt(args["shares"] || "0", 10);
  const maxUsd  = parseFloat(args["max-usd"] || "0");
  const side    = (args["side"] || "buy").toLowerCase();

  if (!ticker) return fail("--ticker is required");
  if (!shares) return fail("--shares must be > 0");
  if (!maxUsd)  return fail("--max-usd must be > 0");

  // Use risk_manager as issuer, trader as target
  const issuerClient = makeClient("shieldtrade-risk-manager");
  const _l = console.log; console.log = () => {};

  try {
    const planCapture = issuerClient.capturePlan(
      "proxy/local-ollama",
      `Delegate ${side} authority for ${shares} shares of ${ticker} (max $${maxUsd}) to trader agent`,
      {
        goal: `Bounded delegation: ${side} ${ticker} up to ${shares} shares / $${maxUsd}`,
        steps: [
          {
            action: "submit_order",
            mcp: "alpaca",
            params: { ticker, qty: shares, side, max_usd: maxUsd },
          },
        ],
      }
    );

    const delegationPolicy = {
      allow: ["submit_order"],
      deny: ["bash", "read", "write"],
      constraints: {
        ticker,
        max_shares: shares,
        max_usd: maxUsd,
        side,
      },
    };

    const token = await issuerClient.getIntentToken(planCapture, delegationPolicy, 300);
    console.log = _l;

    ok({
      delegation_token_id: token.tokenId,
      plan_id: token.planId,
      plan_hash: token.planHash,
      issued_by: "risk_manager",
      issued_to: "trader",
      ticker,
      max_shares: shares,
      max_usd: maxUsd,
      side,
      issued_at: token.issuedAt,
      expires_at: token.expiresAt,
      composite_identity: token.compositeIdentity,
      armoriq_verified: true,
      raw: token,
    });
  } catch (e) {
    console.log = _l;
    fail(`Delegation token issuance failed: ${e.message}`);
  }
}

// ── Main ─────────────────────────────────────────────────────────────────────

const [, , command, ...rest] = process.argv;
const args = parseArgs(rest);

(async () => {
  switch (command) {
    case "capture-token": return cmdCaptureToken(args);
    case "verify-token":  return cmdVerifyToken(args);
    case "delegate":      return cmdDelegate(args);
    default:
      fail(
        `Unknown command: ${command}. Available: capture-token, verify-token, delegate`
      );
  }
})();
