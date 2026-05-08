"""cloudflare.purge_cache hits the Cloudflare API; gracefully no-ops without env vars."""
import requests_mock
import pytest

from cloudflare import purge_cache, MissingCloudflareConfig


def test_purge_cache_no_config_silent_noop(monkeypatch):
    """Without env vars, purge_cache returns False and does NOT raise."""
    monkeypatch.delenv("CLOUDFLARE_PURGE_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ZONE_ID", raising=False)
    assert purge_cache() is False


def test_purge_cache_raises_when_strict_and_no_config(monkeypatch):
    """Strict mode raises MissingCloudflareConfig instead of silently no-op."""
    monkeypatch.delenv("CLOUDFLARE_PURGE_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ZONE_ID", raising=False)
    with pytest.raises(MissingCloudflareConfig):
        purge_cache(strict=True)


def test_purge_cache_calls_api(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_PURGE_TOKEN", "test-token")
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "test-zone-123")
    with requests_mock.Mocker() as m:
        m.post(
            "https://api.cloudflare.com/client/v4/zones/test-zone-123/purge_cache",
            json={"success": True, "result": {"id": "abc"}},
            status_code=200,
        )
        result = purge_cache()
        assert result is True
        # Verify the Authorization header was sent
        history = m.request_history
        assert history[0].headers["Authorization"] == "Bearer test-token"
        # Verify body is purge_everything
        assert history[0].json() == {"purge_everything": True}


def test_purge_cache_swallows_api_errors(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_PURGE_TOKEN", "test-token")
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "test-zone-123")
    with requests_mock.Mocker() as m:
        m.post(
            "https://api.cloudflare.com/client/v4/zones/test-zone-123/purge_cache",
            status_code=500,
        )
        # Should not raise
        result = purge_cache()
        assert result is False
