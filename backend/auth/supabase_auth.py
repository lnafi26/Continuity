"""Verify Supabase user sessions before privileged backend operations.

Do not trust a user_id from the browser: this module asks Supabase Auth to
validate the access token and returns the verified auth.users.id. Backend
routes may then safely pass that identity to their privileged DB operations.
"""

from __future__ import annotations

from uuid import UUID
from urllib.parse import urlsplit

import requests


class AuthenticationError(Exception):
    """The request has no valid authenticated user (HTTP 401)."""


class AuthenticationUnavailable(Exception):
    """Supabase Auth could not be reached or configured (HTTP 503)."""


def verify_access_token(
    authorization_header: str | None,
    *,
    supabase_url: str,
    publishable_key: str,
    timeout: float = 6.0,
) -> str:
    """Return a verified Supabase user UUID, or fail closed.

    Uses Supabase Auth's GET /auth/v1/user endpoint so asymmetric and legacy
    JWT signing methods are both handled by the identity provider. Never
    log or persist the bearer token here. The publishable key is *not* an
    authentication credential; the end-user's token is always required.
    """
    if not isinstance(authorization_header, str):
        raise AuthenticationError("Authentication required.")
    scheme, separator, token = authorization_header.partition(" ")
    if (
        scheme.lower() != "bearer"
        or not separator
        or not token
        or any(ch.isspace() for ch in token)
        or len(token) > 8192
    ):
        raise AuthenticationError("A valid bearer token is required.")

    parsed = urlsplit(supabase_url.strip() if isinstance(supabase_url, str) else "")
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or not isinstance(publishable_key, str)
        or not publishable_key.strip()
    ):
        raise AuthenticationUnavailable("Supabase authentication is not configured.")

    try:
        response = requests.get(
            f"{parsed.scheme}://{parsed.netloc}/auth/v1/user",
            headers={
                "apikey": publishable_key,
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise AuthenticationUnavailable("Authentication service unavailable.") from exc

    if response.status_code in (400, 401, 403):
        raise AuthenticationError("Invalid or expired session.")
    if response.status_code != 200:
        raise AuthenticationUnavailable("Authentication service unavailable.")

    try:
        result = response.json()
        user_id = result.get("id") if isinstance(result, dict) else None
        return str(UUID(user_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AuthenticationUnavailable("Invalid authentication service response.") from exc
