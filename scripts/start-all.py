"""
ShieldTrade — Start Everything
Launches the Gemini proxy and OpenClaw gateway, keeps both alive.

Usage:
  python scripts/start-all.py
"""

import subprocess
import os
import sys
import time
import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, ".env")


def load_env() -> dict:
    env = {}
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


def main():
    env = load_env()
    full_env = {**os.environ, **env}

    print("[start-all] Starting Gemini proxy on port 4000...")
    proxy = subprocess.Popen(
        ["node", os.path.join(ROOT, "scripts", "proxy.js")],
        env=full_env,
    )
    time.sleep(2)
    if proxy.poll() is not None:
        print("[start-all] ERROR: proxy failed to start. Check your Gemini API keys.")
        sys.exit(1)
    print(f"[start-all] Proxy running (PID {proxy.pid})")

    print("[start-all] Starting OpenClaw gateway on port 18789...")
    gateway = subprocess.Popen(
        ["openclaw", "gateway", "run", "--force"],
        env={**full_env, "OPENCLAW_GATEWAY_TOKEN": env.get("OPENCLAW_GATEWAY_TOKEN", "")},
    )
    time.sleep(3)
    if gateway.poll() is not None:
        print("[start-all] ERROR: gateway failed to start.")
        proxy.terminate()
        sys.exit(1)
    print(f"[start-all] Gateway running (PID {gateway.pid})")
    print()
    print("[start-all] Both services up. Press Ctrl+C to stop.")

    def shutdown(sig, frame):
        print("\n[start-all] Shutting down...")
        proxy.terminate()
        gateway.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep alive — restart either process if it dies
    while True:
        time.sleep(5)
        if proxy.poll() is not None:
            print("[start-all] Proxy died — restarting...")
            proxy = subprocess.Popen(
                ["node", os.path.join(ROOT, "scripts", "proxy.js")],
                env=full_env,
            )
        if gateway.poll() is not None:
            print("[start-all] Gateway died — restarting...")
            gateway = subprocess.Popen(
                ["openclaw", "gateway", "run", "--force"],
                env=full_env,
            )


if __name__ == "__main__":
    main()
