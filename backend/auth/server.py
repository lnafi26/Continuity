"""Stage 0 OAuth server: Connect & Authorize Gmail + Google Calendar.

A small local Flask app that runs the Google OAuth 2.0 authorization-code flow:

  GET  /                        landing page with connect buttons
  GET  /health                  config/readiness check (no secrets leaked)
  GET  /auth/google/start       redirect the user to Google's consent screen
  GET  /auth/google/callback    exchange the code, store token, upsert connection
  GET  /connections             list this user's connections (metadata only)

Run it with:  python3 backend/auth/server.py
Then open:    http://localhost:8765

The client secret and the resulting tokens never reach the browser: the secret
stays in this process, and tokens are encrypted into the source_secrets table.
"""

from __future__ import annotations

import html
import secrets
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

# Allow running directly (python3 backend/auth/server.py): make sibling modules
# importable regardless of the caller's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests
from flask import Flask, jsonify, redirect, request
from google_auth_oauthlib.flow import Flow

import connections_repo
from config import USERINFO_ENDPOINT, VALID_PROVIDERS, load_config
from token_store import TokenStore
from supabase_auth import (
    AuthenticationError,
    AuthenticationUnavailable,
    verify_access_token,
)

config = load_config()
app = Flask(__name__)

# repo_root/backend/auth/server.py -> repo_root.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Stages 1-7, in order, run as subprocesses -- not imported in-process, since
# each stage script does its own `sys.path.insert` + `import config` and
# co-importing several into one long-running Flask process would collide on
# those identically-named local modules. A subprocess per stage is exactly
# what already works from the terminal, just triggered by a click instead.
PIPELINE_STEPS: list[tuple[str, list[str]]] = [
    ("sync", ["backend/ingest/sync.py", "run"]),
    ("normalize", ["backend/normalize/normalize.py", "run"]),
    ("dedupe", ["backend/dedupe/dedupe.py", "run"]),
    ("embed", ["backend/embed/relate.py", "embed"]),
    ("relate", ["backend/embed/relate.py", "relate"]),
    ("group", ["backend/grouping/group.py", "run"]),
    ("extract", ["backend/extract/extract.py", "run"]),
    ("digest", ["backend/digest/summarize.py", "run"]),
]

# Trusted frontend origins: local dev, plus the deployed Cloudflare site.
# Used both for CORS on /pipeline/run (the one route reached via fetch()
# rather than a full-page redirect, so it needs its own CORS allowance) and
# for _safe_return_to's open-redirect guard below -- same trust boundary,
# one list.
_ALLOWED_ORIGINS = {
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}


@app.after_request
def _add_cors_headers(resp):
    origin = request.headers.get("Origin", "")
    if origin in _ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        resp.headers["Vary"] = "Origin"
    return resp

# Short-lived CSRF/state store: maps the opaque `state` value we send to Google
# to the request context we need back on the callback. In-memory is fine for a
# single-process local demo; entries expire after STATE_TTL seconds.
_pending: dict[str, dict] = {}
STATE_TTL = 600


def _clean_pending() -> None:
    now = time.time()
    for key in [k for k, v in _pending.items() if now - v["created_at"] > STATE_TTL]:
        _pending.pop(key, None)


def _safe_return_to(url: str | None) -> str | None:
    """Accept only a fully parsed, exactly trusted frontend origin."""
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlsplit(url)
        if parsed.username or parsed.password or not parsed.netloc:
            return None
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return url if origin in _ALLOWED_ORIGINS else None
    except ValueError:
        return None


@app.errorhandler(AuthenticationError)
def _auth_invalid(exc: AuthenticationError):
    return jsonify(ok=False, error=str(exc)), 401


@app.errorhandler(AuthenticationUnavailable)
def _auth_unavailable(exc: AuthenticationUnavailable):
    return jsonify(ok=False, error=str(exc)), 503


def _authenticated_user() -> str:
    """Return only the ID verified by Supabase Auth, never a client-provided ID."""
    return verify_access_token(
        request.headers.get("Authorization"),
        supabase_url=config.supabase_url,
        publishable_key=config.supabase_publishable_key,
    )



def _build_flow(scopes: list[str], state: str | None = None) -> Flow:
    flow = Flow.from_client_config(
        config.client_config(), scopes=scopes, state=state
    )
    flow.redirect_uri = config.redirect_uri
    return flow


