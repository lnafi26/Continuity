"""Encrypted, backend-only storage for Google OAuth tokens.

Architecture.md Stage 0 requires OAuth access/refresh tokens to live in the
backend only -- never in the browser and never in the public `source_connections`
table. They are stored here in a dedicated `source_secrets` table that has Row
Level Security enabled with NO policies, so the browser's publishable key can
never read it; only this backend, using the direct Postgres connection (which
bypasses RLS), can. The token JSON is additionally encrypted with a Fernet key
before insert, so even a raw table read yields only ciphertext.

Keyed by `source_connections.id`. The interface (get/put/delete by connection
id) is deliberately small so the storage backend can be swapped later (for
example to Supabase Vault) without touching the rest of Stage 0.
"""

from __future__ import annotations

import json

import psycopg
from cryptography.fernet import Fernet, InvalidToken


class TokenStoreError(RuntimeError):
    pass


class TokenStore:
    """Encrypted key/value store: connection_id -> token record (a dict)."""

    def __init__(self, encryption_key: str, database_url: str):
        if not encryption_key:
            raise TokenStoreError("TOKEN_ENCRYPTION_KEY is not set.")
        if not database_url:
            raise TokenStoreError("SUPABASE_DATABASE_URL is not set.")
        try:
            self._fernet = Fernet(encryption_key.encode())
        except (ValueError, TypeError) as error:
            raise TokenStoreError(
                "TOKEN_ENCRYPTION_KEY is not a valid Fernet key. Generate one "
                "with: python3 -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            ) from error
        self._database_url = database_url

    def _encrypt(self, record: dict) -> str:
        return self._fernet.encrypt(json.dumps(record).encode("utf-8")).decode("utf-8")

    def _decrypt(self, ciphertext: str) -> dict:
        try:
            plaintext = self._fernet.decrypt(ciphertext.encode("utf-8"))
        except InvalidToken as error:
            raise TokenStoreError(
                "Cannot decrypt a stored token. The TOKEN_ENCRYPTION_KEY likely "
                "changed since it was written; the affected connection must "
                "reconnect."
            ) from error
        return json.loads(plaintext.decode("utf-8"))

    def put(self, connection_id: str, user_id: str, record: dict) -> None:
        """Insert or replace the encrypted token for a connection."""
        encrypted = self._encrypt(record)
        with psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.source_secrets
                        (connection_id, user_id, encrypted_token, updated_at)
                    values (%s, %s, %s, now())
                    on conflict (connection_id) do update
                        set encrypted_token = excluded.encrypted_token,
                            updated_at = now()
                    """,
                    (connection_id, user_id, encrypted),
                )

    def get(self, connection_id: str) -> dict | None:
        """Return the decrypted token record, or None if absent."""
        with psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select encrypted_token from public.source_secrets "
                    "where connection_id = %s",
                    (connection_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return self._decrypt(row[0])

    def delete(self, connection_id: str) -> None:
        with psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.source_secrets where connection_id = %s",
                    (connection_id,),
                )
