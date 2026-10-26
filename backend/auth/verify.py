"""Stage 0 verification CLI.

Proves that a Connect & Authorize result actually works, end to end:

  python3 backend/auth/verify.py doctor            # config + DB preflight
  python3 backend/auth/verify.py list              # show stored connections
  python3 backend/auth/verify.py verify            # test every connection
  python3 backend/auth/verify.py verify --provider gmail

For each connection it: loads the encrypted token from source_secrets (proving
the encryption round-trips), refreshes it if expired, calls the matching Google
API to confirm the grant is live, and updates source_connections.status to
'active' on success or 'error' (with last_error) on failure.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import connections_repo
from config import USERINFO_ENDPOINT, VALID_PROVIDERS, load_config
from token_store import TokenStore, TokenStoreError


def _resolve_user_id(config, explicit: str | None) -> str | None:
    user_id = (explicit or config.default_test_user_id or "").strip()
    if not user_id or user_id == "00000000-0000-0000-0000-000000000000":
        return None
    return user_id


def cmd_doctor(args, config) -> int:
    print("Stage 0 doctor")
    print("-" * 40)
    ok = True

    if config.is_complete:
        print("config: OK (all required values present)")
    else:
        ok = False
        print("config: MISSING ->", ", ".join(config.missing))

    print(f"redirect_uri: {config.redirect_uri}")

    # Database reachability + the token table being backend-only.
    try:
        with psycopg.connect(config.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("select 1")
                cursor.fetchone()
                cursor.execute(
                    "select relrowsecurity from pg_class "
                    "where relname = 'source_secrets' "
                    "and relnamespace = 'public'::regnamespace"
                )
                row = cursor.fetchone()
        print("database: OK (connected)")
        if row is None:
            ok = False
            print("source_secrets: MISSING -> run "
                  "`--title create_source_secrets_table`")
        elif not row[0]:
            ok = False
            print("source_secrets: INSECURE -> RLS is disabled")
        else:
            print("source_secrets: OK (exists, RLS enabled)")
    except psycopg.Error as error:
        ok = False
        print("database: FAIL ->", error)

    # Encryption key usable.
    try:
        TokenStore(config.token_encryption_key, config.database_url)
        print("encryption: OK (TOKEN_ENCRYPTION_KEY is a valid Fernet key)")
    except TokenStoreError as error:
        ok = False
        print("encryption: FAIL ->", error)

    user_id = _resolve_user_id(config, args.user_id)
    print(f"test user: {'OK ' + user_id if user_id else 'not set'}")

    print("-" * 40)
    print("RESULT:", "READY" if ok else "NOT READY")
    return 0 if ok else 1


def cmd_list(args, config) -> int:
    config.require_complete()
    user_id = _resolve_user_id(config, args.user_id)
    rows = connections_repo.list_connections(config.database_url, user_id)
    if not rows:
        print("No connections found. Connect an account at "
              f"http://{config.host}:{config.port} first.")
        return 0
    store = TokenStore(config.token_encryption_key, config.database_url)
    print(f"{'PROVIDER':<17}{'EMAIL':<32}{'STATUS':<12}TOKEN")
    for c in rows:
        try:
            has_token = store.get(c.id) is not None
        except TokenStoreError:
            has_token = None
        token_state = {True: "stored", False: "MISSING", None: "undecryptable"}[has_token]
        print(f"{c.provider:<17}{c.account_email:<32}{c.status:<12}{token_state}")
    return 0


def _load_credentials(record: dict) -> Credentials:
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


def _probe_provider(provider: str, access_token: str) -> str:
    """Call the matching read-only API and return a short proof string."""
    headers = {"Authorization": f"Bearer {access_token}"}
    if provider == "gmail":
        resp = requests.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return (
            f"mailbox {data.get('emailAddress')}, "
            f"{data.get('messagesTotal')} messages total"
        )
    if provider == "google_calendar":
        resp = requests.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            headers=headers,
            params={"maxResults": 10},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return f"{len(items)} calendar(s) visible"
    # Fallback: identity only.
    resp = requests.get(USERINFO_ENDPOINT, headers=headers, timeout=15)
    resp.raise_for_status()
    return f"account {resp.json().get('email')}"


def cmd_verify(args, config) -> int:
    config.require_complete()
    user_id = _resolve_user_id(config, args.user_id)
    rows = connections_repo.list_connections(config.database_url, user_id)
    if args.provider:
        rows = [c for c in rows if c.provider == args.provider]
    if not rows:
        target = f" for provider '{args.provider}'" if args.provider else ""
        print(f"No connections{target}. Connect an account first at "
              f"http://{config.host}:{config.port}.")
        return 1

    store = TokenStore(config.token_encryption_key, config.database_url)
    all_ok = True

    for c in rows:
        print(f"\n[{c.provider}] {c.account_email}  (connection {c.id})")
        try:
            record = store.get(c.id)
            if record is None:
                raise TokenStoreError("no encrypted token stored for this connection")
            print("  token: decrypted from source_secrets OK")

            creds = _load_credentials(record)
            if creds.expiry is None or creds.expired:
                if not creds.refresh_token:
                    raise RuntimeError(
                        "access token expired and no refresh token; reconnect"
                    )
                creds.refresh(Request())
                record["token"] = creds.token
                record["expiry"] = creds.expiry.isoformat() if creds.expiry else None
                store.put(c.id, c.user_id, record)
                print("  token: refreshed and re-encrypted OK")
            else:
                print("  token: still valid, no refresh needed")

            proof = _probe_provider(c.provider, creds.token)
            print(f"  google api: OK -> {proof}")

            connections_repo.set_status(config.database_url, c.id, "active", None)
            print("  status: active")
        except Exception as error:  # noqa: BLE001 - report and continue to next
            all_ok = False
            message = str(error)
            connections_repo.set_status(config.database_url, c.id, "error", message[:500])
            print(f"  FAILED -> {message}")
            print("  status: error (recorded in last_error)")

    print("\n" + ("ALL CONNECTIONS OK" if all_ok else "SOME CONNECTIONS FAILED"))
    return 0 if all_ok else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 0 Connect & Authorize verifier.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="Check config, database, and encryption.")
    p_doctor.add_argument("--user-id", dest="user_id", default=None)

    p_list = sub.add_parser("list", help="List stored connections.")
    p_list.add_argument("--user-id", dest="user_id", default=None)

    p_verify = sub.add_parser("verify", help="Refresh tokens and call Google.")
    p_verify.add_argument("--provider", choices=VALID_PROVIDERS, default=None)
    p_verify.add_argument("--user-id", dest="user_id", default=None)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    if args.command == "doctor":
        return cmd_doctor(args, config)
    if args.command == "list":
        return cmd_list(args, config)
    if args.command == "verify":
        return cmd_verify(args, config)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
