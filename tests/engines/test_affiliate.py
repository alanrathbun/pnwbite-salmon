"""Tests for engines.affiliate.links_for."""
from __future__ import annotations

import urllib.parse

from engines.affiliate import AffiliateLink, links_for


def _set_all(monkeypatch):
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "aff-123")
    monkeypatch.setenv("AVANTLINK_SPWH_MERCHANT_ID", "mid-456")


def _clear_all(monkeypatch):
    for k in (
        "AMAZON_AFFILIATE_TAG",
        "AVANTLINK_AFFILIATE_ID",
        "AVANTLINK_SPWH_MERCHANT_ID",
    ):
        monkeypatch.delenv(k, raising=False)


def test_both_vendors_returns_two_links_in_order(monkeypatch):
    _set_all(monkeypatch)
    out = links_for("hot pink flasher", launch_key="brewster", species="chinook")
    assert len(out) == 2
    assert out[0].vendor == "amzn"
    assert out[1].vendor == "spwh"
    assert all(isinstance(l, AffiliateLink) for l in out)


def test_no_credentials_returns_empty(monkeypatch):
    _clear_all(monkeypatch)
    assert links_for("anything", launch_key="x", species="y") == []


def test_only_amazon_set_returns_one_link(monkeypatch):
    _clear_all(monkeypatch)
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    out = links_for("hot pink flasher", launch_key="b", species="c")
    assert len(out) == 1
    assert out[0].vendor == "amzn"


def test_only_avantlink_set_returns_one_link(monkeypatch):
    _clear_all(monkeypatch)
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "aff-123")
    monkeypatch.setenv("AVANTLINK_SPWH_MERCHANT_ID", "mid-456")
    out = links_for("hot pink flasher", launch_key="b", species="c")
    assert len(out) == 1
    assert out[0].vendor == "spwh"


def test_avantlink_requires_both_vars(monkeypatch):
    """If only one of the AvantLink pair is set, drop spwh entirely."""
    _clear_all(monkeypatch)
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "aff-123")
    # AVANTLINK_SPWH_MERCHANT_ID intentionally unset
    out = links_for("anything", launch_key="b", species="c")
    assert out == []


def test_amazon_url_has_tag_and_subtag(monkeypatch):
    _set_all(monkeypatch)
    out = links_for("hot pink flasher", launch_key="brewster", species="chinook")
    amzn = next(l for l in out if l.vendor == "amzn")
    parsed = urllib.parse.urlparse(amzn.url)
    qs = urllib.parse.parse_qs(parsed.query)
    assert parsed.netloc == "www.amazon.com"
    assert parsed.path == "/s"
    assert qs["k"] == ["hot pink flasher"]
    assert qs["tag"] == ["pnwbite-20"]
    assert qs["ascsubtag"] == ["brewster__chinook"]


def test_spwh_url_wraps_sportsmans_target(monkeypatch):
    _set_all(monkeypatch)
    out = links_for("hot pink flasher", launch_key="brewster", species="chinook")
    spwh = next(l for l in out if l.vendor == "spwh")
    parsed = urllib.parse.urlparse(spwh.url)
    qs = urllib.parse.parse_qs(parsed.query)
    assert parsed.netloc == "www.avantlink.com"
    assert parsed.path == "/click.php"
    assert qs["tt"] == ["cl"]
    assert qs["merchant_id"] == ["mid-456"]
    assert qs["affiliate_id"] == ["aff-123"]
    assert qs["pat"] == ["brewster__chinook"]
    # The wrapped target URL must point at Sportsman's Warehouse search.
    target = qs["url"][0]
    target_parsed = urllib.parse.urlparse(target)
    target_qs = urllib.parse.parse_qs(target_parsed.query)
    assert target_parsed.netloc == "www.sportsmans.com"
    assert target_parsed.path == "/search"
    assert target_qs["query"] == ["hot pink flasher"]


