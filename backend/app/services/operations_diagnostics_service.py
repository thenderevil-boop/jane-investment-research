from __future__ import annotations

from datetime import datetime, timezone
import os

from backend.app import config
from backend.app.schemas.operations_diagnostics import (
    CoverageReadinessRow,
    ManagerUniverseDiagnostics,
    OperationsDiagnosticsResponse,
    ProviderDiagnosticRow,
    RuntimeDiagnostics,
    SourceHealthAction,
)
from backend.app.services.operations_settings_service import get_13f_manager_universe_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _has_env(name: str, placeholders: set[str] | None = None) -> bool:
    value = os.getenv(name, "").strip()
    if not value:
        return False
    return value.lower() not in (placeholders or set())


def _source_type(enabled: bool, has_required_key: bool = True) -> str:
    if not enabled:
        return "disabled"
    if not has_required_key:
        return "mock"
    return "live"


def _status(enabled: bool, has_required_key: bool = True) -> str:
    if not enabled:
        return "disabled"
    if not has_required_key:
        return "missing_key"
    return "available"


def _provider(
    provider_id: str,
    label: str,
    *,
    enabled: bool,
    requires_api_key: bool = False,
    has_api_key: bool = False,
    cache_ttl_days: float | None = None,
    cache_ttl_hours: float | None = None,
    limitations: list[str] | None = None,
    missing_data: list[str] | None = None,
    next_action: str,
    source_type: str | None = None,
) -> ProviderDiagnosticRow:
    has_required_key = (not requires_api_key) or has_api_key
    return ProviderDiagnosticRow(
        provider_id=provider_id,
        label=label,
        enabled=enabled,
        requires_api_key=requires_api_key,
        has_api_key=has_api_key,
        source_type=source_type or _source_type(enabled, has_required_key),
        status=_status(enabled, has_required_key),
        cache_ttl_days=cache_ttl_days,
        cache_ttl_hours=cache_ttl_hours,
        limitations=limitations or [],
        missing_data=missing_data or ([] if has_required_key else ["api_key"]),
        next_action=next_action,
    )


def _manager_universe() -> ManagerUniverseDiagnostics:
    settings = get_13f_manager_universe_settings()
    return ManagerUniverseDiagnostics(
        source=settings.source,
        manager_count=len(settings.effective_manager_ciks),
        is_runtime_override=settings.source in {"local_settings", "startup_env"},
        bundled_starter_count=settings.bundled_starter_count,
        editable=settings.editable,
        warnings=settings.warnings,
    )


