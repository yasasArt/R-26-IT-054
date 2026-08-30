from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def test_real_sidecar_process_starts_and_requires_its_desktop_token(tmp_path: Path) -> None:
    token = "phase-two-process-smoke-test-token-1234567890"
    port = allocate_port()
    environment = {
        **os.environ,
        "GARMENT_COUNTER_PORT": str(port),
        "GARMENT_COUNTER_AUTH_TOKEN": token,
        "GARMENT_COUNTER_DATA_DIR": str(tmp_path / "data"),
        "GARMENT_COUNTER_MODEL_DIR": str(tmp_path),
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "app.main"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        with httpx.Client(trust_env=False, timeout=0.5) as client:
            response: httpx.Response | None = None

            for _ in range(50):
                if process.poll() is not None:
                    stderr = process.stderr.read().decode() if process.stderr else ""
                    raise AssertionError(f"The Python sidecar stopped before becoming ready: {stderr}")

                try:
                    response = client.get(
                        f"http://127.0.0.1:{port}/api/health",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    break
                except httpx.ConnectError:
                    time.sleep(0.1)

            assert response is not None, "The Python sidecar did not become available on localhost."
            assert response.status_code == 200
            assert response.json()["database"] == "ready"
            assert client.get(f"http://127.0.0.1:{port}/api/health").status_code == 401
    finally:
        process.terminate()

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
