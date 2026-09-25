"""Frozen entry point for the customer-installed local application service."""

from __future__ import annotations

import multiprocessing


def main() -> None:
    multiprocessing.freeze_support()

    from app.main import run

    run()


if __name__ == "__main__":
    main()
