"""Supabase audit logger — fire-and-forget helper.

Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from the environment.
If either is missing the call is silently skipped so the main
trading/policy flow is never blocked by an audit failure.

Returns the inserted row's id (str) on success, None otherwise.
"""

import os
import sys

_client = None
_MAX_STR_LEN = 2000


def _get_client():
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            return None
        from supabase import create_client
        _client = create_client(url, key)
    return _client


def _sanitize(record: dict) -> dict:
    """Truncate oversized strings and coerce non-serializable values."""
    out = {}
    for k, v in record.items():
        if isinstance(v, str) and len(v) > _MAX_STR_LEN:
            v = v[:_MAX_STR_LEN] + "...[truncated]"
        out[k] = v
    return out


def log(table: str, record: dict) -> str | None:
    """Insert *record* into *table*. Returns the new row id or None."""
    client = _get_client()
    if client is None:
        return None

    try:
        response = client.table(table).insert(_sanitize(record)).execute()
        if response.data:
            return response.data[0].get("id")
    except Exception as exc:
        # Never let audit failures surface to the caller.
        print(f"[supabase_logger] WARNING: audit write failed: {exc}", file=sys.stderr)

    return None
