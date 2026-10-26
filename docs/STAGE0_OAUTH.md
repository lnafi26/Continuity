# Stage 0 — Connect & Authorize (Gmail + Google Calendar)

This stage lets a signed-in user connect Gmail and/or Google Calendar with
**read-only** permission, and records the result so later stages can sync.
It implements the Stage 0 spec in [Architecture.md](Architecture.md).

## What it produces

- A row in **`source_connections`** (public, non-secret): `provider`,
  `provider_account_id`, `account_email`, `status = 'active'`.
- The OAuth tokens, **encrypted**, in **`source_secrets`** (backend-only: RLS
  on, no policies — the browser can never read it).

The browser never sees the client secret or the tokens.

## Components

| File | Role |
|------|------|
| `backend/auth/config.py` | Env, read-only scopes, provider→scope map, validation |
| `backend/auth/token_store.py` | Encrypt/decrypt tokens ↔ `source_secrets` |
| `backend/auth/connections_repo.py` | Upsert / status / list on `source_connections` |
| `backend/auth/server.py` | Flask OAuth flow (start → Google → callback) |
| `backend/auth/verify.py` | CLI: `doctor` / `list` / `verify` |
| `frontend/assets/js/auth.js` | `startSourceConnection()` hands off to the server |

## One-time setup

### 1. Install dependencies
```bash
python3 -m pip install -r backend/requirements.txt
```

### 2. Create the token table (once per Supabase project)
```bash
python3 backend/database/supabase_connections.py --title create_source_secrets_table
python3 backend/database/supabase_connections.py --title check_source_secrets
# expect: source_secrets | READY (backend-only, no browser access)
```

### 3. Create a Google OAuth client
In [Google Cloud Console](https://console.cloud.google.com):
1. Create/select a project.
2. **APIs & Services → Library** → enable **Gmail API** and **Google Calendar API**.
3. **OAuth consent screen** → External → fill required fields → add your own
   Gmail address under **Test users**.
4. **Credentials → Create credentials → OAuth client ID → Web application**.
   Add this exact **Authorized redirect URI**:
   ```
   http://localhost:8765/auth/google/callback
   ```
5. Copy the **Client ID** and **Client secret**.

### 4. Fill `backend/.env`
```bash
GOOGLE_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...
OAUTH_REDIRECT_URI=http://localhost:8765/auth/google/callback
# generate: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
TOKEN_ENCRYPTION_KEY=...
# Supabase -> Authentication -> Users -> copy a user's UID
DEFAULT_TEST_USER_ID=...
```

> Keep `TOKEN_ENCRYPTION_KEY` stable. Changing it makes existing stored tokens
> undecryptable, forcing users to reconnect.

### 5. Set the backend URL for the frontend
`frontend/config/supabase-config.js` includes:
```js
oauthBaseUrl: "http://localhost:8765",
```

## Preflight check
```bash
python3 backend/auth/verify.py doctor
# expect: RESULT: READY
```
`doctor` checks config completeness, database reachability, that
`source_secrets` exists with RLS on, that the encryption key is valid, and that
a test user is set.

## Testing

### A. Standalone (backend only)
1. Start the server:
   ```bash
   python3 backend/auth/server.py
   ```
2. Open `http://localhost:8765`, click **Connect Gmail** (or Calendar, or both).
3. Complete Google consent with your test-user account.
4. You should land on a **Connected ✓** page showing the account email and
   "Refresh token received: yes".
5. Verify it actually works, end to end:
   ```bash
   python3 backend/auth/verify.py list
   python3 backend/auth/verify.py verify            # all connections
   python3 backend/auth/verify.py verify --provider gmail
   ```
   A passing `verify` prints, per connection: token decrypted → refreshed (or
   still valid) → a live Google call (e.g. `mailbox you@…, N messages total`),
   and sets `status = active`.

### B. Integrated with the home page
1. Keep the OAuth server running (`python3 backend/auth/server.py`).
2. In another terminal, serve the frontend:
   ```bash
   python3 -m http.server 8000 --directory frontend
   ```
3. Open `http://localhost:8000`, sign in.
4. Click **Connect apps → Connect** on Gmail or Google Calendar.
5. Complete consent. You are redirected back to the app, a toast confirms the
   connection, and the source shows **Connected** (read from
   `source_connections`).

## Verifying the security boundary
The tokens must never be reachable by the browser:
```bash
python3 backend/database/supabase_connections.py --title check_source_secrets
# READY (backend-only, no browser access)  ->  RLS on, zero policies
```
Only non-secret metadata lives in `source_connections`; ciphertext lives in
`source_secrets`, readable only via the backend's direct Postgres connection.

## Status lifecycle
`source_connections.status` moves through `active` → `expired` / `error` →
(after reconnect) `active`. `verify` sets `error` with `last_error` when a
refresh or API call fails, so problems are visible rather than silent.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `redirect_uri_mismatch` | The redirect URI in Google must match `OAUTH_REDIRECT_URI` exactly (http, localhost, port 8765, path). |
| Consent blocked / "not verified" | Add your Gmail as a **Test user** on the consent screen. |
| "Refresh token received: NO" | Revoke prior access at [myaccount.google.com/permissions](https://myaccount.google.com/permissions) and reconnect; the server already sends `prompt=consent`. |
| `/health` returns 503 | A required `.env` value is missing — the response lists which. |
| `verify` shows `undecryptable` | `TOKEN_ENCRYPTION_KEY` changed since the token was stored — reconnect. |
| Card doesn't flip to Connected | Ensure the signed-in Supabase user matches `user_id` used to connect; check the row exists via `verify.py list`. |

## Production hardening (later)
- Derive the user identity from a verified Supabase JWT instead of trusting the
  `user_id` query parameter.
- Replace the localhost `return_to` guard with an explicit allowlist of app
  origins.
- Move token storage to Supabase Vault or a managed secret store (the
  `TokenStore` interface is small enough to swap in place).
