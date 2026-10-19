"""Start either ThreadScan Python service from one frozen release runtime."""

from __future__ import annotations

import argparse
import multiprocessing
import os


def run_api() -> None:
    import uvicorn

    from main import app

    port = int(os.environ.get("THREADSCAN_API_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


def run_vision() -> None:
    from live_webcam_pipeline import run_service

    run_service()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a ThreadScan service.")
    parser.add_argument("service", choices=("api", "vision"))
    arguments = parser.parse_args()

    if arguments.service == "api":
        run_api()
    else:
        run_vision()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
