"""Temporary, loopback-only Continuity memory preview.

Requires the existing isolated local Supabase stack.
Never serves the raw frontend or contacts hosted Supabase.
"""

import functools
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
STAGING = Path.home() / "Desktop/Continuity-local-staging"

API = "http://127.0.0.1:21955"
BACKEND = "http://127.0.0.1:8765"
FRONTEND = "http://127.0.0.1:8000"


def public_key_from_status(output):
    from backend.memory.local_staging_boundary import (
        approved_local_memory_config,
    )

    values = {}
    for line in output.splitlines():
        if "=" in line:
            name, value = line.split("=", 1)
            values[name] = value.strip().strip('"').strip("'")

    if values.get("API_URL") != API:
        raise ValueError("Unexpected local Supabase endpoint.")

    key = values.get("ANON_KEY", "")

    if not approved_local_memory_config(API, key, enabled=True):
        raise ValueError("Local public API key rejected.")

    return key


def browser_config(key):
    from backend.memory.local_staging_boundary import (
        approved_local_memory_config,
    )

    if not approved_local_memory_config(API, key, enabled=True):
        raise ValueError("Invalid local public API key.")

    return (
        "window.SUPABASE_CONFIG = " +
        json.dumps({
            "url": API,
            "publishableKey": key,
            "oauthBaseUrl": "",
        }) + ";\n" +
        "window.CONTINUITY_MEMORY_API_BASE = " +
        json.dumps(BACKEND) + ";\n"
    )


def main():
    branch = subprocess.check_output(
        ["git", "-C", str(ROOT), "branch", "--show-current"],
        text=True,
    ).strip()

    if branch != "feat/continuity-local-memory-bridge":
        raise RuntimeError("Unexpected development branch.")

    print("=== Verify isolated local services ===", flush=True)

    for port in (8000, 8765):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))

    with socket.create_connection(("127.0.0.1", 21955), 3):
        pass

    result = subprocess.run(
        ["supabase", "status", "--env"],
        cwd=STAGING,
        capture_output=True,
        text=True,
    )

    if result.returncode:
        raise RuntimeError("Local Supabase status unavailable.")

    key = public_key_from_status(result.stdout)
    print("PASS: Local Supabase and public key verified.")

    with tempfile.TemporaryDirectory(
        prefix="continuity-memory-preview-"
    ) as temporary:

        site = Path(temporary) / "site"
        fake_ref = "abcdefghijklmnopqrst"

        env = os.environ.copy()
        env.update({
            "CONTINUITY_STAGING_SUPABASE_PROJECT_REF": fake_ref,
            "CONTINUITY_STAGING_SUPABASE_URL":
                f"https://{fake_ref}.supabase.co",
            "CONTINUITY_STAGING_SUPABASE_PUBLISHABLE_KEY":
                "sb_publishable_" + "a" * 32,
        })

        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/build_staging_app.py"),
                "--output",
                str(site),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            check=True,
        )

        files = [p for p in site.rglob("*") if p.is_file()]
        if len(files) != 21:
            raise RuntimeError("Unexpected staging artifact contents.")

        config_file = site / "config/supabase-config.js"
        if not config_file.is_file():
            raise RuntimeError("Staging configuration missing.")

        config_file.write_text(browser_config(key))

        os.environ.update({
            "SUPABASE_URL": API,
            "SUPABASE_PUBLISHABLE_KEY": key,
            "CONTINUITY_ENABLE_LOCAL_MEMORY_BRIDGE": "true",
            "CONTINUITY_ENABLE_LEGACY_PIPELINE": "false",
            "SUPABASE_DATABASE_URL": "",
            "GOOGLE_CLIENT_ID": "",
            "GOOGLE_CLIENT_SECRET": "",
            "TOKEN_ENCRYPTION_KEY": "",
            "DEFAULT_TEST_USER_ID": "",
            "OAUTH_SERVER_HOST": "127.0.0.1",
            "OAUTH_SERVER_PORT": "8765",
        })

        from backend.auth import server
        from werkzeug.serving import (
            make_server,
            WSGIRequestHandler,
        )

        assert server.config.auth_ready
        assert server.config.allow_local_memory
        assert server.config.supabase_url == API
        assert not server.config.pipeline_ready
        assert not server.config.oauth_ready
        assert FRONTEND in server._ALLOWED_ORIGINS

        # Live unauthenticated check. No existing project ID required.
        endpoint = (
            f"/memory/projects/{uuid4()}/context"
        )
        result = server.app.test_client().get(
            endpoint, headers={"Origin": FRONTEND}
        )

        assert result.status_code == 401
        assert result.headers.get(
            "Access-Control-Allow-Origin"
        ) == FRONTEND
        assert result.headers.get(
            "Cache-Control"
        ) == "private, no-store"

        class QuietStatic(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        class QuietWSGI(WSGIRequestHandler):
            def log(self, *args):
                pass

        frontend = ThreadingHTTPServer(
            ("127.0.0.1", 8000),
            functools.partial(
                QuietStatic, directory=str(site)
            ),
        )

        backend = make_server(
            "127.0.0.1",
            8765,
            server.app,
            request_handler=QuietWSGI,
        )

        try:
            for service in (frontend, backend):
                threading.Thread(
                    target=service.serve_forever,
                    daemon=True,
                ).start()

            print("PASS: Memory authentication boundary verified.")
            print("PASS: Temporary frontend memory flag enabled.")
            print()
            print("CONTINUITY MEMORY PREVIEW READY")
            print("Frontend:", FRONTEND)
            print("Backend:", BACKEND)
            print("Supabase:", API)
            print()
            print("Ctrl+C stops this preview.", flush=True)

            threading.Event().wait()

        except KeyboardInterrupt:
            print("\nStopping local preview.")

        finally:
            frontend.shutdown()
            backend.shutdown()
            frontend.server_close()
            backend.server_close()

    print("Temporary preview removed. Supabase data preserved.")


if __name__ == "__main__":
    main()
