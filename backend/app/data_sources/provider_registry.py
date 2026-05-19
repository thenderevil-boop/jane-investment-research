from __future__ import annotations

from backend.app import config
from backend.app.data_sources.external_provider_base import ExternalProviderConfig


class ExternalProviderNotEnabledError(RuntimeError):
    """Raised when a future external provider adapter is requested while disabled."""


def _provider_configs() -> dict[str, ExternalProviderConfig]:
    return {
        "fmp": ExternalProviderConfig(
            provider="fmp",
            enabled=config.USE_LIVE_FMP_DATA,
            requires_api_key=True,
            api_key=config.FMP_API_KEY,
            cache_ttl_days=config.FMP_CACHE_TTL_DAYS,
        ),
        "openbb": ExternalProviderConfig(
            provider="openbb",
            enabled=config.USE_OPENBB_SIDECAR,
            requires_api_key=False,
            base_url=config.OPENBB_BASE_URL,
            cache_ttl_days=config.OPENBB_CACHE_TTL_DAYS,
        ),
        "alpha_vantage": ExternalProviderConfig(
            provider="alpha_vantage",
            enabled=config.USE_LIVE_ALPHA_VANTAGE,
            requires_api_key=True,
            api_key=config.ALPHA_VANTAGE_API_KEY,
            cache_ttl_days=config.ALPHA_VANTAGE_CACHE_TTL_DAYS,
        ),
        "usaspending": ExternalProviderConfig(
            provider="usaspending",
            enabled=config.USE_LIVE_USASPENDING_DATA,
            requires_api_key=False,
            cache_ttl_days=config.USASPENDING_CACHE_TTL_DAYS,
        ),
    }


def get_provider_config(provider: str) -> ExternalProviderConfig:
    provider_key = provider.strip().lower()
    configs = _provider_configs()
    if provider_key not in configs:
        raise KeyError(f"Unknown external provider: {provider}")
    return configs[provider_key]


def require_provider_enabled(provider: str) -> ExternalProviderConfig:
    provider_config = get_provider_config(provider)
    if not provider_config.enabled:
        raise ExternalProviderNotEnabledError(f"External provider '{provider_config.provider}' is disabled.")
    if provider_config.requires_api_key and not provider_config.has_api_key:
        raise ExternalProviderNotEnabledError(f"External provider '{provider_config.provider}' requires an API key.")
    return provider_config


def provider_registry_snapshot() -> dict[str, object]:
    providers = [provider.safe_public_dict() for provider in _provider_configs().values()]
    return {
        "phase": "Phase 37 — External Provider Adapter Foundation",
        "providers": providers,
        "enabled_provider_count": sum(1 for provider in providers if provider["enabled"]),
        "fetching_enabled_by_this_phase": False,
    }
