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
    if not positions:
        return {"positions": [], "count": 0}

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

    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=float(qty),
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    order = trade_client.submit_order(order_data=order_data)

    return {
        "order_id": str(order.id),
        "client_order_id": str(order.client_order_id),
        "symbol": order.symbol,
        "qty": str(order.qty),
        "side": str(order.side),
        "type": str(order.type),
        "status": str(order.status),
        "submitted_at": str(order.submitted_at),
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
        print(json.dumps(result, indent=2))
    except Exception as exc:
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
