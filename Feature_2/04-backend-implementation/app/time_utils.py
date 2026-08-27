from datetime import UTC, datetime  # type: ignore


def utc_now_iso() -> str:

    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    """Parse a stored ISO-8601 value and normalize it to aware UTC."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed.astimezone(UTC)


def to_utc_iso(value: datetime) -> str:
    """Normalize an aware datetime to the database's UTC text format."""

    if value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
