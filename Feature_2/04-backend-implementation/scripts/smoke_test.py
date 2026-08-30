"""Start a source or packaged backend and verify its security/readiness contract."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def request_json(
    url: str,
    *,
    token: str | None = None,
    timeout: float = 2.0,
) -> tuple[int, dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def wait_until_ready(base_url: str, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status, body = request_json(f"{base_url}/health")
            if status == 200 and body.get("ready") is True:
                return body
        except (OSError, ValueError, json.JSONDecodeError) as error:
            last_error = error
        time.sleep(0.1)
    raise RuntimeError("Backend did not become ready") from last_error


def terminate(process: subprocess.Popen[str]) -> str:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    output, _ = process.communicate(timeout=2)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the local backend")
    parser.add_argument("--executable", type=Path, help="Packaged backend executable")
    parser.add_argument("--timeout", type=float, default=30.0)
    arguments = parser.parse_args(argv)

    if arguments.executable is not None:
        executable = arguments.executable.expanduser().resolve()
        if not executable.is_file():
            raise SystemExit(f"Packaged executable was not found: {executable}")
        command = [str(executable)]
    else:
        command = [sys.executable, "-m", "uvicorn", "app.main:app"]

    port = allocate_port()
    token = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="garment-backend-smoke-") as temp_dir:
        temporary = Path(temp_dir)
        environment = {
            **os.environ,
            "GARMENT_COUNTER_ENVIRONMENT": "production",
            "GARMENT_COUNTER_HOST": "127.0.0.1",
            "GARMENT_COUNTER_PORT": str(port),
            "GARMENT_COUNTER_API_TOKEN": token,
            "GARMENT_COUNTER_APP_DATA_DIR": str(temporary / "data"),
            "GARMENT_COUNTER_DATABASE_PATH": str(temporary / "data" / "smoke.db"),
            "GARMENT_COUNTER_LOAD_MODELS_ON_STARTUP": "false",
        }
        if arguments.executable is None:
            environment["GARMENT_COUNTER_MODELS_DIR"] = str(PROJECT_ROOT / "models")
        if arguments.executable is None:
            command += ["--host", "127.0.0.1", "--port", str(port)]

        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            wait_until_ready(base_url, arguments.timeout)
            anonymous_status, _ = request_json(f"{base_url}/api/health")
            if anonymous_status != 401:
                raise RuntimeError(f"Anonymous API returned HTTP {anonymous_status}")

            protected_status, protected = request_json(
                f"{base_url}/api/health",
                token=token,
            )
            if protected_status != 200 or protected.get("ready") is not True:
                raise RuntimeError("Authenticated health check failed")

            database_status, database = request_json(
                f"{base_url}/api/health/database",
                token=token,
            )
            if database_status != 200 or database.get("schema_version") != 3:
                raise RuntimeError("Database migration smoke check failed")

            model_status, models = request_json(
                f"{base_url}/api/models/status",
                token=token,
            )
            if model_status != 200 or "classifier" not in models:
                raise RuntimeError("Controlled model-status check failed")
        except Exception:
            logs = terminate(process)
            if logs:
                print(logs[-4000:], file=sys.stderr)
            raise
        finally:
            if process.poll() is None:
                terminate(process)

    print("SMOKE TEST PASSED")
    print("- public readiness: passed")
    print("- anonymous rejection: passed")
    print("- authenticated API: passed")
    print("- SQLite schema version 3: passed")
    print("- controlled model status: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
