#!/usr/bin/env python3
import json
import os
import sys

from dotenv import load_dotenv
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.enums import DataFeed


def to_output(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, indent=2))
    return code


def main() -> int:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    load_dotenv(env_path)

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        return to_output(
            {
                "error": "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env",
                "example": "python scripts/alpaca_realtime_check.py quote AAPL",
            },
            1,
        )

    if len(sys.argv) < 2:
        return to_output(
            {
                "error": "Usage: alpaca_realtime_check.py quote <SYMBOL> [iex|sip]",
            },
            1,
        )

    command = sys.argv[1].lower()
    if command != "quote":
        return to_output({"error": f"Unknown command: {command}"}, 1)

    symbol = (sys.argv[2] if len(sys.argv) >= 3 else "AAPL").upper()
    feed_name = (sys.argv[3] if len(sys.argv) >= 4 else "iex").lower()
    feed = DataFeed.IEX if feed_name == "iex" else DataFeed.SIP

    client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)
    request = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=feed)
    quotes = client.get_stock_latest_quote(request)
    quote = quotes.get(symbol)

    if quote is None:
        return to_output({"error": f"No quote received for {symbol}"}, 1)

    return to_output(
        {
            "symbol": symbol,
            "feed": feed_name,
            "bid_price": float(quote.bid_price),
            "ask_price": float(quote.ask_price),
            "bid_size": int(quote.bid_size),
            "ask_size": int(quote.ask_size),
            "timestamp": quote.timestamp.isoformat(),
        }
    )


if __name__ == "__main__":
    raise SystemExit(main())
