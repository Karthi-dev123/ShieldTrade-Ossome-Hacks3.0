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
                "error": "Usage: alpaca_realtime_check.py quote <SYMBOL|SYMBOL1,SYMBOL2,...> [iex|sip]",
                "examples": [
                    "python scripts/alpaca_realtime_check.py quote AAPL",
                    "python scripts/alpaca_realtime_check.py quote AAPL,MSFT,GOOGL iex",
                    "python scripts/alpaca_realtime_check.py quote AAPL MSFT GOOGL sip",
                ]
            },
            1,
        )

    command = sys.argv[1].lower()
    if command != "quote":
        return to_output({"error": f"Unknown command: {command}"}, 1)

    # Support multiple symbols: comma-separated or space-separated args
    if len(sys.argv) >= 3:
        if "," in sys.argv[2]:
            # Comma-separated: quote "AAPL,MSFT,GOOGL"
            symbols = [s.strip().upper() for s in sys.argv[2].split(",")]
        else:
            # Space-separated: quote AAPL MSFT GOOGL [feed]
            feed_start_idx = 3
            symbols = []
            for i in range(2, len(sys.argv)):
                arg = sys.argv[i].lower()
                if arg in ["iex", "sip"]:
                    feed_start_idx = i
                    break
                symbols.append(arg.upper())
    else:
        symbols = ["AAPL"]

    feed_name = "iex"
    for i in range(len(sys.argv) - 1, 1, -1):
        arg = sys.argv[i].lower()
        if arg in ["iex", "sip"]:
            feed_name = arg
            break

    feed = DataFeed.IEX if feed_name == "iex" else DataFeed.SIP

    client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)
    request = StockLatestQuoteRequest(symbol_or_symbols=symbols, feed=feed)
    quotes = client.get_stock_latest_quote(request)

    if not quotes:
        return to_output({"error": f"No quotes received for symbols: {symbols}"}, 1)

    # If single symbol, return single quote object (backward compatible)
    if len(symbols) == 1:
        quote = quotes.get(symbols[0])
        if quote is None:
            return to_output({"error": f"No quote received for {symbols[0]}"}, 1)
        return to_output(
            {
                "symbol": symbols[0],
                "feed": feed_name,
                "bid_price": float(quote.bid_price),
                "ask_price": float(quote.ask_price),
                "bid_size": int(quote.bid_size),
                "ask_size": int(quote.ask_size),
                "timestamp": quote.timestamp.isoformat(),
            }
        )
    
    # Multiple symbols: return array of quotes
    results = []
    for symbol in symbols:
        quote = quotes.get(symbol)
        if quote is not None:
            results.append(
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
    
    return to_output({"quotes": results, "total": len(results), "requested": len(symbols)})


if __name__ == "__main__":
    raise SystemExit(main())
