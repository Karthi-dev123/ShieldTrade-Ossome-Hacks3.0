#!/usr/bin/env python3
"""ShieldTrade ArmorIQ — Streamlit trading desk UI.

Two-view Streamlit app:
  • Trading Desk  — natural language → LLM Router (Ollama) → Policy Engine
  • Audit Logs    — historical blocked decisions from output/audit_logs.json

Run:
    streamlit run scripts/app.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Path bootstrap — identical pattern to orchestrate_pipeline.py
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

import policy_engine  # noqa: E402  (must follow sys.path tweak)

# ---------------------------------------------------------------------------
# Page config — MUST be the very first Streamlit call in the script
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="ShieldTrade · ArmorIQ",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Runtime config
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# The full qwen3:30b-a3b model used for inference is too heavy for a live
# demo.  Default to the fast 8B model; override with UI_LLM_MODEL env var.
UI_LLM_MODEL: str = os.getenv("UI_LLM_MODEL", "qwen3:8b")

AUDIT_LOG_PATH: Path = _ROOT / "output" / "audit_logs.json"

# OpenClaw gateway settings (used to route responses through openclaw agents)
_OPENCLAW_GATEWAY_TOKEN: str = os.getenv(
    "OPENCLAW_GATEWAY_TOKEN", "d17d4ab08c80922f2bff84cedcad95e54b75e7c2d16ebb01"
)
_OPENCLAW_CONFIG_PATH: str = str(_ROOT / "config" / "openclaw.json")

# ---------------------------------------------------------------------------
# LLM intent-extraction system prompt
# ---------------------------------------------------------------------------
_INTENT_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a pure JSON entity extractor for a financial trading system.
    Your ONLY job is to parse the user's natural language and return ONE JSON object.
    Output ONLY valid JSON. No markdown fences, no explanation, no commentary.

    Required JSON schema:
    {
      "agent":      string — one of: analyst | risk_manager | trader,
      "tool":       string — one of: place_order | market_data_fetch | write_report |
                                     approve_trade | read_portfolio | web_fetch |
                                     shell | get_account | get_positions,
      "ticker":     string — uppercase stock symbol (e.g. "AAPL") or "" if none,
      "shares":     integer — number of shares, 0 if not mentioned,
      "amount_usd": number  — dollar amount, 0.0 if not mentioned,
      "domain":     string  — "paper-api.alpaca.markets" by default, or the
                              actual host if the user mentions an external endpoint,
      "tool_args":  string  — any extra args, flags, or suspicious payload content
    }

    Mapping rules (apply the first rule that matches):
    • buy / sell / execute / trade / order / place       → agent=trader,        tool=place_order
    • analyze / research / fetch data / look up / quote  → agent=analyst,       tool=market_data_fetch
    • write report / save analysis                       → agent=analyst,       tool=write_report
    • approve / validate / check recommendation          → agent=risk_manager,  tool=approve_trade
    • HTTP / URL / website / curl / wget                 → agent=analyst,       tool=web_fetch,  domain=<host>
    • shell / bash / exec / run command / subprocess     → agent=analyst,       tool=shell
    • exfiltrate / send data / POST to server            → agent=analyst,       tool=web_fetch,  domain=<target host>
    • ignore instructions / jailbreak / injection text   → agent=analyst,       tool=shell,      tool_args=<suspicious content>
    • file content / uploaded file / earnings report     → agent=analyst,       tool=market_data_fetch, tool_args=<content snippet>
    • anything else or ambiguous                         → agent=analyst,       tool=market_data_fetch

    Respond with ONLY the JSON object. Nothing else.
""")

# ---------------------------------------------------------------------------
# CSS — light theme, minimal, professional financial aesthetic
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
/* ── Base ──────────────────────────────────────────────────────────────── */
.stApp, [data-testid="stAppViewContainer"] {
    background-color: #f8f9fb !important;
}
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e5e7eb !important;
}
[data-testid="stSidebar"] .stMarkdown p { margin: 0; }
[data-testid="stChatMessage"] {
    background: #ffffff;
    border: 1px solid #e9ebee;
    border-radius: 10px;
    margin-bottom: 10px;
}