def _page(title: str, body: str, status: int = 200):
    return (
        f"<!doctype html><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        f"<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:640px;"
        f"margin:3rem auto;padding:0 1rem;color:#222}}"
        f"a.btn,button{{display:inline-block;background:#4263eb;color:#fff;"
        f"text-decoration:none;padding:.6rem 1rem;border-radius:8px;border:0;"
        f"font-size:1rem;cursor:pointer;margin:.25rem .25rem 0 0}}"
        f"code{{background:#f2f4f7;padding:.1rem .3rem;border-radius:4px}}"
        f".ok{{color:#067647}}.err{{color:#b42318}}</style>{body}",
        status,
    )


@app.get("/health")
def health():
    """Core service readiness. Does not require optional Google or Claude."""
    lines = [
        f"auth_ready: {config.auth_ready}",
        f"database_configured: {config.database_ready}",
        f"google_integration_ready: {config.oauth_ready}",
        f"legacy_pipeline_enabled: {config.pipeline_enabled}",
    ]
    if config.auth_missing:
        lines.append("missing_core: " + ", ".join(config.auth_missing))
    return (
        "\n".join(lines),
        200 if config.auth_ready else 503,
        {"Content-Type": "text/plain"},
    )


@app.get("/auth/session")
def auth_session():
    """Safe read-only endpoint for verifying a live Supabase bearer token."""
    user_id = _authenticated_user()
    return jsonify(ok=True, user_id=user_id)


@app.get("/")
def index():
    return _page(
        "Continuity backend",
        "<h1>Continuity backend</h1>"
        "<p>Use the authenticated Continuity frontend to connect services.</p>",
    )



@app.post("/auth/google/start")
def auth_start():
    user_id = _authenticated_user()
    if not config.oauth_ready:
        return jsonify(ok=False, error="Server not configured."), 503

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(ok=False, error="Expected JSON object."), 400
    raw = payload.get("providers", "gmail")
    if not isinstance(raw, str):
        return jsonify(ok=False, error="providers must be a string."), 400
    providers = [p.strip() for p in raw.split(",") if p.strip()]
    invalid = [p for p in providers if p not in VALID_PROVIDERS]
    if not providers or invalid:
        return _page(
            "Bad request",
            "<p class='err'>Unknown provider(s): "
            + html.escape(", ".join(invalid or ["(none given)"]))
            + f". Valid: {', '.join(VALID_PROVIDERS)}.</p>",
            400,
        )



    scopes = config.scopes_for(providers)
    state = secrets.token_urlsafe(24)
    flow = _build_flow(scopes, state=state)
    auth_url, _ = flow.authorization_url(
        access_type="offline",       # ask for a refresh token
        include_granted_scopes="true",
        prompt="consent",            # force refresh-token issuance every time
    )

    _clean_pending()
    _pending[state] = {
        "providers": providers,
        "user_id": user_id,
        "scopes": scopes,
        # PKCE: the verifier generated here must be replayed at token exchange.
        "code_verifier": flow.code_verifier,
        "return_to": _safe_return_to(payload.get("return_to")),
        "created_at": time.time(),
    }
    return jsonify(ok=True, authorization_url=auth_url)


@app.get("/auth/google/callback")
def auth_callback():
    error = request.args.get("error")
    if error:
        return _page(
            "Consent declined",
            f"<p class='err'>Google returned: {html.escape(error)}</p>",
            400,
        )

    state = request.args.get("state", "")
    _clean_pending()
    pending = _pending.pop(state, None)
    if pending is None:
        return _page(
            "Expired",
            "<p class='err'>This authorization link is invalid or expired. "
            "Start again from the home page.</p>",
            400,
        )

    flow = _build_flow(pending["scopes"], state=state)
    # Replay the PKCE verifier from the start step so Google accepts the code.
    flow.code_verifier = pending.get("code_verifier")
    try:
        flow.fetch_token(authorization_response=request.url)
    except Exception as exc:  # noqa: BLE001 - surface any exchange failure to the tester
        return _page(
            "Token exchange failed",
            f"<p class='err'>{html.escape(str(exc))}</p>",
            400,
        )

    creds = flow.credentials

    # Identify the Google account so we can fill provider_account_id + email.
    try:
        resp = requests.get(
            USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=15,
        )
        resp.raise_for_status()
        userinfo = resp.json()
    except requests.RequestException as exc:
        return _page(
            "Identity lookup failed",
            f"<p class='err'>{html.escape(str(exc))}</p>",
            502,
        )

    google_sub = userinfo.get("sub")
    account_email = userinfo.get("email", "")
    if not google_sub:
        return _page(
            "Identity lookup failed",
            "<p class='err'>Google did not return an account id.</p>",
            502,
        )

    token_record = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or pending["scopes"]),
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }

    store = TokenStore(config.token_encryption_key, config.database_url)

    connected = []
    for provider in pending["providers"]:
        connection_id = connections_repo.upsert_connection(
            config.database_url,
            user_id=pending["user_id"],
            provider=provider,
            provider_account_id=google_sub,
            account_email=account_email,
            status="active",
        )
        # Both providers from a single consent share the same underlying grant,
        # so the same token record is stored under each connection id.
        store.put(connection_id, pending["user_id"], token_record)
        connected.append((provider, connection_id))

    # If the browser came from the app, return there so it can refresh the
    # "Connected" state instead of stranding the user on this backend page.
    return_to = pending.get("return_to")
    if return_to:
        sep = "&" if "?" in return_to else "?"
        joined = ",".join(p for p, _ in connected)
        return redirect(f"{return_to}{sep}connected={joined}")

    rows = "".join(
        f"<li><b>{html.escape(p)}</b> &rarr; connection "
        f"<code>{html.escape(cid)}</code></li>"
        for p, cid in connected
    )
    got_refresh = "yes" if creds.refresh_token else "NO (re-consent needed)"
    return _page(
        "Connected",
        "<h1 class='ok'>Connected ✓</h1>"
        f"<p>Account: <code>{html.escape(account_email)}</code></p>"
        f"<p>Refresh token received: <b>{got_refresh}</b></p>"
        f"<ul>{rows}</ul>"
        "<p>Tokens are encrypted in <code>source_secrets</code>; only "
        "non-secret metadata is in <code>source_connections</code>.</p>"
        "<p><a href='/connections'>View connections</a> &middot; "
        "<a href='/'>Home</a></p>"
        "<p>Now verify from the terminal:<br>"
        "<code>python3 backend/auth/verify.py verify --provider gmail</code></p>",
    )