def test_query_with_special_chars_is_safely_encoded(monkeypatch):
    _set_all(monkeypatch)
    # Apostrophe, ampersand, double-quote — all common in tackle names.
    query = 'Brad\'s "Super Bait" & roe wrap'
    out = links_for(query, launch_key="b", species="chinook")
    for link in out:
        parsed = urllib.parse.urlparse(link.url)
        qs = urllib.parse.parse_qs(parsed.query)
        # Round-trip: parsing the encoded URL should yield the original query.
        if link.vendor == "amzn":
            assert qs["k"] == [query]
        else:
            target_qs = urllib.parse.parse_qs(urllib.parse.urlparse(qs["url"][0]).query)
            assert target_qs["query"] == [query]


def test_link_label_and_title_are_present(monkeypatch):
    _set_all(monkeypatch)
    out = links_for("anything", launch_key="b", species="c")
    by_v = {l.vendor: l for l in out}
    assert by_v["amzn"].label == "amzn"
    assert by_v["spwh"].label == "spwh"
    assert "Amazon" in by_v["amzn"].title
    assert "affiliate" in by_v["amzn"].title.lower()
    assert "Sportsman" in by_v["spwh"].title
    assert "affiliate" in by_v["spwh"].title.lower()


def test_whitespace_only_env_vars_are_treated_as_unset(monkeypatch):
    """Whitespace-only env var must not produce a malformed affiliate URL."""
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "   ")
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "\t")
    monkeypatch.setenv("AVANTLINK_SPWH_MERCHANT_ID", "  ")
    assert links_for("anything", launch_key="x", species="y") == []


def test_empty_query_returns_no_links(monkeypatch):
    """Empty or whitespace-only query produces no links, not a vendor-homepage stub."""
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "aff-123")
    monkeypatch.setenv("AVANTLINK_SPWH_MERCHANT_ID", "mid-456")
    assert links_for("", launch_key="b", species="c") == []
    assert links_for("   ", launch_key="b", species="c") == []


def test_avantlink_requires_both_vars_merchant_id_alone(monkeypatch):
    """Symmetric to test_avantlink_requires_both_vars: only AVANTLINK_SPWH_MERCHANT_ID set."""
    _clear_all(monkeypatch)
    monkeypatch.setenv("AVANTLINK_SPWH_MERCHANT_ID", "mid-456")
    # AVANTLINK_AFFILIATE_ID intentionally unset
    out = links_for("anything", launch_key="b", species="c")
    assert out == []


def test_has_any_affiliate_returns_true_for_amazon(monkeypatch):
    _clear_all(monkeypatch)
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    from engines.affiliate import has_any_affiliate
    assert has_any_affiliate() is True


def test_has_any_affiliate_returns_true_for_avantlink_pair(monkeypatch):
    _clear_all(monkeypatch)
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "aff-123")
    monkeypatch.setenv("AVANTLINK_SPWH_MERCHANT_ID", "mid-456")
    from engines.affiliate import has_any_affiliate
    assert has_any_affiliate() is True


def test_has_any_affiliate_returns_false_for_partial_avantlink(monkeypatch):
    """Only one of the AvantLink pair is set → no link can render → predicate False."""
    _clear_all(monkeypatch)
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "aff-123")
    # AVANTLINK_SPWH_MERCHANT_ID intentionally unset
    from engines.affiliate import has_any_affiliate
    assert has_any_affiliate() is False


def test_has_any_affiliate_returns_false_for_whitespace_only(monkeypatch):
    _clear_all(monkeypatch)
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "   ")
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "\t")
    monkeypatch.setenv("AVANTLINK_SPWH_MERCHANT_ID", "  ")
    from engines.affiliate import has_any_affiliate
    assert has_any_affiliate() is False


def test_has_any_affiliate_returns_false_for_no_credentials(monkeypatch):
    _clear_all(monkeypatch)
    from engines.affiliate import has_any_affiliate
    assert has_any_affiliate() is False
