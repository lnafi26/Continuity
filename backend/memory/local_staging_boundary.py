"""Explicitly opt-in local Supabase memory boundary.

This module does not verify user sessions or make network calls.
Supabase Auth must still validate each user's bearer token.
"""

import base64
import json

LOCAL_SUPABASE_URL = "http://127.0.0.1:21955"


def is_public_api_key(value):
    """Reject known privileged keys, including legacy service-role JWTs."""
    if not isinstance(value, str) or not 10 < len(value) <= 8192:
        return False

    if value.startswith("sb_publishable_"):
        return len(value) > len("sb_publishable_")

    if value.startswith("sb_"):
        return False

    parts = value.split(".")
    if len(parts) != 3 or not all(parts):
        return False

    try:
        encoded = parts[1]
        decoded = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        )
        payload = json.loads(decoded)
    except (ValueError, UnicodeError, TypeError):
        return False

    # Classification only, never authentication.
    # The local Supabase server validates the actual API key.
    return isinstance(payload, dict) and payload.get("role") == "anon"


def approved_local_memory_config(url, api_key, *, enabled=False):
    """Allow only the exact isolated local endpoint, with explicit opt-in."""
    return (
        enabled is True
        and url == LOCAL_SUPABASE_URL
        and is_public_api_key(api_key)
    )