def _provider_rows() -> list[ProviderDiagnosticRow]:
    fred_key = _has_env("FRED_API_KEY", config.FRED_API_KEY_PLACEHOLDERS)
    fmp_key = _has_env("FMP_API_KEY")
    alpha_key = _has_env("ALPHA_VANTAGE_API_KEY")
    sec_user_agent = _has_env("SEC_EDGAR_USER_AGENT")
    return [
        _provider(
            "sec_13f",
            "SEC 13F institutional holdings",
            enabled=config.USE_LIVE_SEC_13F,
            cache_ttl_days=config.SEC_13F_CACHE_TTL_DAYS,
            limitations=["13F filings are delayed and may not reflect current holdings."],
            next_action="Use candidate-specific target matches for C19 readiness; review delayed filing limitations.",
        ),
        _provider(
            "sec_form4",
            "SEC Form 4 insider transactions",
            enabled=config.USE_LIVE_SEC_FORM4,
            cache_ttl_hours=config.SEC_FORM4_CACHE_TTL_HOURS,
            missing_data=[] if sec_user_agent or not config.USE_LIVE_SEC_FORM4 else ["sec_edgar_user_agent"],
            next_action="Configure SEC EDGAR user agent when live Form 4 context is required.",
            source_type=_source_type(config.USE_LIVE_SEC_FORM4, sec_user_agent),
        ),
        _provider(
            "uspto_patentsview",
            "USPTO PatentsView patent count",
            enabled=config.USE_LIVE_USPTO_PATENTS_DATA,
            cache_ttl_days=config.USPTO_PATENTS_CACHE_TTL_DAYS,
            limitations=["Patent count is a proxy and still needs patent-quality and assignee review."],
            next_action="Use provider-backed patent counts as C18 readiness context when available.",
        ),
        _provider(
            "fred_macro",
            "FRED macro data",
            enabled=config.USE_LIVE_MACRO_DATA,
            requires_api_key=True,
            has_api_key=fred_key,
            cache_ttl_days=None,
            next_action="Configure FRED key for live macro context; otherwise Daily Report can remain snapshot/mock-backed.",
        ),
        _provider(
            "yfinance_market",
            "yfinance market/company data",
            enabled=config.USE_LIVE_MARKET_DATA or config.USE_LIVE_COMPANY_DATA,
            source_type="live" if (config.USE_LIVE_MARKET_DATA or config.USE_LIVE_COMPANY_DATA) else "mock",
            next_action="Enable live yfinance market/company data when current prices, market context, or company proxies are needed.",
        ),
        _provider(
            "fmp_financial_proxy",
            "FMP financial statement proxy",
            enabled=config.USE_LIVE_FMP_DATA,
            requires_api_key=True,
            has_api_key=fmp_key,
            cache_ttl_days=config.FMP_CACHE_TTL_DAYS,
            next_action="Use FMP financial proxy for ADR or SEC-gap financial statement context when key is configured.",
        ),
        _provider(
            "fmp_transcript",
            "FMP transcript evidence",
            enabled=config.USE_LIVE_FMP_DATA,
            requires_api_key=True,
            has_api_key=fmp_key,
            cache_ttl_days=config.FMP_CACHE_TTL_DAYS,
            next_action="Use transcript evidence for C2/C17 manual-review context when key is configured.",
        ),
        _provider(
            "usaspending",
            "USASpending.gov awards",
            enabled=config.USE_LIVE_USASPENDING_DATA,
            cache_ttl_days=config.USASPENDING_CACHE_TTL_DAYS,
            next_action="Enable when C15 government relationship context is required.",
        ),
        _provider(
            "openbb_sidecar",
            "OpenBB sidecar / Stockgrid options",
            enabled=config.USE_OPENBB_SIDECAR,
            cache_ttl_days=config.OPENBB_CACHE_TTL_DAYS,
            limitations=["Sidecar diagnostics are read-only and do not test sidecar reachability."],
            next_action="Start sidecar and enable setting only when options-flow context is in scope.",
        ),
        _provider(
            "sec_companyfacts",
            "SEC Companyfacts financial facts",
            enabled=config.USE_LIVE_SEC_COMPANYFACTS,
            cache_ttl_days=config.SEC_COMPANYFACTS_CACHE_TTL_DAYS,
            missing_data=[] if sec_user_agent or not config.USE_LIVE_SEC_COMPANYFACTS else ["sec_edgar_user_agent"],
            next_action="Configure SEC EDGAR user agent for filing-backed companyfacts fetches.",
            source_type=_source_type(config.USE_LIVE_SEC_COMPANYFACTS, sec_user_agent),
        ),
        _provider(
            "daily_report_snapshot",
            "Daily Report snapshot/raw-store",
            enabled=True,
            source_type="derived",
            next_action="Use snapshot freshness metadata to decide whether Daily Report should refresh or stay snapshot-first.",
        ),
        _provider(
            "alpha_vantage",
            "Alpha Vantage adapter foundation",
            enabled=config.USE_LIVE_ALPHA_VANTAGE,
            requires_api_key=True,
            has_api_key=alpha_key,
            cache_ttl_days=config.ALPHA_VANTAGE_CACHE_TTL_DAYS,
            next_action="Adapter foundation only; do not rely on it for current scoring unless a future phase activates it.",
        ),
    ]


