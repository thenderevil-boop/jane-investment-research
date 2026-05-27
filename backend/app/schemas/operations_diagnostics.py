from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ProviderSourceType = Literal["live", "cached_live", "derived", "fallback", "mock", "disabled", "unknown"]
ProviderStatus = Literal["available", "disabled", "missing_key", "stale", "unavailable", "not_configured"]
Readiness = Literal["ready", "partial", "disabled", "missing_key", "stale", "unavailable"]
ManagerUniverseSource = Literal["startup_env", "local_settings", "bundled_starter_universe"]


class RuntimeDiagnostics(BaseModel):
    daily_report_read_mode: str
    daily_batch_allow_live_fetch: bool
    read_only: bool = True
    triggers_provider_calls: bool = False
    not_investment_advice: bool = True


class ProviderDiagnosticRow(BaseModel):
    provider_id: str
    label: str
    enabled: bool
    requires_api_key: bool = False
    has_api_key: bool = False
    source_type: ProviderSourceType = "unknown"
    status: ProviderStatus = "unavailable"
    cache_ttl_days: float | None = None
    cache_ttl_hours: float | None = None
    last_snapshot_at: str | None = None
    limitations: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    next_action: str


class CoverageReadinessRow(BaseModel):
    criterion_id: int
    criterion_name: str
    provider_id: str
    readiness: Readiness
    covered_submetrics: list[str] = Field(default_factory=list)
    next_action: str
    not_investment_advice: bool = True


class ManagerUniverseDiagnostics(BaseModel):
    source: ManagerUniverseSource
    manager_count: int
    is_runtime_override: bool
    bundled_starter_count: int
    editable: bool = True
    warnings: list[str] = Field(default_factory=list)


class SecretsPolicyDiagnostics(BaseModel):
    api_key_values_returned: bool = False
    redaction_policy: str = "only safe booleans are exposed; API key values are never returned"


class OperationsDiagnosticsResponse(BaseModel):
    version: Literal["phase62_operations_diagnostics_v1"] = "phase62_operations_diagnostics_v1"
    generated_at: str
    runtime: RuntimeDiagnostics
    providers: list[ProviderDiagnosticRow]
    coverage_readiness: list[CoverageReadinessRow]
    manager_universe: ManagerUniverseDiagnostics
    secrets_policy: SecretsPolicyDiagnostics = Field(default_factory=SecretsPolicyDiagnostics)
    not_investment_advice: bool = True
