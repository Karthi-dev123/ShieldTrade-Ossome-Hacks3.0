import sys
from pathlib import Path

repo = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo / "scripts"))

import policy_engine as pe


def _with_market_hours_disabled():
    config = pe.POLICY["trading"]["time_restrictions"]["market_hours_only"]
    original = config.get("enabled", True)
    config["enabled"] = False
    return config, original


def test_check_share_count_blocks_when_over_limit():
    config, original = _with_market_hours_disabled()
    try:
        result = pe.validate_trade({"symbol": "AAPL", "qty": 101, "side": "buy", "price": 10}, "trader")
        assert result["all_passed"] is False
        assert "share_count_limit" in result["failed_checks"]
    finally:
        config["enabled"] = original


def test_check_share_count_allows_at_limit():
    config, original = _with_market_hours_disabled()
    try:
        result = pe.validate_trade({"symbol": "AAPL", "qty": 100, "side": "buy", "price": 10}, "trader")
        assert "share_count_limit" not in result["failed_checks"]
    finally:
        config["enabled"] = original
