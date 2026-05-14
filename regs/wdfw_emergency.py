"""WDFW emergency-rules advanced-search fetcher.

Pulls currently-effective emergency rules from
https://wdfw.wa.gov/fishing/regulations/emergency-rules/search and parses each
into an EmergencyRule. The downstream classifier (regs/emergency_classifier.py)
maps each rule to pamphlet section ids using Claude API.

The advanced-search page renders results inline as a Drupal Views list. Each
list item has the shape::

    <li>
      <div class="views-field views-field-field-expiration-date">
        <div class="field-content">
          <a href="/fishing/regulations/emergency-rules/...">Title text</a>
          - May 5, 2026
          to <time datetime="2026-10-15T12:00:00Z">Oct 15, 2026</time>
        </div>
      </div>
    </li>

The "from" date is plain text immediately after the anchor; the "to" date is a
``<time>`` element whose ``datetime`` attribute carries an ISO timestamp. We
prefer the ``datetime`` attribute when present and fall back to text parsing.

After parsing the listing page, each rule's detail page is fetched to extract
the full body text (``div.view-mode-full``). The listing-page body only contains
the title and date range; all geographic/date specifics live on the detail page.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Optional

from bs4 import BeautifulSoup

from regs.emergency_types import EmergencyRule
from utils import fetch

log = logging.getLogger("wdfw_emergency")

ADVANCED_SEARCH_URL = "https://wdfw.wa.gov/fishing/regulations/emergency-rules/search"


def parse_advanced_search(html: str) -> list[EmergencyRule]:
    """Parse the WDFW advanced-search HTML into a list of EmergencyRule entries.

    Selector strategy: locate ``div.view-content`` and iterate its ``li``
    children. Each ``li`` is a single emergency rule.
    """
    soup = BeautifulSoup(html, "lxml")
    rules: list[EmergencyRule] = []

    # The Views render wraps the list in div.view-content > div.item-list > ul.
    container = soup.select_one("div.view-content")
    if container is None:
        return rules

    for li in container.select("li"):
        title_el = li.select_one("a[href]")
        if title_el is None:
            continue
        href = title_el.get("href", "")
        if not href:
            continue
        url = href if href.startswith("http") else f"https://wdfw.wa.gov{href}"
        title = title_el.get_text(" ", strip=True)
        if not title:
            continue

        listing_body = li.get_text(" ", strip=True)
        eff_from, eff_to = _extract_dates(li, listing_body)
        modified_at = _extract_modified(li) or datetime.now()

        rules.append(EmergencyRule(
            url=url,
            title=title,
            body=listing_body[:2000],  # placeholder; enriched below in fetch_active_rules
            effective_from=eff_from,
            effective_to=eff_to,
            modified_at=modified_at,
        ))

    return rules


# --- date extraction helpers ----------------------------------------------

# Matches "Apr 30, 2026" / "April 30, 2026" / "Apr 30 2026" (comma optional).
_LOOSE_DATE_RE = re.compile(
    r"([A-Za-z]+\s+\d{1,2},?\s*\d{4})"
)
_DATE_RANGE_RE = re.compile(
    r"([A-Za-z]+\s+\d{1,2},?\s*\d{4})\s*"
    r"(?:-|to|through|–|—)\s*"
    r"([A-Za-z]+\s+\d{1,2},?\s*\d{4})",
    re.IGNORECASE,
)


def _extract_dates(li, body: str) -> tuple[Optional[date], Optional[date]]:
    """Pull (effective_from, effective_to) from a list-item.

    Strategy:
      1. If a ``<time datetime="...">`` element is present, use its
         ``datetime`` attribute as ``effective_to`` (this matches the Drupal
         Views render — the ``<time>`` element wraps the expiration date).
      2. Parse the leading "from" date out of the surrounding text.
      3. If a full date range is present in body text alone (no ``<time>``),
         parse both ends from text.
    """
    eff_to: Optional[date] = None
    time_el = li.find("time")
    if time_el is not None:
        iso = time_el.get("datetime")
        if iso:
            eff_to = _parse_iso_date(iso)
        if eff_to is None:
            txt = time_el.get_text(" ", strip=True)
            eff_to = _try_loose(txt)

    eff_from: Optional[date] = None
    # The "from" date appears between the title link and the "to" word/element.
    # Strip the title text first to avoid false matches inside the title.
    a = li.select_one("a[href]")
    after = body
    if a is not None:
        title_text = a.get_text(" ", strip=True)
        idx = body.find(title_text)
        if idx >= 0:
            after = body[idx + len(title_text):]

    # Try to find the first " - <date> to <date>" or " - <date>" in the tail.
    range_m = _DATE_RANGE_RE.search(after)
    if range_m:
        eff_from = _try_loose(range_m.group(1))
        if eff_to is None:
            eff_to = _try_loose(range_m.group(2))
    else:
        first_m = _LOOSE_DATE_RE.search(after)
        if first_m:
            eff_from = _try_loose(first_m.group(1))

    return eff_from, eff_to


def _try_loose(s: str) -> Optional[date]:
    try:
        return _parse_loose_date(s)
    except ValueError:
        return None


def _parse_loose_date(s: str) -> date:
    s = s.replace(",", "").strip()
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unparseable date: {s}")


def _parse_iso_date(iso: str) -> Optional[date]:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _extract_modified(li) -> datetime | None:
    """Best-effort: WDFW's Views markup does not expose a per-row modified
    timestamp on the search page, so we return None and let callers default
    to ``datetime.now()``. Kept as a hook in case the markup changes.
    """
    return None


# --- detail-page body extraction -------------------------------------------

def _fetch_detail_body(url: str) -> str:
    """Fetch a rule's detail page and return its main body text.

    Targets ``div.view-mode-full`` which Drupal uses for the full-node view.
    Falls back to ``div.field-name-body`` and then the raw page text. Returns
    an empty string on network or parse errors (the listing-page body remains
    as the fallback in that case).
    """
    try:
        html = fetch(url)
    except Exception as exc:
        log.warning("detail fetch failed for %s: %s", url, exc)
        return ""
    try:
        soup = BeautifulSoup(html, "lxml")
        for selector in ("div.view-mode-full", "div.field-name-body", "article"):
            el = soup.select_one(selector)
            if el:
                txt = el.get_text(" ", strip=True)
                if len(txt) > 100:
                    return txt[:4000]
    except Exception as exc:
        log.warning("detail parse failed for %s: %s", url, exc)
    return ""


# --- public fetch -----------------------------------------------------------

def fetch_active_rules(
    today: date,
    *,
    html: str | None = None,
    fetch_detail_pages: bool = True,
) -> list[EmergencyRule]:
    """Fetch the advanced-search page and return rules effective on ``today``.

    A rule is "active" when ``effective_from <= today <= effective_to``. If
    either bound is unknown (``None``) it's treated as open-ended on that side.

    ``html`` may be supplied directly to avoid network access (used by tests).

    When ``fetch_detail_pages`` is True (the default), each active rule's detail
    page is fetched to enrich the ``body`` field with the full rule text. Set to
    False in tests that supply pre-canned HTML to avoid extra network calls.
    """
    if html is None:
        html = fetch(ADVANCED_SEARCH_URL)
    all_rules = parse_advanced_search(html)
    active = [
        r for r in all_rules
        if (r.effective_from is None or r.effective_from <= today)
        and (r.effective_to is None or r.effective_to >= today)
    ]
    if not fetch_detail_pages:
        return active
    # Enrich body from detail pages (one request per active rule).
    enriched: list[EmergencyRule] = []
    for rule in active:
        detail_body = _fetch_detail_body(rule.url)
        if detail_body:
            rule = EmergencyRule(
                url=rule.url,
                title=rule.title,
                body=detail_body,
                effective_from=rule.effective_from,
                effective_to=rule.effective_to,
                modified_at=rule.modified_at,
            )
        enriched.append(rule)
    return enriched
