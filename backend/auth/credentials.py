"""Shared helper: turn a stored token record into live Google credentials.

Used by both the Stage 0 verifier and the Stage 1 sync. Loads the encrypted
token for a connection, refreshes the access token if it has expired, persists
the refreshed token back to source_secrets, and returns ready-to-use
credentials. Keeping this in one place means every stage refreshes tokens the
same way.
"""

from __future__ import annotations

from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from token_store import TokenStore, TokenStoreError


def load_credentials(record: dict) -> Credentials:
    """Reconstruct google credentials from a stored token record."""
    creds = Credentials(
        token=record.get("token"),
        refresh_token=record.get("refresh_token"),
        token_uri=record.get("token_uri"),
        client_id=record.get("client_id"),
        client_secret=record.get("client_secret"),
        scopes=record.get("scopes"),
    )
    expiry = record.get("expiry")
    if expiry:
        # google-auth stores expiry as a naive UTC datetime.
        parsed = datetime.fromisoformat(expiry)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        creds.expiry = parsed
    return creds


def get_fresh_credentials(
    store: TokenStore, connection_id: str, user_id: str
) -> Credentials:
    """Return valid credentials for a connection, refreshing + persisting if needed.

    Raises TokenStoreError if no token is stored, or RuntimeError if the access
    token is expired and cannot be refreshed (caller should mark the connection
    'expired' and prompt a reconnect).
    """
    record = store.get(connection_id)
    if record is None:
        raise TokenStoreError(
            f"No encrypted token stored for connection {connection_id}."
        )

    creds = load_credentials(record)
    if creds.expiry is None or creds.expired:
        if not creds.refresh_token:
            raise RuntimeError(
                "Access token expired and no refresh token is available; reconnect."
            )
        creds.refresh(Request())
        record["token"] = creds.token
        record["expiry"] = creds.expiry.isoformat() if creds.expiry else None
        store.put(connection_id, user_id, record)
    return creds
