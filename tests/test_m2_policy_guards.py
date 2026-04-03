import json
import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "alpaca_bridge.py"


def _run_bridge(*args):
    env = dict(os.environ)
    env.setdefault("ALPACA_API_KEY", "DUMMY_KEY")
    env.setdefault("ALPACA_SECRET_KEY", "DUMMY_SECRET")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    output = (proc.stdout or proc.stderr).strip()
    payload = json.loads(output)
    return proc.returncode, payload


def test_invalid_order_side_is_blocked():
    code, payload = _run_bridge("order", "AAPL", "1", "hold")
    assert code == 0
    assert "error" in payload
    assert "Invalid side" in payload["error"]


def test_missing_order_args_is_rejected():
    code, payload = _run_bridge("order", "AAPL")
    assert code == 1
    assert "error" in payload
    assert "requires at least 3 argument(s)" in payload["error"]


def test_unknown_command_is_rejected():
    code, payload = _run_bridge("do-something")
    assert code == 1
    assert payload.get("error", "").startswith("Unknown command")
