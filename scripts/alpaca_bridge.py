#!/usr/bin/env python3
"""
ShieldTrade - Alpaca Paper Trading Bridge
=========================================
This script is the interface between OpenClaw agents and Alpaca.
All responses are JSON.

Usage:
  python3 alpaca_bridge.py account
  python3 alpaca_bridge.py positions
  python3 alpaca_bridge.py quote AAPL
  python3 alpaca_bridge.py bars AAPL 1Day 30
  python3 alpaca_bridge.py order AAPL 10 buy
  python3 alpaca_bridge.py order AAPL 5 sell
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

try:
    from supabase_logger import log as supabase_log
except Exception:
    supabase_log = None


API_KEY = os.environ.get("ALPACA_API_KEY")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")

if not API_KEY or not SECRET_KEY:
    print(
        json.dumps(
            {
                "error": "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in environment",
            }
        )
    )
    raise SystemExit(1)

trade_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

TERMINAL_ORDER_STATUSES = {"filled", "canceled", "expired", "rejected"}


def _audit(command, status, details):
    if supabase_log is None:
        return None
    return supabase_log(
        "audit_log",
        {
            "event_type": "alpaca_bridge",
            "command": command,
            "status": status,
            "details": json.dumps(details, default=str),
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    )


def _status_name(value):
    return str(value).split(".")[-1].lower()


def _cancel_conflicting_open_orders(symbol, requested_side):
    opposite_side = "sell" if requested_side == "buy" else "buy"
    canceled = []

    try:
        open_orders = trade_client.get_orders()
    except Exception:
        return canceled

    for open_order in open_orders:
        if str(getattr(open_order, "symbol", "")).upper() != symbol:
            continue

        status = _status_name(getattr(open_order, "status", ""))
        if status in TERMINAL_ORDER_STATUSES:
            continue

        side = _status_name(getattr(open_order, "side", ""))
        if side != opposite_side:
            continue

        order_id = str(getattr(open_order, "id", ""))
        if not order_id:
            continue

        try:
            trade_client.cancel_order_by_id(order_id)
            canceled.append(order_id)
        except Exception:
            pass

    return canceled


def _wait_for_order_terminal_state(order_id, timeout_seconds=30, poll_seconds=1):
    deadline = time.time() + timeout_seconds
    latest = None

    while time.time() < deadline:
        latest = trade_client.get_order_by_id(order_id)
        status = _status_name(getattr(latest, "status", ""))
        if status in TERMINAL_ORDER_STATUSES:
            return latest, True
        time.sleep(poll_seconds)

    return latest, False


def cmd_account():
    acct = trade_client.get_account()
    return {
        "status": str(acct.status),
        "buying_power": str(acct.buying_power),
        "cash": str(acct.cash),
        "portfolio_value": str(acct.portfolio_value),
        "equity": str(acct.equity),
        "currency": "USD",
        "paper": True,
    }


def cmd_positions():
    positions = trade_client.get_all_positions()

    pending_orders = []
    try:
        open_orders = trade_client.get_orders()
        for order in open_orders:
            status = _status_name(getattr(order, "status", ""))
            if status in TERMINAL_ORDER_STATUSES:
                continue
            pending_orders.append(
                {
                    "order_id": str(order.id),
                    "symbol": order.symbol,
                    "qty": str(order.qty),
                    "side": str(order.side),
                    "status": str(order.status),
                    "submitted_at": str(order.submitted_at),
                }
            )
    except Exception:
        pending_orders = []

    if not positions:
        return {"positions": [], "count": 0, "pending_orders": pending_orders, "pending_count": len(pending_orders)}

    return {
        "positions": [
            {
                "symbol": p.symbol,
                "qty": str(p.qty),
                "side": str(p.side),
                "market_value": str(p.market_value),
                "avg_entry_price": str(p.avg_entry_price),
                "current_price": str(p.current_price),
                "unrealized_pl": str(p.unrealized_pl),
                "unrealized_plpc": str(p.unrealized_plpc),
            }
            for p in positions
        ],
        "count": len(positions),
        "pending_orders": pending_orders,
        "pending_count": len(pending_orders),
    }


def cmd_quote(symbol):
    symbol = symbol.upper().strip()
    request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
    quotes = data_client.get_stock_latest_quote(request)
    quote = quotes[symbol]
    return {
        "symbol": symbol,
        "ask_price": str(quote.ask_price),
        "bid_price": str(quote.bid_price),
        "ask_size": quote.ask_size,
        "bid_size": quote.bid_size,
        "timestamp": str(quote.timestamp),
    }


def cmd_bars(symbol, timeframe="1Day", limit=30):
    symbol = symbol.upper().strip()
    tf_map = {
        "1Min": TimeFrame.Minute,
        "5Min": TimeFrame(5, "Min"),
        "1Hour": TimeFrame.Hour,
        "1Day": TimeFrame.Day,
    }
    tf = tf_map.get(timeframe, TimeFrame.Day)

    limit_int = int(limit)
    end_ts = datetime.now(timezone.utc)
    start_ts = end_ts - timedelta(days=max(limit_int * 4, 30))

    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=tf,
        start=start_ts,
        end=end_ts,
        limit=limit_int,
        feed=DataFeed.IEX,
    )
    bars_data = data_client.get_stock_bars(request)

    # alpaca-py may return BarSet with .data rather than a plain dict.
    bars_list = []
    if isinstance(bars_data, dict):
        bars_list = bars_data.get(symbol, [])
    elif hasattr(bars_data, "data") and isinstance(bars_data.data, dict):
        bars_list = bars_data.data.get(symbol, [])
    else:
        try:
            bars_list = bars_data[symbol]
        except Exception:
            bars_list = []

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(bars_list),
        "bars": [
            {
                "timestamp": str(bar.timestamp),
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": int(bar.volume),
            }
            for bar in bars_list
        ],
    }


def cmd_order(symbol, qty, side):
    symbol = symbol.upper().strip()
    side = side.lower().strip()

    if side not in ("buy", "sell"):
        return {"error": f"Invalid side '{side}'. Must be 'buy' or 'sell'."}

    canceled_conflicts = _cancel_conflicting_open_orders(symbol, side)

    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=float(qty),
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    order = trade_client.submit_order(order_data=order_data)

    final_order, reached_terminal = _wait_for_order_terminal_state(str(order.id))
    if final_order is None:
        final_order = order

    return {
        "order_id": str(final_order.id),
        "client_order_id": str(final_order.client_order_id),
        "symbol": final_order.symbol,
        "qty": str(final_order.qty),
        "side": str(final_order.side),
        "type": str(final_order.type),
        "status": str(final_order.status),
        "submitted_at": str(final_order.submitted_at),
        "filled_qty": str(getattr(final_order, "filled_qty", "0")),
        "reached_terminal_state": reached_terminal,
        "canceled_conflicting_order_ids": canceled_conflicts,
        "paper": True,
    }


COMMANDS = {
    "account": (cmd_account, 0),
    "positions": (cmd_positions, 0),
    "quote": (cmd_quote, 1),
    "bars": (cmd_bars, 1),
    "order": (cmd_order, 3),
}


def print_usage():
    print(
        json.dumps(
            {
                "error": "Invalid usage",
                "commands": {
                    "account": "Get account info",
                    "positions": "Get open positions",
                    "quote <SYMBOL>": "Get latest quote",
                    "bars <SYMBOL> [TIMEFRAME] [LIMIT]": "Get historical bars",
                    "order <SYMBOL> <QTY> <SIDE>": "Place market order (buy/sell)",
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        raise SystemExit(1)

    command = sys.argv[1].lower()

    if command not in COMMANDS:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        print_usage()
        raise SystemExit(1)

    func, min_args = COMMANDS[command]
    args = sys.argv[2:]

    if len(args) < min_args:
        print(
            json.dumps(
                {
                    "error": f"'{command}' requires at least {min_args} argument(s), got {len(args)}",
                }
            )
        )
        raise SystemExit(1)

    try:
        result = func(*args)
        _audit(command, "success", {"args": args, "result": result})
        print(json.dumps(result, indent=2))
    except Exception as exc:
        _audit(command, "error", {"args": args, "error": str(exc)})
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "command": command,
                    "args": args,
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            )
        )
        raise SystemExit(1)
