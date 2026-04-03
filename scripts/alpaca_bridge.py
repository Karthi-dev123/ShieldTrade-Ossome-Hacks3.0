"""ShieldTrade Alpaca Bridge — paper trading execution layer.

Isolated bridge between OpenClaw agents and Alpaca paper sandbox.
All output is valid JSON to stdout. No logging, no markdown.
"""

import json
import os
import sys
from datetime import datetime, timezone

import supabase_logger


def _env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(f"Missing required env var: {key}")
    return val


def _trading_client():
    _env("ARMORIQ_API_KEY")
    from alpaca.trading.client import TradingClient
    return TradingClient(
        api_key=_env("ALPACA_API_KEY"),
        secret_key=_env("ALPACA_SECRET_KEY"),
        paper=True,
    )


def _data_client():
    _env("ARMORIQ_API_KEY")
    from alpaca.data.historical import StockHistoricalDataClient
    return StockHistoricalDataClient(
        api_key=_env("ALPACA_API_KEY"),
        secret_key=_env("ALPACA_SECRET_KEY"),
    )


def _serialize(obj) -> str:
    """JSON-safe serialization for alpaca model objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return {k: _serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(i) for i in obj]
    return obj


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_account() -> dict:
    client = _trading_client()
    acct = client.get_account()
    return {
        "status": str(acct.status),
        "buying_power": str(acct.buying_power),
        "cash": str(acct.cash),
        "equity": str(acct.equity),
        "currency": str(acct.currency),
        "account_number": str(acct.account_number),
    }


def cmd_positions() -> dict:
    client = _trading_client()
    positions = client.get_all_positions()
    return {
        "count": len(positions),
        "positions": [
            {
                "symbol": str(p.symbol),
                "qty": str(p.qty),
                "side": str(p.side),
                "market_value": str(p.market_value),
                "avg_entry_price": str(p.avg_entry_price),
                "unrealized_pl": str(p.unrealized_pl),
                "unrealized_plpc": str(p.unrealized_plpc),
                "current_price": str(p.current_price),
            }
            for p in positions
        ],
    }


def cmd_quote(symbol: str) -> dict:
    from alpaca.data.requests import StockLatestQuoteRequest

    client = _data_client()
    req = StockLatestQuoteRequest(symbol_or_symbols=[symbol.upper()])
    quotes = client.get_stock_latest_quote(req)

    quote = quotes.get(symbol.upper())
    if quote is None:
        raise ValueError(f"No quote data returned for {symbol.upper()}")

    return {
        "symbol": symbol.upper(),
        "ask_price": float(quote.ask_price) if quote.ask_price else None,
        "ask_size": float(quote.ask_size) if quote.ask_size else None,
        "bid_price": float(quote.bid_price) if quote.bid_price else None,
        "bid_size": float(quote.bid_size) if quote.bid_size else None,
        "timestamp": quote.timestamp.isoformat() if quote.timestamp else None,
    }


def cmd_bars(symbol: str, timeframe: str = "1Day", limit: int = 30) -> dict:
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    tf_map = {
        "1Min": TimeFrame.Minute,
        "1Hour": TimeFrame.Hour,
        "1Day": TimeFrame.Day,
        "1Week": TimeFrame.Week,
        "1Month": TimeFrame.Month,
    }

    tf = tf_map.get(timeframe)
    if tf is None:
        raise ValueError(f"Unknown timeframe '{timeframe}'. Valid: {list(tf_map.keys())}")

    client = _data_client()
    req = StockBarsRequest(
        symbol_or_symbols=[symbol.upper()],
        timeframe=tf,
        limit=limit,
    )
    bars_data = client.get_stock_bars(req)
    
    if hasattr(bars_data, "data"):
        bars_list = bars_data.data.get(symbol.upper(), [])
    else:
        try:
            bars_list = bars_data[symbol.upper()]
        except KeyError:
            bars_list = []

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "count": len(bars_list),
        "bars": [
            {
                "timestamp": b.timestamp.isoformat() if b.timestamp else None,
                "open": float(b.open),
                "high": float(b.high),
                "low": float(b.low),
                "close": float(b.close),
                "volume": int(b.volume),
                "vwap": float(b.vwap) if b.vwap else None,
            }
            for b in bars_list
        ],
    }


def cmd_order(symbol: str, qty: int, side: str, policy_check_id: str | None = None) -> dict:
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    side_enum = {"buy": OrderSide.BUY, "sell": OrderSide.SELL}.get(side.lower())
    if side_enum is None:
        raise ValueError(f"Invalid side '{side}'. Must be 'buy' or 'sell'.")

    client = _trading_client()
    req = MarketOrderRequest(
        symbol=symbol.upper(),
        qty=qty,
        side=side_enum,
        time_in_force=TimeInForce.DAY,
    )
    order = client.submit_order(req)

    result = {
        "order_id": str(order.id),
        "symbol": str(order.symbol),
        "qty": str(order.qty),
        "side": str(order.side),
        "type": str(order.type),
        "status": str(order.status),
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        "time_in_force": str(order.time_in_force),
    }

    supabase_logger.log("trade_events", {
        "order_id": result["order_id"],
        "symbol": result["symbol"],
        "qty": result["qty"],
        "side": "buy" if "BUY" in result["side"].upper() else "sell",
        "order_type": result["type"],
        "time_in_force": result["time_in_force"],
        "status": result["status"],
        "submitted_at": result["submitted_at"],
        **({"policy_check_id": policy_check_id} if policy_check_id else {}),
    })

    return result


# ---------------------------------------------------------------------------
# CLI dispatcher
# ---------------------------------------------------------------------------

USAGE = {
    "account": "account",
    "positions": "positions",
    "quote": "quote <SYMBOL>",
    "bars": "bars <SYMBOL> [TIMEFRAME] [LIMIT]",
    "order": "order <SYMBOL> <QTY> <SIDE>",
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in USAGE:
        print(json.dumps({
            "error": "Unknown command",
            "usage": USAGE,
        }))
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    try:
        if cmd == "account":
            result = cmd_account()

        elif cmd == "positions":
            result = cmd_positions()

        elif cmd == "quote":
            if not args:
                raise ValueError("Missing required argument: SYMBOL")
            result = cmd_quote(args[0])

        elif cmd == "bars":
            if not args:
                raise ValueError("Missing required argument: SYMBOL")
            symbol = args[0]
            timeframe = args[1] if len(args) > 1 else "1Day"
            limit = int(args[2]) if len(args) > 2 else 30
            result = cmd_bars(symbol, timeframe, limit)

        elif cmd == "order":
            if len(args) < 3:
                raise ValueError("Usage: order <SYMBOL> <QTY> <SIDE> [POLICY_CHECK_ID]")
            policy_check_id = args[3] if len(args) > 3 else None
            result = cmd_order(args[0], int(args[1]), args[2], policy_check_id)

        print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