def _readiness(enabled: bool, has_required_key: bool = True) -> str:
    if not enabled:
        return "disabled"
    if not has_required_key:
        return "missing_key"
    return "ready"


def _coverage_rows() -> list[CoverageReadinessRow]:
    fmp_key = _has_env("FMP_API_KEY")
    return [
        CoverageReadinessRow(
            criterion_id=18,
            criterion_name="Patents / IP",
            provider_id="uspto_patentsview",
            readiness=_readiness(config.USE_LIVE_USPTO_PATENTS_DATA),
            covered_submetrics=["patent_count"],
            next_action="Review patent count, assignee match, and patent quality before treating C18 as supported.",
        ),
        CoverageReadinessRow(
            criterion_id=19,
            criterion_name="VC / Institutional Support",
            provider_id="sec_13f",
            readiness=_readiness(config.USE_LIVE_SEC_13F),
            covered_submetrics=["institutional_support", "fund_support"],
            next_action="Use candidate-specific SEC 13F target matches as delayed institutional context, not real-time flow.",
        ),
        CoverageReadinessRow(
            criterion_id=15,
            criterion_name="Government Relationship",
            provider_id="usaspending",
            readiness=_readiness(config.USE_LIVE_USASPENDING_DATA),
            covered_submetrics=["government_contracts", "defense_or_infrastructure_status"],
            next_action="Review recipient/entity matches and award descriptions manually.",
        ),
        CoverageReadinessRow(
            criterion_id=5,
            criterion_name="Financial Quality",
            provider_id="sec_companyfacts",
            readiness=_readiness(config.USE_LIVE_SEC_COMPANYFACTS, _has_env("SEC_EDGAR_USER_AGENT")),
            covered_submetrics=["revenue_growth", "margin_trend", "rd_intensity"],
            next_action="Use filing-backed financial facts where mapped concepts exist; keep qualitative moat evidence separate.",
        ),
        CoverageReadinessRow(
            criterion_id=2,
            criterion_name="Visionary Founder / CEO",
            provider_id="fmp_transcript",
            readiness=_readiness(config.USE_LIVE_FMP_DATA, fmp_key),
            covered_submetrics=["management_language", "founder_ceo_context"],
            next_action="Treat transcript evidence as management-language context requiring manual review.",
        ),
        CoverageReadinessRow(
            criterion_id=3,
            criterion_name="Contrarian / Skepticism Context",
            provider_id="yfinance_market",
            readiness=_readiness(config.USE_LIVE_MARKET_DATA or config.USE_LIVE_COMPANY_DATA),
            covered_submetrics=["short_interest_proxy"],
            next_action="Use yfinance short-interest proxy as partial evidence only when current data is available.",
        ),
        CoverageReadinessRow(
            criterion_id=11,
            criterion_name="Theme Alignment",
            provider_id="user_theme_context",
            readiness="partial",
            covered_submetrics=["user_theme_context"],
            next_action="User-supplied themes are validation targets and require separate evidence for revenue exposure or industry growth.",
        ),
    ]


