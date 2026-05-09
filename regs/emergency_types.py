"""Shared types for the emergency-rule fetch + classify + apply pipeline.

Kept in a separate module so wdfw_emergency.py and emergency_classifier.py can
import them without depending on each other (avoids circular imports).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal


@dataclass(frozen=True)
class EmergencyRule:
    """A single WDFW emergency rule entry as fetched from the advanced-search page."""
    url: str
    title: str
    body: str
    effective_from: date | None
    effective_to: date | None
    modified_at: datetime


@dataclass(frozen=True)
class Classification:
    """Claude-API output for a single emergency rule."""
    section_ids: list[str]
    status: Literal["open", "closed"]
    effective_from: date | None
    effective_to: date | None
    confidence: float
    reasoning: str
