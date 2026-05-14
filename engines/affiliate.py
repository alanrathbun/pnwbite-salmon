"""Affiliate-link URL builder.

Pure function. Reads credentials from environment variables at call time
so tests can manipulate them with monkeypatch. Returns zero, one, or two
AffiliateLink entries depending on which vendors are configured. When
both vendors are configured, Amazon comes first, then Sportsman's
Warehouse via AvantLink — the order is deterministic so render-layer
snapshots are stable.

Vendor: 'amzn' (Amazon Associates) | 'spwh' (Sportsman's Warehouse via
AvantLink). AvantLink requires BOTH `AVANTLINK_AFFILIATE_ID` and
`AVANTLINK_SPWH_MERCHANT_ID`; if either is missing the spwh link is
omitted.

Sub-tag format: `<launch_key>__<species>` — double underscore avoids
collisions with launch keys that contain a single underscore.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass(frozen=True)
class AffiliateLink:
    vendor: str   # "amzn" | "spwh"
    url: str
    label: str    # short text shown in the badge
    title: str    # tooltip / aria text


_AMAZON_BASE = "https://www.amazon.com/s"
_AVANTLINK_BASE = "https://www.avantlink.com/click.php"
_SPWH_SEARCH_BASE = "https://www.sportsmans.com/search"


def _amazon_link(query: str, *, tag: str, subtag: str) -> AffiliateLink:
    qs = urlencode({"k": query, "tag": tag, "ascsubtag": subtag})
    return AffiliateLink(
        vendor="amzn",
        url=f"{_AMAZON_BASE}?{qs}",
        label="amzn",
        title="Search Amazon (affiliate link)",
    )


def _spwh_link(
    query: str, *, affiliate_id: str, merchant_id: str, subtag: str,
) -> AffiliateLink:
    target = f"{_SPWH_SEARCH_BASE}?{urlencode({'query': query})}"
    qs = urlencode({
        "tt": "cl",
        "merchant_id": merchant_id,
        "affiliate_id": affiliate_id,
        "url": target,
        "pat": subtag,
    })
    return AffiliateLink(
        vendor="spwh",
        url=f"{_AVANTLINK_BASE}?{qs}",
        label="spwh",
        title="Search Sportsman's Warehouse (affiliate link)",
    )


def links_for(query: str, *, launch_key: str, species: str) -> list[AffiliateLink]:
    """Build affiliate links for a gear search phrase.

    Caller composes the search phrase (e.g. f"{value} {key}" from a gear
    dict entry → "hot pink size 4 flasher"). Returns a list ordered
    [amzn, spwh]; either vendor may be omitted when its credentials are
    not configured.
    """
    if not query.strip():
        return []
    subtag = f"{launch_key}__{species}"
    out: list[AffiliateLink] = []

    amazon_tag = (os.environ.get("AMAZON_AFFILIATE_TAG") or "").strip()
    if amazon_tag:
        out.append(_amazon_link(query, tag=amazon_tag, subtag=subtag))

    aid = (os.environ.get("AVANTLINK_AFFILIATE_ID") or "").strip()
    mid = (os.environ.get("AVANTLINK_SPWH_MERCHANT_ID") or "").strip()
    if aid and mid:
        out.append(_spwh_link(query, affiliate_id=aid, merchant_id=mid, subtag=subtag))

    return out
