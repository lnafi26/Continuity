"""Stage 0 configuration: environment, OAuth scopes, and provider mapping.

Loads settings from backend/.env (same file the database runner uses) and
exposes them as a single validated Config object. Nothing here talks to Google
or Supabase; it only assembles and checks configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

# google-auth-oauthlib raises if Google returns a slightly different scope set
# than requested (Google always echoes back "openid"). Relaxing this avoids a
# spurious failure during the token exchange.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

# The redirect URI is http://localhost during local development, but oauthlib
# refuses to run OAuth over plain HTTP unless this is set. Safe for a local
# loopback address only; a deployed server must use https and drop this.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_FILE)

# Read-only scopes, matching Architecture.md Stage 0. userinfo.email + openid
# let us identify the Google account (stable "sub" id + email) so we can fill
# provider_account_id and account_email without any extra write access.
IDENTITY_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]
PROVIDER_SCOPES: dict[str, list[str]] = {
    "gmail": ["https://www.googleapis.com/auth/gmail.readonly"],
    "google_calendar": ["https://www.googleapis.com/auth/calendar.readonly"],
}
VALID_PROVIDERS = tuple(PROVIDER_SCOPES)

USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


@dataclass
class Config:
    google_client_id: str
    google_client_secret: str
    redirect_uri: str
    token_encryption_key: str
    database_url: str
    default_test_user_id: str
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    pipeline_enabled: bool = False
    host: str = "localhost"
    port: int = 8765
    missing: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """Legacy Google integration completeness (kept for verification CLI)."""
        return not self.missing

    @property
    def auth_missing(self) -> list[str]:
        """Core auth requires only the project URL and browser-safe API key."""
        missing = []
        try:
            parsed = urlsplit(self.supabase_url)
        except ValueError:
            return ["SUPABASE_URL"]
        if (
            parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or "PROJECT_REFERENCE" in self.supabase_url
        ):
            missing.append("SUPABASE_URL")
        if (
            not self.supabase_publishable_key.startswith("sb_publishable_")
            or "REPLACE_ME" in self.supabase_publishable_key
        ):
            missing.append("SUPABASE_PUBLISHABLE_KEY")
        return missing

    @property
    def auth_ready(self) -> bool:
        return not self.auth_missing

    @property
    def database_ready(self) -> bool:
        """Only means a DB connection string was supplied, not probed."""
        return bool(self.database_url) and not any(
            marker in self.database_url
            for marker in ("REPLACE_ME", "PROJECT_REFERENCE")
        )

    @property
    def oauth_ready(self) -> bool:
        return self.auth_ready and self.is_complete

    @property
    def pipeline_ready(self) -> bool:
        """The inherited Claude pipeline stays opt-in until decoupled."""
        return self.oauth_ready and self.pipeline_enabled

    def require_complete(self) -> None:
        if self.missing:
            raise ConfigError(
                "Missing required configuration: "
                + ", ".join(self.missing)
                + f". Set them in {ENV_FILE} (see backend/.env.example)."
            )

    def scopes_for(self, providers: list[str]) -> list[str]:
        """Union of identity scopes and the scopes for each requested provider."""
        scopes = list(IDENTITY_SCOPES)
        for provider in providers:
            if provider not in PROVIDER_SCOPES:
                raise ConfigError(
                    f"Unknown provider '{provider}'. "
                    f"Valid providers: {', '.join(VALID_PROVIDERS)}."
                )
            for scope in PROVIDER_SCOPES[provider]:
                if scope not in scopes:
                    scopes.append(scope)
        return scopes

    def client_config(self) -> dict:
        """Client config shaped for google_auth_oauthlib.flow.Flow."""
        return {
            "web": {
                "client_id": self.google_client_id,
                "client_secret": self.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri],
            }
        }


def load_config() -> Config:
    """Build a Config from the environment, recording (not raising on) gaps.

    Callers that only inspect configuration (for example the `doctor` command)
    can read `missing`; callers that need to run the flow call
    `require_complete()` first.
    """
    placeholders = {"", "REPLACE_ME", "00000000-0000-0000-0000-000000000000"}

    def read(name: str) -> str:
        value = (os.getenv(name) or "").strip()
        return value

    values = {
        "GOOGLE_CLIENT_ID": read("GOOGLE_CLIENT_ID"),
        "GOOGLE_CLIENT_SECRET": read("GOOGLE_CLIENT_SECRET"),
        "TOKEN_ENCRYPTION_KEY": read("TOKEN_ENCRYPTION_KEY"),
        "SUPABASE_DATABASE_URL": read("SUPABASE_DATABASE_URL"),
        "DEFAULT_TEST_USER_ID": read("DEFAULT_TEST_USER_ID"),
        "SUPABASE_URL": read("SUPABASE_URL"),
        "SUPABASE_PUBLISHABLE_KEY": read("SUPABASE_PUBLISHABLE_KEY"),
    }

    missing = [
        name
        for name, value in values.items()
        # DEFAULT_TEST_USER_ID is optional at import time; it can also be passed
        # per-request. Everything else is required to run the flow.
        if name not in (
            "DEFAULT_TEST_USER_ID", "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY"
        ) and (value in placeholders or value.endswith("REPLACE_ME"))
    ]

    host = read("OAUTH_SERVER_HOST") or "localhost"
    try:
        port = int(read("OAUTH_SERVER_PORT") or "8765")
    except ValueError:
        port = 8765
    redirect_uri = (
        read("OAUTH_REDIRECT_URI")
        or f"http://{host}:{port}/auth/google/callback"
    )

    return Config(
        google_client_id=values["GOOGLE_CLIENT_ID"],
        google_client_secret=values["GOOGLE_CLIENT_SECRET"],
        redirect_uri=redirect_uri,
        token_encryption_key=values["TOKEN_ENCRYPTION_KEY"],
        database_url=values["SUPABASE_DATABASE_URL"],
        default_test_user_id=values["DEFAULT_TEST_USER_ID"],
        supabase_url=values["SUPABASE_URL"],
        supabase_publishable_key=values["SUPABASE_PUBLISHABLE_KEY"],
        pipeline_enabled=read("CONTINUITY_ENABLE_LEGACY_PIPELINE").lower() == "true",
        host=host,
        port=port,
        missing=missing,
    )