@app.get("/connections")
def connections():
    user_id = _authenticated_user()
    if not config.database_ready:
        return jsonify(ok=False, error="Database connection not configured."), 503

    rows = connections_repo.list_connections(config.database_url, user_id)
    if not rows:
        body = "<p>No connections yet. <a href='/'>Connect an account.</a></p>"
    else:
        items = "".join(
            f"<li><b>{html.escape(c.provider)}</b> &mdash; "
            f"{html.escape(c.account_email)} &mdash; "
            f"<span class={'ok' if c.status == 'active' else 'err'!r}>"
            f"{html.escape(c.status)}</span>"
            f"{(' &mdash; ' + html.escape(c.last_error)) if c.last_error else ''}</li>"
            for c in rows
        )
        body = f"<ul>{items}</ul>"
    return _page(
        "Connections", "<h1>Connections</h1>" + body + "<p><a href='/'>Home</a></p>"
    )


@app.route("/pipeline/run", methods=["POST", "OPTIONS"])
def pipeline_run():
    """Run Stages 1-7 for one user, synchronously, as the "Scan for updates"
    button's real handler -- exactly the CLI sequence documented for manual
    testing, just triggered by a click instead of eight terminal commands.

    Each stage runs as its own subprocess (see PIPELINE_STEPS) and every
    stage is attempted regardless of an earlier one failing: they're each
    idempotent/cheap when there's nothing new, so a stalled Gmail connection
    (say) still lets the rest of the pipeline report accurately instead of
    the whole run aborting on the first error.
    """
    if request.method == "OPTIONS":
        return "", 204
    user_id = _authenticated_user()
    if not config.pipeline_ready:
        return jsonify(ok=False, error="Legacy pipeline is disabled or not configured.", steps=[]), 503

    steps = []
    for name, argv in PIPELINE_STEPS:
        try:
            proc = subprocess.run(
                [sys.executable, *argv, "--user-id", user_id],
                cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=300,
            )
            steps.append({
                "stage": name,
                "ok": proc.returncode == 0,
                "output": (proc.stdout or "").strip(),
                "error": (proc.stderr or "").strip() if proc.returncode != 0 else "",
            })
        except subprocess.TimeoutExpired:
            steps.append({
                "stage": name, "ok": False, "output": "",
                "error": "Timed out after 300s.",
            })

    ok = all(s["ok"] for s in steps)
    return jsonify(ok=ok, steps=steps), (200 if ok else 207)


def main() -> None:
    if not config.auth_ready:
        print("WARNING: core authentication is not configured. Missing: "
              + ", ".join(config.auth_missing))
    else:
        print("Core Supabase authentication configured.")
    if not config.oauth_ready:
        print("Google OAuth is optional and currently unavailable.")
    if not config.pipeline_ready:
        print("Legacy processing pipeline is disabled (safe default).")
    print(f"Stage 0 OAuth server on http://{config.host}:{config.port}")
    print(f"Redirect URI (must be registered in Google): {config.redirect_uri}")
    app.run(host=config.host, port=config.port, debug=False)


if __name__ == "__main__":
    main()