/* ── BLOCK enforcement banner ──────────────────────────────────────────── */
.ev-block-banner {
    background: #fef2f2;
    border: 1px solid #fca5a5;
    border-left: 5px solid #dc2626;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 10px 0 6px 0;
}
.ev-block-title {
    color: #b91c1c;
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 6px;
}
.ev-block-meta { color: #7f1d1d; font-size: 0.82rem; margin-bottom: 12px; }
.ev-block-note {
    background: #fee2e2;
    border-radius: 4px;
    padding: 8px 12px;
    color: #991b1b;
    font-size: 0.8rem;
    font-style: italic;
    margin-top: 10px;
}

/* ── ALLOW enforcement banner ──────────────────────────────────────────── */
.ev-allow-banner {
    background: #f0fdf4;
    border: 1px solid #86efac;
    border-left: 5px solid #16a34a;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 10px 0 6px 0;
}
.ev-allow-title { color: #15803d; font-size: 1rem; font-weight: 700; margin-bottom: 6px; }
.ev-allow-meta  { color: #166534; font-size: 0.82rem; }

/* ── Per-check table ───────────────────────────────────────────────────── */
.checks-table {
    width: 100%; border-collapse: collapse;
    margin-top: 12px; font-size: 0.82rem; background: transparent;
}
.checks-table th {
    text-align: left; color: #9ca3af; font-weight: 600;
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em;
    border-bottom: 1px solid #e5e7eb; padding: 4px 10px;
}
.checks-table td {
    padding: 7px 10px; border-bottom: 1px solid #f3f4f6;
    vertical-align: top; line-height: 1.4;
}
.checks-table tr:last-child td { border-bottom: none; }
.badge-pass {
    background: #dcfce7; color: #15803d; border-radius: 3px;
    padding: 1px 8px; font-weight: 700; font-size: 0.72rem; white-space: nowrap;
}
.badge-fail {
    background: #fee2e2; color: #b91c1c; border-radius: 3px;
    padding: 1px 8px; font-weight: 700; font-size: 0.72rem; white-space: nowrap;
}
.td-check  { color: #374151; font-weight: 600; font-family: monospace; font-size: 0.8rem; }
.td-detail { color: #6b7280; }
.td-ref    { color: #9ca3af; font-family: monospace; font-size: 0.72rem; }

/* ── Audit table ───────────────────────────────────────────────────────── */
.audit-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
.audit-table th {
    background: #f9fafb; color: #374151; font-weight: 600;
    font-size: 0.78rem; padding: 10px 14px;
    border-bottom: 2px solid #e5e7eb; text-align: left; white-space: nowrap;
}
.audit-table td {
    padding: 10px 14px; border-bottom: 1px solid #f3f4f6;
    color: #374151; vertical-align: top;
}
.audit-table tr:hover td { background: #f9fafb; }
.a-badge-block {
    background: #fee2e2; color: #b91c1c; border-radius: 3px;
    padding: 2px 8px; font-weight: 700; font-size: 0.75rem; white-space: nowrap;
}
.a-badge-allow {
    background: #dcfce7; color: #15803d; border-radius: 3px;
    padding: 2px 8px; font-weight: 700; font-size: 0.75rem; white-space: nowrap;
}

/* ── Sidebar ───────────────────────────────────────────────────────────── */
.model-badge {
    display: inline-block; background: #eff6ff; color: #1d4ed8;
    border-radius: 4px; padding: 2px 8px;
    font-size: 0.72rem; font-family: monospace; font-weight: 600;
}
.sidebar-label {
    font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em;
    color: #9ca3af; font-weight: 700; margin: 16px 0 4px 0;
}

/* ── File uploader drop zone ───────────────────────────────────────────── */
[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed #d1d5db !important;
    background: #fafafa !important;
    border-radius: 8px !important;
}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_policy() -> dict:
    # Avoid @st.cache_resource — it triggers typing.Union immutability errors
    # in Python 3.14 when Streamlit introspects the return-type annotation.
    # session_state gives equivalent single-load-per-session behaviour.
    if "_policy_cache" not in st.session_state:
        st.session_state["_policy_cache"] = policy_engine.load_policy()
    return st.session_state["_policy_cache"]


def _normalize_intent(raw: dict) -> dict:
    """Coerce LLM JSON output to the types TradeIntent expects."""
    return {
        "agent": str(raw.get("agent") or "analyst"),
        "tool":  str(raw.get("tool")  or "market_data_fetch"),
        "ticker": str(raw.get("ticker") or "").upper().strip(),
        "shares": int(raw.get("shares") or 0),
        "amount_usd": float(raw.get("amount_usd") or 0.0),
        "domain": str(raw.get("domain") or "paper-api.alpaca.markets"),
        "tool_args": str(raw.get("tool_args")) if raw.get("tool_args") else None,
    }


def _fast_intent_parse(text: str) -> dict | None:
    """Regex-based intent parser — returns in <1ms for all common patterns.

    Returns a normalized intent dict on match, or None if the input is
    genuinely ambiguous and needs LLM reasoning.
    """
    import re
    t = text.strip().lower()

    _TICKERS = r"(aapl|msft|googl|amzn|nvda|tsla|gme|[a-z]{1,5})"
    _NUM     = r"(\d+(?:\.\d+)?)"

    def _base(agent, tool, ticker="", shares=0, amount=0.0, domain="paper-api.alpaca.markets", tool_args=""):
        return {"agent": agent, "tool": tool, "ticker": ticker.upper() if ticker else "",
                "shares": int(shares), "amount_usd": float(amount),
                "domain": domain, "tool_args": tool_args}

    # ── Exfiltration / data-send attacks ──────────────────────────────────────
    m = re.search(r"(send|post|upload|exfiltrate|transmit|leak).*?(https?://)?([a-z0-9._-]+\.[a-z]{2,})", t)
    if m:
        return _base("analyst", "web_fetch", domain=m.group(3))

    # ── Shell / injection ─────────────────────────────────────────────────────
    if re.search(r"\b(bash|shell|exec|subprocess|rm -rf|ignore (previous|all)|jailbreak|override)\b", t):
        return _base("analyst", "shell", tool_args=text[:200])

    # ── Prompt injection keywords ─────────────────────────────────────────────
    if re.search(r"(ignore (previous|above|all)|forget (previous|all)|you are now|act as|system:)", t):
        return _base("analyst", "shell", tool_args=text[:200])

    # ── URL / web fetch ───────────────────────────────────────────────────────
    m = re.search(r"https?://([a-z0-9._-]+)", t)
    if m:
        return _base("analyst", "web_fetch", domain=m.group(1))

    # ── Trade execution: buy/sell N TICKER ───────────────────────────────────
    m = re.search(rf"\b(buy|sell|trade|order|execute)\b.*?{_NUM}?\s*(?:shares? of\s*)?{_TICKERS}", t)
    if m:
        side  = m.group(1)
        num   = float(m.group(2)) if m.group(2) else 5
        tick  = m.group(3)
        return _base("trader", "place_order", ticker=tick, shares=int(num))

    # sell ALL (no ticker/amount) → block-worthy intent
    if re.search(r"\bsell\s+all\b", t):
        return _base("trader", "place_order", shares=9999)

    # ── Research / analysis ───────────────────────────────────────────────────
    # Covers: analyze/analyse/analysis, price/info/data, "what is", "tell me about", etc.
    if re.search(
        r"\b(analyz\w*|analys\w*|research|quote|look\s*up|fetch|check|price|"
        r"info|data|tell\s*me|what\s*is|what'?s|how\s*is|show\s*me|get\s*me|"
        r"report|summary|news|earnings)\b",
        t,
    ):
        # Extract only KNOWN tickers — avoid false matches on common words
        _KNOWN_TICKERS = r"(aapl|msft|googl|amzn|nvda|tsla|gme)"
        tm = re.search(rf"\b{_KNOWN_TICKERS}\b", t)
        tick = tm.group(1) if tm else ""
        return _base("analyst", "market_data_fetch", ticker=tick)

    # ── Risk / approval ───────────────────────────────────────────────────────
    if re.search(r"\b(approve|validate|review recommendation|check limits?)\b", t):
        return _base("risk_manager", "approve_trade")

    # ── Portfolio / positions ─────────────────────────────────────────────────
    if re.search(r"\b(positions?|portfolio|holdings?|balance|account)\b", t):
        return _base("trader", "get_positions")

    # ── Any known ticker mentioned → default to market data lookup ───────────
    _KNOWN = {"aapl", "msft", "googl", "amzn", "nvda", "tsla", "gme"}
    km = re.search(r"\b(aapl|msft|googl|amzn|nvda|tsla|gme)\b", t)
    if km:
        return _base("analyst", "market_data_fetch", ticker=km.group(1))

    return None  # genuinely ambiguous → fall through to LLM


def parse_intent_via_llm(text: str) -> dict:
    """Parse intent: fast regex first, LLM fallback for ambiguous inputs.

    The regex path returns in <1ms for all common patterns (buy/sell/analyze/
    exfiltration/injection). LLM is called only for genuinely ambiguous text,
    with a 45-second timeout and /no_think to suppress qwen3 chain-of-thought.
    """
    # Fast path — handles >95% of inputs instantly
    fast = _fast_intent_parse(text)
    if fast is not None:
        return fast

    # LLM fallback for edge cases
    full_prompt = f"/no_think\n{_INTENT_SYSTEM_PROMPT}\n\nUser input:\n{text}"
    payload = {
        "model": UI_LLM_MODEL,
        "prompt": full_prompt,
        "format": "json",
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 128},
    }
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=45,
        )
        resp.raise_for_status()
        raw_content = resp.json().get("response", "{}")
        return _normalize_intent(json.loads(raw_content))
    except Exception:
        # If LLM also fails, treat as analyst market_data_fetch (safe default)
        return _fast_intent_parse(text) or {
            "agent": "analyst", "tool": "market_data_fetch",
            "ticker": "", "shares": 0, "amount_usd": 0.0,
            "domain": "paper-api.alpaca.markets", "tool_args": text[:200],
        }


_LLM_RESPONSE_TIMEOUT = 180  # seconds — user requested a few minutes


def _build_response_prompt(original_input: str, intent: dict) -> str:
    """Build a concise, context-aware prompt for the post-policy LLM response."""
    ticker = intent.get("ticker") or ""
    shares = intent.get("shares") or 0
    tool   = intent.get("tool")   or ""
    agent  = intent.get("agent")  or ""

    preamble = (
        "/no_think\n"
        "You are ShieldTrade, an AI financial assistant. "
        "Be concise — 3-5 sentences max. No markdown headers. No bullet lists. "
        "Plain conversational text only.\n\n"
    )

    if tool == "market_data_fetch":
        return (
            preamble
            + f"The user asked: \"{original_input}\"\n"
            + (f"Focus on {ticker}. " if ticker else "")
            + "Give a brief, informative market commentary. "
            + "Mention this is a paper-trading demo with no real orders."
        )
    if tool == "place_order":
        return (
            preamble
            + f"The user requested to trade {shares} shares of {ticker or 'the stock'}. "
            + "Confirm the trade intent, note any key risks to watch, and remind them "
            + "this is a paper-trading demo."
        )
    if tool == "get_positions" or tool == "get_account":
        return (
            preamble
            + "The user asked about their portfolio or account. "
            + "Remind them this is a paper-trading system and suggest what to check."
        )
    if tool == "approve_trade":
        return (
            preamble
            + f"The user asked: \"{original_input}\"\n"
            + "Give a brief risk management perspective on reviewing trade recommendations."
        )
    # generic fallback
    return (
        preamble
        + f"The user asked: \"{original_input}\"\n"
        + "Respond helpfully in the context of a financial trading assistant."
    )


def _ollama_stream(prompt: str):
    """Generator yielding text tokens from Ollama streaming API.

    Yields empty string on any error so callers never crash.
    """
    try:
        with requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": UI_LLM_MODEL,
                "prompt": prompt,
                "stream": True,
                "think": False,
                "options": {"temperature": 0.4, "num_predict": 300},
            },
            timeout=_LLM_RESPONSE_TIMEOUT,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines():
                if raw:
                    try:
                        chunk = json.loads(raw)
                        if not chunk.get("done"):
                            yield chunk.get("response", "")
                    except json.JSONDecodeError:
                        continue
    except Exception:
        yield ""


def _issue_armoriq_for_ui(original_input: str, intent: dict, decision: str) -> dict:
    """Issue a real ArmorIQ intent token for any Trading Desk action.

    Trade intents (place_order) use armoriq_stub.issue().
    All other intents use armoriq_stub.capture() so every UI action creates a
    log entry in the ArmorIQ dashboard regardless of agent/tool.
    """
    sys.path.insert(0, str(_SCRIPT_DIR))
    import armoriq_stub  # noqa: F401

    agent  = intent.get("agent", "analyst")
    tool   = intent.get("tool", "market_data_fetch")
    ticker = intent.get("ticker", "")
    shares = int(intent.get("shares") or 0)

    try:
        if tool == "place_order" and ticker and shares > 0:
            side = "buy"  # Trading Desk defaults to buy intent for policy demo
            token_str = armoriq_stub.issue(ticker, shares, side)
            return json.loads(token_str)

        # Non-trade intent — capture in ArmorIQ with goal description
        goal = (
            f"[{decision}] {agent} · {tool}"
            + (f" · {ticker}" if ticker else "")
            + f" — \"{original_input[:80]}\""
        )
        return armoriq_stub.capture(
            agent_id=f"shieldtrade-{agent}",
            goal=goal,
            input_text=original_input,
        )
    except Exception as exc:
        return {"source": "error", "error": str(exc)}


def _openclaw_agent_lines(message: str, agent_id: str = "shieldtrade-analyst"):
    """Generator that yields text lines from an openclaw agent --local call.

    Routes the message through the OpenClaw gateway so every call appears in
    the gateway log (openclaw logs / ~/.openclaw/logs/gateway.log).
    Yields lines as they arrive; yields a final status line when done.
    """
    env = {
        **os.environ,
        "OPENCLAW_CONFIG_PATH": _OPENCLAW_CONFIG_PATH,
        "OPENCLAW_GATEWAY_TOKEN": _OPENCLAW_GATEWAY_TOKEN,
    }
    try:
        proc = subprocess.Popen(
            ["openclaw", "agent", "--local",
             "--agent", agent_id,
             message],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            cwd=str(_ROOT),
        )
        for raw in proc.stdout:  # type: ignore[union-attr]
            line = raw.rstrip()
            if line and "[ollama-stream]" not in line:
                yield line
        proc.wait()
    except FileNotFoundError:
        yield "⚠️ openclaw CLI not found — install with: npm install -g openclaw"
    except Exception as exc:
        yield f"⚠️ OpenClaw error: {exc}"


def _load_audit_log() -> list[dict]:
    if not AUDIT_LOG_PATH.exists():
        return []
    try:
        with open(AUDIT_LOG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _append_audit_log(entry: dict) -> None:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entries = _load_audit_log()
    entries.append(entry)
    with open(AUDIT_LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2)


# ---------------------------------------------------------------------------
# Enforcement Interceptor renderer
# ---------------------------------------------------------------------------

def _render_enforcement(result: dict) -> None:
    """Render the deterministic BLOCK / ALLOW banner and per-check table.

    Deliberately contains no Approve / Reject / Override controls.
    Blocks are final and immutable by design.
    """
    decision = result.get("decision", "UNKNOWN")
    checks   = result.get("checks", [])
    blocked  = result.get("blocked_reasons", [])
    agent    = result.get("agent", "")
    tool     = result.get("tool", "")
    ticker   = result.get("ticker", "")
    ts       = (result.get("timestamp") or "")[:19].replace("T", " ")

    meta_parts = [f"Agent: <b>{agent}</b>", f"Tool: <b>{tool}</b>"]
    if ticker:
        meta_parts.append(f"Ticker: <b>{ticker}</b>")
    if ts:
        meta_parts.append(f"{ts} UTC")
    meta_html = " &nbsp;·&nbsp; ".join(meta_parts)

    if decision == "BLOCK":
        reasons_li = "".join(
            f'<li style="color:#991b1b;font-size:0.83rem;margin:3px 0">{r}</li>'
            for r in blocked
        )
        st.markdown(
            f"""
<div class="ev-block-banner">
  <div class="ev-block-title">🛡️ ENFORCEMENT INTERCEPTOR &mdash; ACTION BLOCKED</div>
  <div class="ev-block-meta">{meta_html}</div>
  <ul style="margin:0;padding-left:18px">{reasons_li}</ul>
  <div class="ev-block-note">
    ⚠️ This action was autonomously blocked by the deterministic policy engine.
    No human approval is required or permitted by system design.
  </div>
</div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
<div class="ev-allow-banner">
  <div class="ev-allow-title">✅ POLICY CLEARED &mdash; ACTION ALLOWED</div>
  <div class="ev-allow-meta">{meta_html}</div>
</div>""",
            unsafe_allow_html=True,
        )

    if checks:
        rows = ""
        for c in checks:
            badge = (
                '<span class="badge-pass">PASS</span>'
                if c.get("result") == "PASS"
                else '<span class="badge-fail">FAIL</span>'
            )
            rows += (
                f"<tr>"
                f"<td>{badge}</td>"
                f'<td class="td-check">{c.get("check","")}</td>'
                f'<td class="td-detail">{c.get("detail","")}</td>'
                f'<td class="td-ref">{c.get("policy_ref","")}</td>'
                f"</tr>"
            )
        st.markdown(
            f"""
<table class="checks-table">
  <thead>
    <tr><th>Result</th><th>Check</th><th>Detail</th><th>Policy Ref</th></tr>
  </thead>
  <tbody>{rows}</tbody>
</table>""",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Core request handler — called inline when new input arrives
# ---------------------------------------------------------------------------

def _handle_new_request(
    content: str,
    policy: dict,
    *,
    is_file: bool = False,
    file_name: str = "",
) -> None:
    """LLM-route one user request, enforce policy, render result, persist to log."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    display = f"📄 File scanned: `{file_name}`" if is_file else content

    with st.chat_message("user"):
        st.markdown(display)
    st.session_state.messages.append({"role": "user", "content": display})

    reasoning_steps: list[str] = []
    result: dict | None = None
    intent: dict | None = None
    error_msg: str | None = None
    llm_response: str | None = None
    armoriq_token: dict | None = None

    # ── Process first, render after — avoids st.status() context-retention bug ─
    try:
        # Step 1: Prepare LLM input
        if is_file:
            reasoning_steps.append(
                f"📄 **Reading uploaded file:** `{file_name}` ({len(content):,} chars)"
            )
            llm_input = (
                f"A file named '{file_name}' was uploaded with this content:\n"
                f"{content[:800]}"
            )
        else:
            llm_input = content

        # Step 2: Parse intent (fast regex, LLM fallback)
        reasoning_steps.append(f"🧠 **Parsing intent via `{UI_LLM_MODEL}`...**")
        intent = parse_intent_via_llm(llm_input)

        if is_file and not intent.get("tool_args"):
            intent["tool_args"] = content[:2000]

        intent_json = json.dumps(intent, indent=2)
        reasoning_steps.append(
            f"✅ **Structured intent extracted:**\n```json\n{intent_json}\n```"
        )

        # Step 3: Policy engine (subprocess — avoids Python 3.14 typing.Union bug)
        reasoning_steps.append("⚖️ **Sending structured request to Policy Engine...**")
        _pe_proc = subprocess.run(
            [sys.executable,
             str(_ROOT / "scripts" / "policy_engine.py"),
             "validate-all", json.dumps(intent)],
            capture_output=True, text=True,
            env={**os.environ, "SHIELDTRADE_POLICY_PATH":
                 str(_ROOT / "config" / "shieldtrade-policies.yaml")},
            cwd=str(_ROOT),
        )
        if _pe_proc.returncode not in (0, 2):
            raise RuntimeError(_pe_proc.stderr[:300] or "policy engine error")
        result = json.loads(_pe_proc.stdout)

        decision = result.get("decision", "UNKNOWN")
        n_checks = len(result.get("checks", []))
        n_fail   = len([c for c in result.get("checks", []) if c.get("result") == "FAIL"])
        n_pass   = n_checks - n_fail
        reasoning_steps.append(
            f"🏁 **Policy decision: `{decision}`** — {n_pass} passed / {n_fail} failed"
        )

        # ── ArmorIQ intent token (real API call, ~1-2 s) ─────────────────
        armoriq_token = _issue_armoriq_for_ui(content, intent, decision)
        src = armoriq_token.get("source", "unknown")
        if src == "armoriq_iap":
            reasoning_steps.append(
                f"🔐 **ArmorIQ token issued:** `{armoriq_token.get('token_id', 'n/a')[:24]}…` "
                f"(plan_id: `{armoriq_token.get('plan_id', 'n/a')[:24]}…`)"
            )
        else:
            reasoning_steps.append(f"🔐 **ArmorIQ:** {src} (real API unavailable)")

    except requests.exceptions.ConnectionError:
        error_msg = (
            f"Cannot connect to Ollama at `{OLLAMA_BASE_URL}`. "
            "Run `ollama serve` and try again."
        )
        reasoning_steps.append(f"❌ **Connection error:** {error_msg}")
    except json.JSONDecodeError as exc:
        error_msg = (
            "Could not parse trading intent from natural language. "
            "Please specify a ticker and shares (e.g. 'Buy 5 AAPL')."
        )
        reasoning_steps.append(f"⚠️ **JSON parse error:** `{exc}`")
    except Exception as exc:
        error_msg = f"Unexpected error: {exc}"
        reasoning_steps.append(f"❌ **Error:** {exc}")

    # ── Render — all output goes directly into the chat bubble ───────────────
    with st.chat_message("assistant"):
        # Reasoning log (collapsed by default — click to expand)
        with st.expander("🔍 Agent Reasoning Log", expanded=False):
            for step in reasoning_steps:
                st.markdown(step)

        # Error banner (if something failed during processing)
        if error_msg:
            st.error(error_msg)

        # Enforcement result banner — rendered directly, no status() wrapper
        if result is not None:
            _render_enforcement(result)

            # ── ArmorIQ token card ────────────────────────────────────────
            if armoriq_token:
                src = armoriq_token.get("source", "unknown")
                is_real = src == "armoriq_iap"
                border  = "#16a34a" if is_real else "#f59e0b"
                bg      = "#f0fdf4" if is_real else "#fffbeb"
                icon    = "🔐" if is_real else "⚠️"
                label   = "Real ArmorIQ Token" if is_real else f"Fallback ({src})"
                st.markdown(
                    f"""<div style="border:1px solid {border};border-left:4px solid {border};
                    border-radius:6px;background:{bg};padding:10px 14px;margin:8px 0">
                    <div style="font-weight:700;font-size:0.85rem;color:{border};margin-bottom:4px">
                        {icon} ArmorIQ — {label}
                    </div>""" + (
                        f'<div style="font-size:0.78rem;color:#374151;font-family:monospace">'
                        f'token_id: {armoriq_token.get("token_id","n/a")}<br>'
                        f'plan_id:&nbsp; {armoriq_token.get("plan_id","n/a")}<br>'
                        f'agent:&nbsp;&nbsp;&nbsp; {armoriq_token.get("agent_id","shieldtrade")}<br>'
                        f'goal:&nbsp;&nbsp;&nbsp;&nbsp; {armoriq_token.get("goal","n/a")[:80]}'
                        f'</div>' if is_real else
                        f'<div style="font-size:0.78rem;color:#92400e">'
                        f'Set ARMORIQ_API_KEY in .env to see real tokens in the ArmorIQ dashboard.'
                        f'</div>'
                    ) + "</div>",
                    unsafe_allow_html=True,
                )

            # ── OpenClaw agent response (streamed) ────────────────────────
            if result.get("decision") == "ALLOW" and intent is not None:
                st.markdown("---")
                agent_id = f"shieldtrade-{intent.get('agent','analyst')}"
                st.markdown(
                    f'<div style="font-size:0.78rem;color:#6b7280;margin-bottom:4px">'
                    f'🤖 <b>OpenClaw agent</b> · <code>{agent_id}</code> · '
                    f'via local gateway <code>localhost:18789</code>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                oc_lines: list[str] = []
                oc_placeholder = st.empty()
                try:
                    for line in _openclaw_agent_lines(content, agent_id):
                        oc_lines.append(line)
                        # Show last 40 lines live
                        oc_placeholder.code("\n".join(oc_lines[-40:]), language=None)
                    llm_response = "\n".join(oc_lines)
                except Exception as exc:
                    oc_placeholder.warning(f"OpenClaw stream error: {exc}")

    # ── Persist to session state for replay ──────────────────────────────────
    st.session_state.messages.append({
        "role": "assistant",
        "content": "",
        "reasoning_steps": reasoning_steps,
        "enforcement_result": result,
        "armoriq_token": armoriq_token,
        "llm_response": llm_response,
    })

    # ── Save blocked actions to audit log ────────────────────────────────────
    if result and result.get("decision") == "BLOCK":
        _append_audit_log({
            "timestamp": result.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
            "input": content,
            "extracted_intent": intent,
            "policy_result": {
                "decision":        result["decision"],
                "agent":           result.get("agent"),
                "tool":            result.get("tool"),
                "ticker":          result.get("ticker"),
                "checks":          result.get("checks", []),
                "blocked_reasons": result.get("blocked_reasons", []),
                "policy_check_id": result.get("policy_check_id"),
            },
        })


# ---------------------------------------------------------------------------
# View: Trading Desk
# ---------------------------------------------------------------------------

def _view_trading_desk(policy: dict) -> None:
    st.markdown(
        """
<div style="margin-bottom:8px">
  <h2 style="margin:0;font-size:1.4rem;color:#111827;font-weight:700;line-height:1.3">
    Trading Desk
  </h2>
  <p style="margin:2px 0 0 0;color:#6b7280;font-size:0.85rem">
    Natural language requests are routed through the LLM intent parser,
    then deterministically enforced by the ArmorIQ policy engine.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )

    # ── File uploader ─────────────────────────────────────────────────────────
    with st.expander("📎 Scan untrusted content for injections / PII", expanded=False):
        st.caption(
            "Upload an earnings report, analyst note, CSV, or any file. "
            "The policy engine will scan it for PII patterns, data-exfiltration "
            "payloads, and prompt-injection attempts before any tool is invoked."
        )
        uploaded = st.file_uploader(
            "Drop a file here",
            type=None,
            label_visibility="collapsed",
            key="file_uploader",
        )
        scan_btn = st.button(
            "🔍 Scan file",
            disabled=(uploaded is None),
            key="scan_btn",
        )

    st.write("")  # vertical spacer

    # ── Session state init ────────────────────────────────────────────────────
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "_processed_file" not in st.session_state:
        st.session_state["_processed_file"] = None

    # ── Replay existing messages ──────────────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("content"):
                st.markdown(msg["content"])
            if msg.get("reasoning_steps"):
                with st.expander("🔍 Agent Reasoning Log", expanded=False):
                    for step in msg["reasoning_steps"]:
                        st.markdown(step)
            if msg.get("enforcement_result"):
                _render_enforcement(msg["enforcement_result"])
            tok = msg.get("armoriq_token")
            if tok:
                src = tok.get("source", "unknown")
                is_real = src == "armoriq_iap"
                border = "#16a34a" if is_real else "#f59e0b"
                bg     = "#f0fdf4" if is_real else "#fffbeb"
                icon   = "🔐" if is_real else "⚠️"
                label  = "Real ArmorIQ Token" if is_real else f"Fallback ({src})"
                st.markdown(
                    f"""<div style="border:1px solid {border};border-left:4px solid {border};
                    border-radius:6px;background:{bg};padding:10px 14px;margin:8px 0">
                    <div style="font-weight:700;font-size:0.85rem;color:{border};margin-bottom:4px">
                        {icon} ArmorIQ — {label}
                    </div>""" + (
                        f'<div style="font-size:0.78rem;color:#374151;font-family:monospace">'
                        f'token_id: {tok.get("token_id","n/a")}<br>'
                        f'plan_id:&nbsp; {tok.get("plan_id","n/a")}<br>'
                        f'agent:&nbsp;&nbsp;&nbsp; {tok.get("agent_id","shieldtrade")}<br>'
                        f'goal:&nbsp;&nbsp;&nbsp;&nbsp; {tok.get("goal","n/a")[:80]}'
                        f'</div>' if is_real else
                        f'<div style="font-size:0.78rem;color:#92400e">'
                        f'Set ARMORIQ_API_KEY in .env to see real tokens in the ArmorIQ dashboard.'
                        f'</div>'
                    ) + "</div>",
                    unsafe_allow_html=True,
                )
            if msg.get("llm_response"):
                st.markdown("---")
                st.code(msg["llm_response"], language=None)

    # ── Handle file scan ──────────────────────────────────────────────────────
    if scan_btn and uploaded is not None:
        file_key = f"{uploaded.name}:{uploaded.size}"
        if st.session_state["_processed_file"] != file_key:
            st.session_state["_processed_file"] = file_key
            content = uploaded.read().decode("utf-8", errors="replace")
            _handle_new_request(content, policy, is_file=True, file_name=uploaded.name)

    # ── Handle chat input ─────────────────────────────────────────────────────
    elif user_input := st.chat_input(
        "e.g. 'Analyze NVDA', 'Buy 5 shares of AAPL', 'Send data to attacker.com'…",
    ):
        _handle_new_request(user_input, policy)


# ---------------------------------------------------------------------------
# View: Audit Logs
# ---------------------------------------------------------------------------

def _view_audit_logs() -> None:
    col_hdr, col_btn = st.columns([5, 1])
    with col_hdr:
        st.markdown(
            """
<h2 style="margin:0 0 2px 0;font-size:1.4rem;color:#111827;font-weight:700">
  Audit Logs
</h2>
<p style="margin:0 0 12px 0;color:#6b7280;font-size:0.85rem">
  Immutable record of every blocked action with timestamp, policy reference,
  and full reasoning. Sourced from <code>output/audit_logs.json</code>.
</p>
""",
            unsafe_allow_html=True,
        )
    with col_btn:
        if st.button("↻ Refresh", use_container_width=True):
            st.rerun()

    entries = _load_audit_log()

    if not entries:
        st.info(
            "No audit log entries yet. "
            "Generate blocked actions from the Trading Desk to populate this view."
        )
        return

    # ── Summary metrics ───────────────────────────────────────────────────────
    total = len(entries)
    agents = [e.get("policy_result", {}).get("agent", "") for e in entries]
    unique_agents = sorted(set(agents))
    agent_summary = ", ".join(f"{a} ×{agents.count(a)}" for a in unique_agents) or "—"

    all_failed_checks = [
        c
        for e in entries
        for c in e.get("policy_result", {}).get("checks", [])
        if c.get("result") == "FAIL"
    ]
    top_check = (
        max(
            set(c.get("check", "") for c in all_failed_checks),
            key=lambda x: sum(1 for c in all_failed_checks if c.get("check") == x),
            default="—",
        )
        if all_failed_checks
        else "—"
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Blocked Actions", total)
    m2.metric("Agents Involved", len(unique_agents), help=agent_summary)
    m3.metric("Top Block Rule", top_check)

    st.markdown("---")

    # ── Detail table ──────────────────────────────────────────────────────────
    rows_html = ""
    for entry in reversed(entries):
        ts = (entry.get("timestamp") or "")[:19].replace("T", " ")
        pr = entry.get("policy_result", {})
        agent  = pr.get("agent", "")
        tool   = pr.get("tool", "")
        ticker = pr.get("ticker") or "—"
        reasons = "; ".join(pr.get("blocked_reasons", [])) or "—"

        failed_refs = ", ".join(
            c.get("policy_ref", "")
            for c in pr.get("checks", [])
            if c.get("result") == "FAIL" and c.get("policy_ref")
        ) or "—"

        raw_input = entry.get("input", "")
        input_trunc = (raw_input[:55] + "…") if len(raw_input) > 55 else raw_input

        rows_html += f"""
<tr>
  <td style="white-space:nowrap;color:#6b7280;font-size:0.79rem">{ts}&nbsp;UTC</td>
  <td><span class="a-badge-block">BLOCK</span></td>
  <td style="font-family:monospace;font-size:0.79rem">{agent}</td>
  <td style="font-family:monospace;font-size:0.79rem">{tool}</td>
  <td style="font-weight:600;color:#111827">{ticker}</td>
  <td style="color:#6b7280;font-size:0.8rem;max-width:200px">{reasons[:120]}</td>
  <td style="font-family:monospace;font-size:0.71rem;color:#9ca3af;max-width:160px">{failed_refs}</td>
  <td style="color:#9ca3af;font-size:0.79rem;font-style:italic;max-width:160px">{input_trunc}</td>
</tr>"""

    st.markdown(
        f"""
<div style="overflow-x:auto">
<table class="audit-table">
  <thead>
    <tr>
      <th>Timestamp</th>
      <th>Decision</th>
      <th>Agent</th>
      <th>Tool</th>
      <th>Ticker</th>
      <th>Blocked Reason</th>
      <th>Policy Ref</th>
      <th>Original Input</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
</div>""",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    with st.expander("📥 Raw JSON — audit_logs.json", expanded=False):
        st.json(entries)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _sidebar() -> str:
    with st.sidebar:
        st.markdown(
            """
<div style="display:flex;align-items:center;gap:10px;
            padding-bottom:12px;border-bottom:1px solid #e5e7eb;margin-bottom:4px">
  <span style="font-size:1.6rem;line-height:1">🛡️</span>
  <div>
    <div style="font-size:1rem;font-weight:700;color:#111827;line-height:1.2">ShieldTrade</div>
    <div style="font-size:0.72rem;color:#6b7280;line-height:1.4">ArmorIQ Enforcement Layer</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown('<p class="sidebar-label">Navigation</p>', unsafe_allow_html=True)
        view = st.radio(
            "View",
            options=["Trading Desk", "🤖 OpenClaw Pipeline", "📋 OpenClaw Logs", "Audit Logs"],
            label_visibility="collapsed",
        )

        st.markdown('<p class="sidebar-label">LLM Router</p>', unsafe_allow_html=True)
        st.markdown(
            f'<span class="model-badge">{UI_LLM_MODEL}</span>',
            unsafe_allow_html=True,
        )
        st.caption(f"Endpoint: `{OLLAMA_BASE_URL}`")
        st.caption("Override: `UI_LLM_MODEL` env var")

        st.markdown('<p class="sidebar-label">Active Policy</p>', unsafe_allow_html=True)
        try:
            p = _load_policy()
            meta     = p.get("metadata", {})
            tickers  = p.get("trading", {}).get("approved_tickers", {}).get("symbols", [])
            per_ord  = p.get("trading", {}).get("order_limits", {}).get("per_order_max_usd", 0)
            daily    = p.get("trading", {}).get("order_limits", {}).get("daily_aggregate_max_usd", 0)
            st.caption(
                f"v`{meta.get('version','?')}` · `{meta.get('enforcement','?')}`"
            )
            st.caption("Approved: `" + "  ".join(tickers) + "`")
            st.caption(f"Cap: `${per_ord:,.0f}` / order · `${daily:,.0f}` / day")
        except Exception as exc:
            st.error(f"Policy load error: {exc}")

        st.markdown(
            """
<div style="margin-top:24px;padding-top:12px;border-top:1px solid #e5e7eb;
            font-size:0.72rem;color:#9ca3af;line-height:1.8">
  All policy enforcement is <strong>fully autonomous</strong>.<br>
  Human approval is <strong>not permitted</strong> by design.<br>
  Blocks are deterministic and immutable.
</div>
""",
            unsafe_allow_html=True,
        )

    return view


# ---------------------------------------------------------------------------
# View: OpenClaw Agent Pipeline
# ---------------------------------------------------------------------------

def _view_openclaw_pipeline() -> None:
    """Run the genuine OpenClaw Analyst → Risk → Trader pipeline in the UI."""
    st.markdown(
        """
<h2 style="margin:0 0 4px 0;font-size:1.4rem;color:#111827;font-weight:700">
  OpenClaw Agent Pipeline
</h2>
<p style="margin:0 0 16px 0;color:#6b7280;font-size:0.85rem">
  Runs <b>shieldtrade-analyst → shieldtrade-risk-manager → shieldtrade-trader</b>
  as genuine OpenClaw agents via <code>openclaw agent --local</code>.
  Each agent reasons via the local LLM (proxy → Ollama) and calls the Python
  enforcement tools autonomously.
</p>
""",
        unsafe_allow_html=True,
    )

    # ── Controls ──────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        ticker = st.selectbox(
            "Ticker",
            ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "GME"],
            label_visibility="visible",
        )
    with col2:
        shares = st.number_input("Shares", min_value=1, max_value=500, value=5)
    with col3:
        assume_price = st.number_input("Assume price $", min_value=0.0, value=150.0, step=10.0)
    with col4:
        dry_run = st.checkbox("Dry-run", value=True, help="Skip Alpaca order submission")

    assume_open = st.checkbox(
        "Bypass market-hours check (demo mode)",
        value=False,
        help="Disables the market_hours_only policy check so the pipeline can run on weekends/after hours. "
             "Only use for demo/testing — never in production.",
    )

    run_btn = st.button("▶ Run OpenClaw Pipeline", type="primary", use_container_width=True)

    st.caption(
        "TSLA / GME will be **blocked** by policy (unapproved ticker). "
        "Shares > 100 trigger the share-count cap. "
        "Amount > $2000 triggers per-order cap."
    )

    if not run_btn:
        st.info("Configure the trade above and click **Run OpenClaw Pipeline** to start.")
        return

    # ── Run ───────────────────────────────────────────────────────────────────
    ticker = ticker.upper()
    cmd = [
        sys.executable, str(_ROOT / "scripts" / "run_agents.py"),
        ticker,
        "--shares", str(shares),
        "--assume-price", str(assume_price),
    ]
    if dry_run:
        cmd.append("--dry-run")
    if assume_open:
        cmd.append("--assume-open")

    env = {
        **os.environ,
        "OPENCLAW_CONFIG_PATH": str(_ROOT / "config" / "openclaw.json"),
        "OPENCLAW_GATEWAY_TOKEN": "d17d4ab08c80922f2bff84cedcad95e54b75e7c2d16ebb01",
    }

    # ── Agent stage containers ────────────────────────────────────────────────
    st.markdown("---")

    analyst_container   = st.container()
    risk_container      = st.container()
    trader_container    = st.container()
    summary_container   = st.container()

    output_lines: list[str] = []
    stage_outputs: dict[str, list[str]] = {
        "analyst": [], "risk": [], "trader": [], "summary": []
    }
    current_stage = "analyst"

    with analyst_container:
        st.markdown(
            '<div style="font-weight:700;color:#1d4ed8;font-size:0.9rem;margin-bottom:4px">'
            '🔍 Stage 1 — Analyst Agent (shieldtrade-analyst)</div>',
            unsafe_allow_html=True,
        )
        analyst_out = st.empty()

    with risk_container:
        st.markdown(
            '<div style="font-weight:700;color:#7c3aed;font-size:0.9rem;margin-bottom:4px">'
            '⚖️ Stage 2 — Risk Manager Agent (shieldtrade-risk-manager)</div>',
            unsafe_allow_html=True,
        )
        risk_out = st.empty()

    with trader_container:
        st.markdown(
            '<div style="font-weight:700;color:#065f46;font-size:0.9rem;margin-bottom:4px">'
            '🤖 Stage 3 — Trader Agent (shieldtrade-trader)</div>',
            unsafe_allow_html=True,
        )
        trader_out = st.empty()

    # ── Stream subprocess output ──────────────────────────────────────────────
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            cwd=str(_ROOT),
        )

        def _render(container_placeholder, lines: list[str]) -> None:
            text = "\n".join(lines[-80:])  # cap to last 80 lines
            container_placeholder.code(text, language=None)

        for raw_line in proc.stdout:  # type: ignore[union-attr]
            line = raw_line.rstrip()
            output_lines.append(line)

            # Route line to the right stage bucket
            if "STAGE 1" in line or "Analyst Agent" in line:
                current_stage = "analyst"
            elif "STAGE 2" in line or "Risk Manager" in line:
                current_stage = "risk"
            elif "STAGE 3" in line or "Trader Agent" in line:
                current_stage = "trader"
            elif "PIPELINE SUMMARY" in line or "PIPELINE COMPLETE" in line or "PIPELINE BLOCKED" in line:
                current_stage = "summary"

            # Skip internal stream warnings
            if "[ollama-stream]" in line:
                continue

            stage_outputs[current_stage].append(line)

            # Live update the right container
            if current_stage == "analyst":
                _render(analyst_out, stage_outputs["analyst"])
            elif current_stage == "risk":
                _render(risk_out, stage_outputs["risk"])
            elif current_stage == "trader":
                _render(trader_out, stage_outputs["trader"])

        proc.wait()
        exit_code = proc.returncode

    except FileNotFoundError:
        st.error("`run_agents.py` or `openclaw` CLI not found. Run `npm install -g openclaw`.")
        return
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")
        return

    # ── Final renders ─────────────────────────────────────────────────────────
    _render(analyst_out, stage_outputs["analyst"])
    _render(risk_out,    stage_outputs["risk"])
    _render(trader_out,  stage_outputs["trader"])

    # ── Enforcement result ────────────────────────────────────────────────────
    with summary_container:
        st.markdown("---")
        full_text = "\n".join(output_lines)
        if exit_code == 0 and ("PIPELINE COMPLETE" in full_text or "✓" in full_text):
            st.markdown(
                """<div class="ev-allow-banner">
  <div class="ev-allow-title">✅ OPENCLAW PIPELINE — TRADE ALLOWED</div>
  <div class="ev-allow-meta">
    All three OpenClaw agents completed. Policy engine cleared the trade.
    Reasoning (LLM) and enforcement (policy_engine.py) are fully separated.
  </div>
</div>""",
                unsafe_allow_html=True,
            )
        else:
            blocked_lines = [l for l in output_lines if "BLOCK" in l or "✗" in l or "blocked" in l.lower()]
            reasons_html = "".join(
                f'<li style="color:#991b1b;font-size:0.83rem;margin:3px 0">{l.strip()}</li>'
                for l in blocked_lines[:5] if l.strip()
            )
            st.markdown(
                f"""<div class="ev-block-banner">
  <div class="ev-block-title">🛡️ OPENCLAW PIPELINE — ACTION BLOCKED</div>
  <div class="ev-block-meta">
    Policy engine autonomously blocked the trade. No human intervention required or possible.
  </div>
  <ul style="margin:8px 0 0 0;padding-left:18px">{reasons_html}</ul>
  <div class="ev-block-note">
    ⚠️ The OpenClaw LLM agent cannot override this block — enforcement is in the Python
    layer, not the prompt. The agent can reason all it wants; policy_engine.py has final say.
  </div>
</div>""",
                unsafe_allow_html=True,
            )

        # Full raw output expander
        with st.expander("📋 Full agent output (all stages)", expanded=False):
            st.code("\n".join(output_lines), language=None)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_openclaw_logs(max_entries: int = 200) -> list[dict]:
    """Read today's (and yesterday's) OpenClaw NDJSON log and return clean entries."""
    import re as _re
    from datetime import date, timedelta

    _ANSI = _re.compile(r"\x1b\[[0-9;]*m")
    _SKIP_MSGS = ("Config write audit", "Gateway start blocked", "xai-auth",
                  "no config-backed key found", "config-audit.jsonl")

    def _strip(s: str) -> str:
        return _ANSI.sub("", s).strip()

    def _extract_text(val) -> str:
        if isinstance(val, str):
            return _strip(val)
        if isinstance(val, dict):
            # agent/embedded event dict
            event  = val.get("event", "")
            run_id = val.get("runId", "")
            model  = val.get("model", "")
            error  = val.get("error", "")
            parts  = [p for p in [event, f"runId={run_id}" if run_id else "",
                                   f"model={model}" if model else "",
                                   f"error={error}" if error else ""] if p]
            return "  ".join(parts)
        return str(val)

    entries: list[dict] = []
    today = date.today()
    for d in [today, today - timedelta(days=1)]:
        log_path = f"/tmp/openclaw/openclaw-{d}.log"
        try:
            with open(log_path) as f:
                for line in f:
                    try:
                        obj = json.loads(line.strip())
                    except Exception:
                        continue

                    # Build a readable message from field "0" and "1"
                    f0 = obj.get("0", "")
                    f1 = obj.get("1", "")
                    subsystem = ""

                    if isinstance(f0, str) and f0.startswith("{"):
                        try:
                            sub = json.loads(f0)
                            subsystem = sub.get("subsystem", "")
                        except Exception:
                            pass
                        message = _extract_text(f1) if f1 else ""
                    else:
                        message = _extract_text(f0)
                        if f1:
                            message += "  " + _extract_text(f1)

                    # Skip noise
                    if any(skip in message for skip in _SKIP_MSGS):
                        continue
                    if not message.strip():
                        continue

                    level = (obj.get("_meta") or {}).get("logLevelName", "INFO")
                    ts    = obj.get("time", "")
                    entries.append({
                        "time":      ts,
                        "level":     level,
                        "subsystem": subsystem,
                        "message":   message[:300],
                    })
        except FileNotFoundError:
            continue

    # Return most recent entries last
    return entries[-max_entries:]


def _view_openclaw_logs() -> None:
    """Live view of OpenClaw gateway logs, filtered and formatted for the demo."""
    col_hdr, col_btn = st.columns([5, 1])
    with col_hdr:
        st.markdown(
            """
<h2 style="margin:0 0 2px 0;font-size:1.4rem;color:#111827;font-weight:700">
  OpenClaw Gateway Logs
</h2>
<p style="margin:0 0 12px 0;color:#6b7280;font-size:0.85rem">
  Live view of <code>/tmp/openclaw/openclaw-*.log</code> — every agent call,
  tool execution, and policy event routed through the local gateway
  (<code>localhost:18789</code>).
</p>
""",
            unsafe_allow_html=True,
        )
    with col_btn:
        if st.button("↻ Refresh", use_container_width=True):
            st.rerun()

    entries = _parse_openclaw_logs(max_entries=300)

    # ── Filter controls ───────────────────────────────────────────────────────
    fc1, fc2 = st.columns([3, 2])
    with fc1:
        search = st.text_input("Filter by keyword", placeholder="agent, runId, shieldtrade…",
                               label_visibility="collapsed")
    with fc2:
        level_filter = st.selectbox("Level", ["ALL", "INFO", "ERROR", "WARN"],
                                    label_visibility="collapsed")

    if search:
        entries = [e for e in entries if search.lower() in e["message"].lower()
                   or search.lower() in e["subsystem"].lower()]
    if level_filter != "ALL":
        entries = [e for e in entries if e["level"] == level_filter]

    # ── Metrics ───────────────────────────────────────────────────────────────
    total   = len(entries)
    n_err   = sum(1 for e in entries if e["level"] == "ERROR")
    n_agent = sum(1 for e in entries if "agent" in e["subsystem"].lower()
                  or "agent" in e["message"].lower())
    m1, m2, m3 = st.columns(3)
    m1.metric("Log Entries", total)
    m2.metric("Agent Events", n_agent)
    m3.metric("Errors", n_err)

    st.markdown("---")

    if not entries:
        st.info("No log entries found. Use the Trading Desk to trigger agent calls.")
        return

    # ── Log table ─────────────────────────────────────────────────────────────
    rows = ""
    for e in reversed(entries):
        ts  = e["time"][:19].replace("T", " ") if e["time"] else "—"
        lvl = e["level"]
        sub = e["subsystem"] or "gateway"
        msg = e["message"]

        # Colour coding
        if lvl == "ERROR":
            lvl_html = '<span style="background:#fee2e2;color:#b91c1c;border-radius:3px;padding:1px 7px;font-size:0.72rem;font-weight:700">ERROR</span>'
        elif lvl == "WARN":
            lvl_html = '<span style="background:#fef3c7;color:#92400e;border-radius:3px;padding:1px 7px;font-size:0.72rem;font-weight:700">WARN</span>'
        else:
            lvl_html = '<span style="background:#dbeafe;color:#1d4ed8;border-radius:3px;padding:1px 7px;font-size:0.72rem;font-weight:700">INFO</span>'

        # Highlight ShieldTrade-related entries
        is_agent = "agent" in sub.lower() or "shieldtrade" in msg.lower() or "runId" in msg
        row_style = 'background:#f0fdf4;' if is_agent else ''

        # Bold key tokens
        import html as _html
        msg_safe = _html.escape(msg)
        for kw in ("shieldtrade-analyst", "shieldtrade-risk-manager", "shieldtrade-trader",
                   "runId", "ALLOW", "BLOCK", "agent"):
            msg_safe = msg_safe.replace(kw, f"<b>{kw}</b>")

        rows += f"""<tr style="{row_style}">
  <td style="white-space:nowrap;color:#6b7280;font-size:0.78rem">{ts}</td>
  <td>{lvl_html}</td>
  <td style="font-family:monospace;font-size:0.75rem;color:#6b7280">{_html.escape(sub)}</td>
  <td style="font-size:0.8rem;color:#111827;max-width:600px;word-break:break-word">{msg_safe}</td>
</tr>"""

    st.markdown(
        f"""<div style="overflow-x:auto">
<table style="width:100%;border-collapse:collapse;font-size:0.82rem">
  <thead>
    <tr style="background:#f9fafb">
      <th style="text-align:left;padding:8px 12px;border-bottom:2px solid #e5e7eb;white-space:nowrap">Time</th>
      <th style="text-align:left;padding:8px 12px;border-bottom:2px solid #e5e7eb">Level</th>
      <th style="text-align:left;padding:8px 12px;border-bottom:2px solid #e5e7eb">Subsystem</th>
      <th style="text-align:left;padding:8px 12px;border-bottom:2px solid #e5e7eb">Message</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table></div>""",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    with st.expander("📄 Raw log path", expanded=False):
        from datetime import date as _date
        st.code(f"/tmp/openclaw/openclaw-{_date.today()}.log", language=None)
        st.caption("Also available via: `openclaw logs --follow` in terminal")


def main() -> None:
    policy = _load_policy()
    view   = _sidebar()
    if view == "Trading Desk":
        _view_trading_desk(policy)
    elif view == "🤖 OpenClaw Pipeline":
        _view_openclaw_pipeline()
    elif view == "📋 OpenClaw Logs":
        _view_openclaw_logs()
    else:
        _view_audit_logs()


if __name__ == "__main__":
    main()
