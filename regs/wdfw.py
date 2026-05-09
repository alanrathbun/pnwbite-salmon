"""WDFW RegStatus dataclass — emergency-rules parsing was moved to regs/wdfw_emergency.py.

This file is kept so existing imports (e.g., `from regs.wdfw import RegStatus`)
continue to work after the refactor.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RegStatus:
    authority: str
    section_key: str
    open: bool
    reason: str
    last_checked: datetime
    effective_from: datetime | None = None
    effective_to: datetime | None = None


def fetch_status() -> list[RegStatus]:
    """Deprecated: emergency rules now flow through regs/wdfw_emergency.py + classifier."""
    return []
