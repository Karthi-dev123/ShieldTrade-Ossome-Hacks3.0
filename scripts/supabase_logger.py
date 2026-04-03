"""Supabase audit logger helper.

Non-blocking by design: if Supabase is not configured or insert fails,
callers continue without errors.
"""

import os
import sys

_client = None
_MAX_STR_LEN = 2000


def _get_client():
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
        if not url or not key:
            return None
        from supabase import create_client

        _client = create_client(url, key)
    return _client


def _sanitize(record: dict) -> dict:
    output = {}
    for key, value in record.items():
        if isinstance(value, str) and len(value) > _MAX_STR_LEN:
            value = value[:_MAX_STR_LEN] + "...[truncated]"
        output[key] = value
    return output


def log(table: str, record: dict) -> str | None:
    client = _get_client()
    if client is None:
        return None

    try:
        response = client.table(table).insert(_sanitize(record)).execute()
        if response.data:
            return response.data[0].get("id")
    except Exception as exc:
        print(f"[supabase_logger] WARNING: audit write failed: {exc}", file=sys.stderr)

    return None
