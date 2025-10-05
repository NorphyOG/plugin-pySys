"""Time utilities for timezone-aware UTC datetimes."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)

__all__ = ["utc_now"]
