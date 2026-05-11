"""Shared parsing helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from dateutil import parser as dateparser


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return dateparser.parse(value, fuzzy=True)
    except (ValueError, TypeError, OverflowError):
        return None


def parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None
