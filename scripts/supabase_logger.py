"""Supabase audit logger — fire-and-forget helper.

Reads SUPABASE_URL and a Supabase JWT key from the environment:
SUPABASE_SERVICE_KEY (preferred for server-side inserts) or, if unset,
SUPABASE_ANON_KEY. The anon key only works if RLS policies allow inserts
into the audit tables; otherwise use the service_role key.

If URL or key is missing the call is silently skipped so the main
trading/policy flow is never blocked by an audit failure.

Returns the inserted row's id (str) on success, None otherwise.
"""

import os
import sys

_client = None
_client_init_attempted = False
_MAX_STR_LEN = 2000


def _get_client():
    global _client, _client_init_attempted
    if _client_init_attempted:
        return _client
    _client_init_attempted = True
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        _client = create_client(url, key)
    except Exception as exc:
        # supabase/httpcore may be incompatible with the current Python version.
        print(f"[supabase_logger] WARNING: supabase unavailable ({exc}), audit logging disabled", file=sys.stderr)
        _client = None
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
