from datetime import UTC, datetime


def format_age(iso_timestamp: str) -> str:
    """Convert an ISO timestamp, return a human-readable age string (e.g. '3h ago', '2d ago')."""
    if not iso_timestamp:
        return ""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        delta = datetime.now(UTC) - dt
        total_seconds = int(delta.total_seconds())
    except (ValueError, TypeError):
        return iso_timestamp

    if total_seconds < 60:
        return f"{total_seconds}s ago"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"
