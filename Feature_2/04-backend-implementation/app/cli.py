from __future__ import annotations

import argparse
from collections.abc import Sequence

import uvicorn

from app.config import Settings, get_settings
from app.main import create_application


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Garment Counter backend")
    parser.add_argument("--host", help="Bind host; production permits 127.0.0.1 only")
    parser.add_argument("--port", type=int, help="Bind port; defaults to configuration")
    parser.add_argument(
        "--log-level",
        choices=("debug", "info", "warning", "error", "critical"),
        help="Uvicorn log level",
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    return parser


def run_backend(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    resolved = settings or get_settings()
    arguments = build_parser().parse_args(argv)
    if arguments.version:
        print(resolved.application_version)
        return 0

    host = arguments.host or resolved.host
    port = arguments.port or resolved.port
    log_level = arguments.log_level or resolved.log_level.lower()
    if not 1 <= port <= 65535:
        raise SystemExit("Port must be between 1 and 65535")
    if resolved.environment == "production":
        if host != "127.0.0.1":
            raise SystemExit("Production backend must bind to 127.0.0.1")
        if resolved.api_token is None:
            raise SystemExit("Production backend requires GARMENT_COUNTER_API_TOKEN")

    uvicorn.run(
        create_application(resolved),
        host=host,
        port=port,
        log_level=log_level,
        access_log=resolved.environment != "production",
    )
    return 0


def main() -> None:
    raise SystemExit(run_backend())


if __name__ == "__main__":
    main()

