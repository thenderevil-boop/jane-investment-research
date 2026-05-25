from __future__ import annotations

import importlib
from datetime import datetime, timezone

import pytest


def reload_provider_modules(monkeypatch: pytest.MonkeyPatch, **env: str):
    keys = [
        "USE_LIVE_FMP_DATA",
        "FMP_API_KEY",
        "FMP_CACHE_TTL_DAYS",
        "USE_OPENBB_SIDECAR",
        "OPENBB_BASE_URL",
        "OPENBB_CACHE_TTL_DAYS",
        "USE_LIVE_ALPHA_VANTAGE",
        "ALPHA_VANTAGE_API_KEY",
        "ALPHA_VANTAGE_CACHE_TTL_DAYS",
        "USE_LIVE_USASPENDING_DATA",
        "USASPENDING_CACHE_TTL_DAYS",
        "USE_LIVE_USPTO_PATENTS_DATA",
        "USPTO_PATENTS_CACHE_TTL_DAYS",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    import backend.app.config as config
    import backend.app.data_sources.external_provider_base as base
    import backend.app.data_sources.provider_registry as registry

    importlib.reload(config)
    importlib.reload(base)
    importlib.reload(registry)
    return config, base, registry


def test_phase37_provider_registry_defaults_keep_keyed_external_providers_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, registry = reload_provider_modules(monkeypatch)

    snapshot = registry.provider_registry_snapshot()
    provider_names = [provider["provider"] for provider in snapshot["providers"]]
    provider_by_name = {provider["provider"]: provider for provider in snapshot["providers"]}

    assert provider_names == ["fmp", "openbb", "alpha_vantage", "usaspending", "uspto_patentsview"]
    assert snapshot["enabled_provider_count"] == 1
    assert provider_by_name["uspto_patentsview"]["enabled"] is True
    assert provider_by_name["uspto_patentsview"]["requires_api_key"] is False
    assert all(
        provider["enabled"] is False
        for provider in snapshot["providers"]
        if provider["provider"] != "uspto_patentsview"
    )
    assert all("api_key" not in provider for provider in snapshot["providers"])

    with pytest.raises(registry.ExternalProviderNotEnabledError):
        registry.require_provider_enabled("fmp")

    assert registry.require_provider_enabled("uspto_patentsview").enabled is True


def test_phase37_env_driven_provider_config_and_status_conversion(monkeypatch: pytest.MonkeyPatch) -> None:
    _, base, registry = reload_provider_modules(
        monkeypatch,
        USE_LIVE_FMP_DATA="true",
        FMP_API_KEY="dummy_fmp_key_for_test",
        FMP_CACHE_TTL_DAYS="3",
        USE_OPENBB_SIDECAR="true",
        OPENBB_BASE_URL="http://127.0.0.1:6900/",
        OPENBB_CACHE_TTL_DAYS="2",
        USE_LIVE_USASPENDING_DATA="true",
        USASPENDING_CACHE_TTL_DAYS="14",
        USE_LIVE_USPTO_PATENTS_DATA="true",
        USPTO_PATENTS_CACHE_TTL_DAYS="30",
    )

    fmp = registry.require_provider_enabled("fmp")
    openbb = registry.require_provider_enabled("openbb")
    usaspending = registry.require_provider_enabled("usaspending")
    uspto = registry.require_provider_enabled("uspto_patentsview")

    assert fmp.provider == "fmp"
    assert fmp.enabled is True
    assert fmp.cache_ttl_days == 3
    assert fmp.has_api_key is True
    assert fmp.safe_public_dict() == {
        "provider": "fmp",
        "enabled": True,
        "requires_api_key": True,
        "has_api_key": True,
        "base_url": None,
        "cache_ttl_days": 3,
    }
    assert openbb.base_url == "http://127.0.0.1:6900"
    assert openbb.has_api_key is False
    assert usaspending.requires_api_key is False
    assert uspto.requires_api_key is False
    assert uspto.cache_ttl_days == 30

    fetched_at = datetime(2026, 5, 19, 9, 0, tzinfo=timezone.utc)
    status = base.ExternalProviderStatus(
        provider="fmp",
        source_type="live",
        source_date="2026-05-18",
        fetched_at=fetched_at,
        cache_hit=False,
        rate_limited=False,
        fallback_used=False,
        limitations=["Transcript endpoint is research evidence only."],
        missing_data=[],
    )

    data_source_status = status.to_data_source_status(freshness_window="3d")
    assert data_source_status.provider == "fmp"
    assert data_source_status.source_type == "live"
    assert data_source_status.source_date == "2026-05-18"
    assert data_source_status.fetched_at == "2026-05-19T09:00:00+00:00"
    assert data_source_status.is_fresh is True
    assert data_source_status.freshness_window == "3d"
    assert data_source_status.limitations == ["Transcript endpoint is research evidence only."]


def test_phase37_provider_status_handles_fallback_rate_limit_and_cached_source(monkeypatch: pytest.MonkeyPatch) -> None:
    _, base, _ = reload_provider_modules(monkeypatch)

    cached = base.ExternalProviderStatus(
        provider="openbb",
        source_type="cached_live",
        source_date="2026-05-18",
        cache_hit=True,
        rate_limited=True,
        fallback_used=True,
        fallback_reason="OpenBB sidecar returned HTTP 429.",
        limitations=["Using cached sidecar payload."],
        missing_data=["options_block_premium"],
    )

    data_source_status = cached.to_data_source_status(freshness_window="2d")
    assert data_source_status.source_type == "cached_live"
    assert data_source_status.provider == "openbb"
    assert data_source_status.is_fresh is False
    assert data_source_status.fallback_used is True
    assert data_source_status.fallback_reason == "OpenBB sidecar returned HTTP 429."
    assert "Provider was rate limited." in data_source_status.limitations
    assert "Cache hit from external provider adapter." in data_source_status.limitations
    assert data_source_status.missing_data == ["options_block_premium"]


def test_phase37_unknown_provider_name_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, registry = reload_provider_modules(monkeypatch)

    with pytest.raises(KeyError):
        registry.get_provider_config("polygon")
