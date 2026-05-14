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
class Projection:
    """A single date-bounded open/closed window for one pamphlet section.

    Discrete dates: ``effective_from == effective_to``.
    Continuous range: ``effective_from <= effective_to``.
    Always-active: both fields None — used for legacy today-only scrapers
    (ODFW, IDFG) until they grow date-projection support.
    """
    section_id: str
    status: Literal["open", "closed"]
    effective_from: date | None
    effective_to: date | None
    reason: str
    authority: str


@dataclass(frozen=True)
class Classification:
    """Claude-API output for a single emergency rule.

    One rule may produce N projections — supports the common case where a
    single notice covers multiple sections with different open dates each
    (e.g. Snake Spring Chinook: Little Goose May 15+19, Ice Harbor May 20+21).
    """
    projections: list[Projection]
    confidence: float
    reasoning: str
