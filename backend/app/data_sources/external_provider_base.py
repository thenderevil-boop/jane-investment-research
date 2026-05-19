from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from backend.app.schemas.common import DataSourceStatus

ExternalProviderSourceType = Literal["live", "cached_live", "fallback", "unknown"]


@dataclass(frozen=True)
class ExternalProviderConfig:
    provider: str
    enabled: bool = False
    requires_api_key: bool = False
    api_key: str = ""
    base_url: str | None = None
    cache_ttl_days: int = 7

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key.strip())

    def safe_public_dict(self) -> dict[str, object]:
        """Return config metadata that is safe for logs/API diagnostics."""
        return {
            "provider": self.provider,
            "enabled": self.enabled,
            "requires_api_key": self.requires_api_key,
            "has_api_key": self.has_api_key,
            "base_url": self.base_url.rstrip("/") if self.base_url else None,
            "cache_ttl_days": self.cache_ttl_days,
        }


@dataclass(frozen=True)
class ExternalProviderStatus:
    provider: str
    source_type: ExternalProviderSourceType = "unknown"
    source_date: str = ""
    fetched_at: datetime | str | None = None
    cache_hit: bool = False
    rate_limited: bool = False
    fallback_used: bool = False
    fallback_reason: str | None = None
    limitations: list[str] | None = None
    missing_data: list[str] | None = None

    def _fetched_at_string(self) -> str | None:
        if isinstance(self.fetched_at, datetime):
            return self.fetched_at.isoformat()
        return self.fetched_at

    def to_data_source_status(self, freshness_window: str = "external_provider_cache") -> DataSourceStatus:
        limitations = list(self.limitations or [])
        if self.rate_limited:
            limitations.append("Provider was rate limited.")
        if self.cache_hit:
            limitations.append("Cache hit from external provider adapter.")
        return DataSourceStatus(
            source_type=self.source_type,
            provider=self.provider,
            source_date=self.source_date,
            fetched_at=self._fetched_at_string(),
            is_fresh=self.source_type == "live" and not self.fallback_used and not self.rate_limited,
            freshness_window=freshness_window,
            fallback_used=self.fallback_used,
            fallback_reason=self.fallback_reason,
            limitations=limitations,
            missing_data=list(self.missing_data or []),
        )