def _source_health_actions(providers: list[ProviderDiagnosticRow], coverage_rows: list[CoverageReadinessRow]) -> list[SourceHealthAction]:
    readiness_by_provider: dict[str, set[int]] = {}
    for row in coverage_rows:
        readiness_by_provider.setdefault(row.provider_id, set()).add(row.criterion_id)

    configured_criteria: dict[str, list[int]] = {
        "fmp_financial_proxy": [5, 6, 10],
        "fmp_transcript": [2, 17],
        "fred_macro": [],
        "sec_form4": [2, 3],
        "sec_companyfacts": [5],
        "uspto_patentsview": [18],
        "sec_13f": [19],
        "usaspending": [15],
        "openbb_sidecar": [3],
        "alpha_vantage": [],
    }
    surfaces_by_provider: dict[str, list[str]] = {
        "fred_macro": ["operations", "daily_report"],
        "fmp_financial_proxy": ["operations", "stock_research", "daily_report"],
        "fmp_transcript": ["operations", "stock_research", "evidence_library"],
        "sec_form4": ["operations", "daily_report", "stock_research"],
        "sec_companyfacts": ["operations", "stock_research", "daily_report"],
        "uspto_patentsview": ["operations", "stock_research", "daily_report"],
        "sec_13f": ["operations", "stock_research", "daily_report"],
        "usaspending": ["operations", "stock_research"],
        "openbb_sidecar": ["operations", "stock_research"],
        "alpha_vantage": ["operations"],
    }
    titles = {
        "fmp_financial_proxy": "Configure FMP financial proxy key",
        "fmp_transcript": "Configure FMP transcript key",
        "fred_macro": "Configure FRED macro key",
        "sec_form4": "Configure SEC EDGAR user agent for Form 4",
        "sec_companyfacts": "Configure SEC EDGAR user agent for Companyfacts",
        "uspto_patentsview": "Enable USPTO PatentsView context",
        "sec_13f": "Enable SEC 13F target-manager context",
    }
    action_ids = {
        ("fmp_financial_proxy", "missing_key"): "missing_fmp_key",
        ("fmp_transcript", "missing_key"): "missing_fmp_key",
        ("fred_macro", "missing_key"): "missing_fred_key",
        ("sec_form4", "source_setup_required"): "missing_sec_user_agent",
        ("sec_companyfacts", "source_setup_required"): "missing_sec_user_agent",
        ("uspto_patentsview", "provider_disabled"): "disabled_uspto",
        ("sec_13f", "provider_disabled"): "disabled_sec_13f",
    }
    actions: list[SourceHealthAction] = []
    seen: set[str] = set()
    for provider in providers:
        category = None
        if provider.status == "missing_key":
            category = "missing_key"
        elif "sec_edgar_user_agent" in provider.missing_data:
            category = "source_setup_required"
        elif provider.status == "disabled" and provider.provider_id in {"uspto_patentsview", "sec_13f", "usaspending", "openbb_sidecar", "alpha_vantage"}:
            category = "provider_disabled"
        elif provider.status == "stale":
            category = "cache_refresh_required"
        if not category:
            continue
        action_id = action_ids.get((provider.provider_id, category), f"{category}_{provider.provider_id}")
        if action_id in seen:
            continue
        seen.add(action_id)
        affected_criteria = sorted(set(configured_criteria.get(provider.provider_id, [])) | readiness_by_provider.get(provider.provider_id, set()))
        severity = "high" if category in {"missing_key", "source_setup_required"} else "medium"
        actions.append(
            SourceHealthAction(
                action_id=action_id,
                provider_id=provider.provider_id,
                severity=severity,
                category=category,  # type: ignore[arg-type]
                title=titles.get(provider.provider_id, f"Review {provider.label} setup"),
                recommended_action=provider.next_action,
                affected_criteria=affected_criteria,
                affected_surfaces=surfaces_by_provider.get(provider.provider_id, ["operations"]),  # type: ignore[arg-type]
            )
        )
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda action: (severity_rank[action.severity], action.provider_id, action.action_id))
    return actions[:10]


def build_operations_diagnostics() -> OperationsDiagnosticsResponse:
    providers = _provider_rows()
    coverage_rows = _coverage_rows()
    return OperationsDiagnosticsResponse(
        generated_at=_now_iso(),
        runtime=RuntimeDiagnostics(
            daily_report_read_mode=config.DAILY_REPORT_READ_MODE,
            daily_batch_allow_live_fetch=config.DAILY_BATCH_ALLOW_LIVE_FETCH,
        ),
        providers=providers,
        coverage_readiness=coverage_rows,
        manager_universe=_manager_universe(),
        source_health_actions=_source_health_actions(providers, coverage_rows),
    )
