from datetime import UTC, datetime  # type: ignore


def utc_now_iso() -> str:

    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
