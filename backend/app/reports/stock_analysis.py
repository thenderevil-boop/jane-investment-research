from __future__ import annotations

from backend.app.data_sources.mock_data import DEFAULT_STOCK, MOCK_SOURCE_DATE, STOCK_FIXTURES
from backend.app.engines.leadership_engine import evaluate_leadership
from backend.app.engines.macro_regime_engine import evaluate_macro_regime
from backend.app.engines.market_timing_engine import evaluate_market_timing
from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.engines.sec_13f_target_matching import build_candidate_13f_evidence
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.pipelines.research_pipeline import _build_jane_reference_conditions, _enrich_source_status, score_object
from backend.app.raw_store.repository import get_company_fundamentals, get_company_profile, get_sec_companyfacts, read_macro_data, read_market_data, read_sec_filings
from backend.app.schemas.common import ScoreObject
from backend.app.schemas.stock_analysis import (
    AnalyzeStockDataQualitySummary,
    AnalyzeStockRequest,
    AnalyzeStockResponse,
    CandidateValidationSummary,
    EvidenceMatrixItem,
    FinancialStatementSignals,
    JaneCompanyQuality,
    NextManualCheck,
    ResearchVerdict,
    ScoreDriverBreakdown,
)
from backend.app.utils.freshness import build_source_status, summarize_data_quality

MOCK_LEADERSHIP_CONFIDENCE_CAP = 0.72
MOCK_EVIDENCE_LIMITATION = "Mock evidence limits analyze-stock confidence; treat mock-based components as preliminary validation only."


def _research_verdict(
    *,
    company_quality_score: float,
    company_quality_confidence: float,
    key_qualitative_insufficient: bool,
    smart_money_score: float,
    macro_score: float,
    overheat_score: float,
    missing_data_count: int,
    confidence_inputs: list[float],
    mock_evidence_present: bool = False,
    fallback_evidence_present: bool = False,
    live_macro_present: bool = False,
) -> ResearchVerdict:
    raw_score = company_quality_score * 0.45 + smart_money_score * 0.25 + macro_score * 0.20 + max(0, 100 - overheat_score) * 0.10
    missing_penalty = min(25, missing_data_count * 3)
    score = round(max(0, min(100, raw_score - missing_penalty)), 2)
    confidence = max(0.15, min(1, (sum([*confidence_inputs, company_quality_confidence]) / (len(confidence_inputs) + 1)) - min(0.35, missing_data_count * 0.03)))
    if mock_evidence_present:
        confidence = min(confidence, MOCK_LEADERSHIP_CONFIDENCE_CAP)
    if fallback_evidence_present:
        confidence = min(confidence, 0.75)
    if key_qualitative_insufficient:
        confidence = min(confidence, 0.80)
    confidence = round(confidence, 2)
    if missing_data_count >= 7 or confidence < 0.35:
        label = "insufficient_data"
        summary = "Research reference only. Evidence is incomplete, so this ticker needs human verification before deeper research priority is raised."
    elif overheat_score >= 75:
        label = "high_risk_context"
        summary = "Research reference only. The ticker has elevated risk context, so deeper review should focus on evidence quality and downside scenarios."
    elif score >= 70 and macro_score >= 50:
        label = "worth_deep_research"
        summary = "Research reference only. The ticker is worth deeper research under Jane methodology, with current environment context included."
    elif score >= 45:
        label = "watchlist_candidate"
        summary = "Research reference only. The ticker merits watchlist-level validation while missing or weaker evidence is checked."
    else:
        label = "insufficient_data"
        summary = "Research reference only. Current structured evidence is not strong enough to raise research priority."
    if mock_evidence_present:
        summary = f"{summary} Mock evidence limits confidence."
    boosters = []
    limiters = []
    if live_macro_present:
        boosters.append("Macro environment uses live or derived-live source context.")
    if macro_score >= 56:
        boosters.append("Macro score is neutral-to-constructive under macro_v12_5.")
    if smart_money_score >= 50:
        boosters.append("Aggregate smart-money evidence is at least neutral in the current framework.")
    if company_quality_score >= 60 and company_quality_confidence >= 0.45:
        boosters.append("Jane company quality has partial evidence from financial metrics.")
    if mock_evidence_present:
        limiters.append("Legacy leadership or company-related evidence is mock-based.")
    if key_qualitative_insufficient:
        limiters.append("Key qualitative Jane company quality criteria remain insufficient.")
    if fallback_evidence_present:
        limiters.append("One or more smart-money or filing components use fallback or cached-after-failure evidence.")
    if missing_data_count:
        limiters.append(f"{missing_data_count} missing-data items require human verification.")
    return ResearchVerdict(
        label=label,
        score=score,
        confidence=confidence,
        summary=summary,
        confidence_factors={
            "confidence_boosters": boosters,
            "confidence_limiters": limiters,
        },
    )


def _status_dict(value) -> dict:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {}


def _sanitize_api_secret_markers(value):
    if isinstance(value, str):
        return value.replace("SEC_EDGAR_USER_AGENT", "SEC EDGAR User-Agent")
    if isinstance(value, list):
        return [_sanitize_api_secret_markers(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_api_secret_markers(child) for key, child in value.items()}
    return value


def _source_quality_from_status(status: dict, *, category: str = "") -> str:
    source_type = status.get("source_type")
    provider = str(status.get("provider") or "")
    fallback_used = bool(status.get("fallback_used")) or source_type == "fallback"
    if category == "macro_environment" and source_type == "derived" and provider.startswith("mixed_FRED"):
        return "derived_live"
    if fallback_used:
        return "mixed_with_fallback"
    if category in {"sec_financial_facts"} and source_type in {"live", "cached_live"}:
        return "filing_backed"
    if category == "fundamentals_cross_check":
        return "derived_from_mixed_sources"
    if "SEC_companyfacts" in provider or "SEC companyfacts" in provider:
        return "derived_from_mixed_sources" if source_type == "derived" else "filing_backed"
    if source_type == "mock":
        return "mock_only"
    if source_type == "cached_live":
        return "cached_live"
    if source_type == "live":
        return "live_backed"
    if source_type == "derived":
        if provider == "mixed_smart_money_sources":
            return "mixed_with_fallback" if fallback_used else "derived_live"
        if "mock" in provider.lower():
            return "mixed_with_fallback"
        return "derived_live"
    if category == "risk_flags":
        return "derived_live"
    return "insufficient"


def _sec_available(sec_facts: dict) -> bool:
    return _status_dict(sec_facts.get("source_status")).get("source_type") in {"live", "cached_live"} and any(sec_facts.get("facts", {}).values())


def _sec_metric(sec_facts: dict, metric: str):
    return (sec_facts.get("derived_metrics") or {}).get(metric)


def _sec_fact_value(sec_facts: dict, fact_name: str):
    fact = (sec_facts.get("facts") or {}).get(fact_name)
    return fact.get("value") if isinstance(fact, dict) else None


def _sec_source_quality(sec_facts: dict, fallback: str) -> str:
    if _sec_available(sec_facts):
        return "filing_backed"
    return fallback


def _build_fundamentals_cross_check(sec_facts: dict, yfinance_fundamentals: dict) -> dict:
    sec_status = _status_dict(sec_facts.get("source_status"))
    yf_status = _status_dict(yfinance_fundamentals.get("source_status"))
    limitations = [
        "SEC Companyfacts complements yfinance and does not replace provider-normalized MVP fundamentals.",
        "Provider normalization differences are expected; discrepancies are review signals.",
    ]
    invalid = sec_facts.get("invalid_derived_metrics") or {}
    metrics = [
        ("revenue_ttm", yfinance_fundamentals.get("revenue_ttm"), _sec_fact_value(sec_facts, "revenue"), "revenue"),
        ("gross_margin_pct", yfinance_fundamentals.get("gross_margin_pct"), _sec_metric(sec_facts, "gross_margin_pct"), "gross_margin_pct"),
        ("operating_margin_pct", yfinance_fundamentals.get("operating_margin_pct"), _sec_metric(sec_facts, "operating_margin_pct"), "operating_margin_pct"),
        ("free_cash_flow_ttm", yfinance_fundamentals.get("free_cash_flow_ttm"), _sec_metric(sec_facts, "fcf"), "fcf"),
        ("cash_and_equivalents", yfinance_fundamentals.get("cash_and_equivalents"), _sec_fact_value(sec_facts, "cash_and_equivalents"), "cash_and_equivalents"),
        ("total_debt", yfinance_fundamentals.get("total_debt"), _sec_fact_value(sec_facts, "total_debt"), "total_debt"),
        ("shares_outstanding", yfinance_fundamentals.get("shares_outstanding"), _sec_fact_value(sec_facts, "shares_outstanding"), "shares_outstanding"),
    ]
    checked = []
    for name, yf_value, sec_value, sec_metric_name in metrics:
        difference = None
        if sec_metric_name in invalid:
            status = "sec_invalid_period_alignment"
        elif _metric_available(yf_value) and _metric_available(sec_value) and yf_value != 0:
            difference = round(abs(float(sec_value) - float(yf_value)) / abs(float(yf_value)) * 100, 4)
            status = "consistent" if difference <= 5 else "moderate_difference" if difference <= 15 else "divergent"
        elif not _metric_available(sec_value) and not _metric_available(yf_value):
            status = "insufficient"
        elif not _metric_available(sec_value):
            status = "sec_missing"
        else:
            status = "yfinance_missing"
        checked.append(
            {
                "name": name,
                "yfinance_value": yf_value if _metric_available(yf_value) else None,
                "sec_value": sec_value if _metric_available(sec_value) else None,
                "difference_pct": difference,
                "status": status,
                "source_quality": "filing_backed" if status in {"consistent", "moderate_difference", "divergent"} else "provider_backed" if status in {"sec_missing", "sec_invalid_period_alignment"} and _metric_available(yf_value) else "insufficient",
            }
        )
    comparable = [item for item in checked if item["status"] in {"consistent", "moderate_difference", "divergent"}]
    divergent = [item for item in comparable if item["status"] == "divergent"]
    consistent = [item for item in comparable if item["status"] == "consistent"]
    consistent_names = {item["name"] for item in consistent}
    divergent_names = {item["name"] for item in divergent}
    parser_period_alignment_valid = not bool(invalid)
    provider_normalization_discrepancies = bool(divergent) and parser_period_alignment_valid
    revenue_and_margin_consistent = {"revenue_ttm", "gross_margin_pct"}.issubset(consistent_names)
    divergent_category = "none"
    if invalid:
        divergent_category = "invalid_sec_period_alignment"
    elif divergent_names & {"free_cash_flow_ttm"}:
        divergent_category = "cash_flow_provider_normalization"
    elif divergent_names & {"cash_and_equivalents", "total_debt"}:
        divergent_category = "balance_sheet_provider_normalization"
    elif divergent:
        divergent_category = "provider_normalization_or_classification"
    if not comparable:
        agreement = "insufficient"
        summary = "SEC/yfinance cross-check has insufficient comparable filing-backed metrics."
    elif divergent:
        agreement = "low"
        if revenue_and_margin_consistent:
            summary = "SEC and yfinance agree on revenue and gross margin; some balance-sheet or cash-flow fields differ due to provider normalization or statement classification differences."
        else:
            summary = "SEC/yfinance cross-check found material comparable metric differences that need provider-normalization review."
    elif len(consistent) >= max(1, len(comparable) - 1):
        agreement = "high"
        summary = "SEC/yfinance cross-check is directionally consistent for comparable metrics."
    else:
        agreement = "moderate"
        summary = "SEC/yfinance cross-check is partly consistent with some provider-period differences."
    if sec_status.get("source_type") in {"live", "cached_live"} and yf_status.get("source_type") in {"live", "cached_live", "derived"}:
        limitations.append("SEC latest FY values may be compared with yfinance TTM/provider-normalized values; period mismatch can create differences.")
    if invalid:
        limitations.append("SEC Companyfacts is available, but some derived metrics require period-alignment review.")
    source_status = build_source_status(
        {
            "source_type": "derived",
            "provider": "mixed_SEC_companyfacts_and_yfinance",
            "source_date": max([item for item in [sec_status.get("source_date"), yf_status.get("source_date")] if item], default=""),
            "fallback_used": bool(sec_status.get("fallback_used") or yf_status.get("fallback_used")),
            "fallback_reason": sec_status.get("fallback_reason") or yf_status.get("fallback_reason"),
            "limitations": limitations,
            "missing_data": sorted(set([*sec_facts.get("missing_data", []), *yfinance_fundamentals.get("missing_data", [])])),
        }
    ).model_dump(mode="json")
    return {
        "provider": "mixed_SEC_companyfacts_and_yfinance",
        "source_type": "derived",
        "summary": summary,
        "agreement_level": agreement,
        "divergence_reason": divergent_category,
        "parser_period_alignment_valid": parser_period_alignment_valid,
        "provider_normalization_discrepancies": provider_normalization_discrepancies,
        "checked_metrics": checked,
        "confidence_adjustment": {
            "boost_applied": agreement in {"high", "moderate"} and bool(comparable),
            "penalty_applied": agreement == "low",
            "reason": summary,
        },
        "source_status": source_status,
        "limitations": limitations,
        "missing_data": source_status["missing_data"],
    }


def _score_status(score: float | None) -> str:
    if score is None:
        return "insufficient"
    if score >= 65:
        return "supportive"
    if score >= 45:
        return "neutral"
    return "caution"


def _metric_available(value) -> bool:
    return isinstance(value, (int, float)) and value is not None


def _safe_ratio(numerator: float | None, denominator: float | None, missing_data: list[str], missing_label: str) -> float | None:
    if numerator is None or denominator is None:
        missing_data.append(missing_label)
        return None
    if denominator <= 0:
        missing_data.append(f"{missing_label}: denominator missing or non-positive")
        return None
    return round(numerator / denominator, 4)


def _financial_quality_score(financials: dict) -> tuple[float, str, float]:
    status = _status_dict(financials.get("source_status"))
    live_like = status.get("source_type") in {"live", "cached_live", "derived"}
    required = [
        financials.get("revenue_yoy_growth_pct"),
        financials.get("gross_margin_pct"),
        financials.get("free_cash_flow_ttm"),
        financials.get("cash_and_equivalents"),
        financials.get("total_debt"),
    ]
    available = sum(1 for item in required if _metric_available(item))
    if not live_like or available < 3:
        return 50, "neutral", 0.45 if not live_like else 0.58
    score = 50
    if (financials.get("revenue_yoy_growth_pct") or 0) >= 10:
        score += 12
    if (financials.get("gross_margin_pct") or 0) >= 40:
        score += 10
    if (financials.get("free_cash_flow_ttm") or 0) > 0:
        score += 10
    if (financials.get("net_cash_or_debt") or 0) >= 0:
        score += 8
    if (financials.get("debt_to_equity") or 0) and (financials.get("debt_to_equity") or 0) > 150:
        score -= 8
    score = round(max(0, min(100, score)), 2)
    label = "favorable_research_environment" if score >= 70 else "neutral"
    confidence = round(min(0.78, 0.52 + available * 0.05), 2)
    return score, label, confidence


def _build_financial_quality_score(financials: dict) -> ScoreObject:
    status = _status_dict(financials.get("source_status"))
    score, label, confidence = _financial_quality_score(financials)
    return ScoreObject(
        name="financial_quality_score",
        score=score,
        label=label,
        raw_data=financials,
        derived_metrics={
            "revenue_yoy_growth_pct": financials.get("revenue_yoy_growth_pct"),
            "revenue_3y_cagr_pct": financials.get("revenue_3y_cagr_pct"),
            "gross_margin_pct": financials.get("gross_margin_pct"),
            "free_cash_flow_margin_pct": financials.get("free_cash_flow_margin_pct"),
            "net_cash_or_debt": financials.get("net_cash_or_debt"),
            "available_core_metric_count": sum(
                1
                for item in [
                    financials.get("revenue_yoy_growth_pct"),
                    financials.get("gross_margin_pct"),
                    financials.get("free_cash_flow_ttm"),
                    financials.get("cash_and_equivalents"),
                    financials.get("total_debt"),
                ]
                if _metric_available(item)
            ),
        },
        benchmark={
            "revenue_growth_supportive_pct": 10,
            "gross_margin_supportive_pct": 40,
            "positive_free_cash_flow_required_for_quality_driver": True,
            "net_cash_supportive": True,
        },
        trend={
            "financial_quality": "available" if status.get("source_type") in {"live", "cached_live", "derived"} else "preliminary",
        },
        source=[status.get("provider") or financials.get("provider") or "unknown"],
        source_date=status.get("source_date") or financials.get("source_date") or "",
        confidence=confidence,
        limitations=financials.get("limitations", []),
        missing_data=financials.get("missing_data", []),
        source_status=build_source_status(financials).model_copy(update=status) if status else build_source_status(financials),
    )


def _build_valuation_context(profile: dict, financials: dict) -> ScoreObject:
    missing_data: list[str] = []
    market_cap = profile.get("market_cap")
    enterprise_value = profile.get("enterprise_value")
    revenue_ttm = financials.get("revenue_ttm")
    free_cash_flow_ttm = financials.get("free_cash_flow_ttm")
    price_to_sales = _safe_ratio(market_cap, revenue_ttm, missing_data, "market_cap or revenue_ttm unavailable for price_to_sales_ttm")
    ev_to_sales = _safe_ratio(enterprise_value, revenue_ttm, missing_data, "enterprise_value or revenue_ttm unavailable for ev_to_sales_ttm")
    price_to_fcf = _safe_ratio(market_cap, free_cash_flow_ttm, missing_data, "market_cap or free_cash_flow_ttm unavailable for price_to_free_cash_flow_ttm")
    ev_to_fcf = _safe_ratio(enterprise_value, free_cash_flow_ttm, missing_data, "enterprise_value or free_cash_flow_ttm unavailable for ev_to_free_cash_flow_ttm")
    multiples = [value for value in [price_to_sales, ev_to_sales, price_to_fcf, ev_to_fcf] if value is not None]
    if not multiples:
        label = "insufficient"
        score = 50
        summary = "Valuation context is insufficient because live market value and fundamental denominators are incomplete."
    elif (price_to_sales is not None and price_to_sales >= 15) or (ev_to_sales is not None and ev_to_sales >= 18) or (price_to_fcf is not None and price_to_fcf >= 60):
        label = "elevated"
        score = 35
        summary = "Valuation context is elevated as a research risk flag based on available live or cached inputs."
    elif (price_to_sales is not None and price_to_sales >= 8) or (ev_to_sales is not None and ev_to_sales >= 10):
        label = "moderate"
        score = 55
        summary = "Valuation context is moderate based on available live or cached inputs."
    else:
        label = "low"
        score = 70
        summary = "Valuation context is not elevated based on available live or cached inputs."
    profile_status = _status_dict(profile.get("source_status"))
    fundamentals_status = _status_dict(financials.get("source_status"))
    source_types = {profile_status.get("source_type"), fundamentals_status.get("source_type")}
    if source_types <= {"live", "cached_live"}:
        source_type = "derived"
        provider = "derived_from_yfinance"
    elif any(item in {"live", "cached_live", "derived"} for item in source_types):
        source_type = "derived"
        provider = "derived_from_yfinance"
    else:
        source_type = "mock"
        provider = "mock"
    source_date = max([item for item in [profile_status.get("source_date"), fundamentals_status.get("source_date")] if item], default="")
    limitations = sorted(set([*profile.get("limitations", []), *financials.get("limitations", []), "Valuation context is risk context only and is not an investment instruction."]))
    missing = sorted(set([*missing_data, *profile.get("missing_data", []), *financials.get("missing_data", [])]))
    source_status = build_source_status(
        {
            "source_type": source_type,
            "provider": provider,
            "source_date": source_date,
            "limitations": limitations,
            "missing_data": missing,
            "fallback_used": bool(profile_status.get("fallback_used") or fundamentals_status.get("fallback_used")),
            "fallback_reason": profile_status.get("fallback_reason") or fundamentals_status.get("fallback_reason"),
        }
    )
    return ScoreObject(
        name="valuation_context_score",
        score=score,
        label=label,
        raw_data={
            "ticker": profile.get("ticker") or financials.get("ticker"),
            "market_cap": market_cap,
            "enterprise_value": enterprise_value,
            "price_to_sales_ttm": price_to_sales,
            "ev_to_sales_ttm": ev_to_sales,
            "price_to_free_cash_flow_ttm": price_to_fcf,
            "ev_to_free_cash_flow_ttm": ev_to_fcf,
            "gross_margin_pct": financials.get("gross_margin_pct"),
            "revenue_growth_yoy_pct": financials.get("revenue_yoy_growth_pct"),
            "valuation_risk_label": label,
            "valuation_summary": summary,
            "source_status": source_status.model_dump(mode="json"),
            "limitations": limitations,
            "missing_data": missing,
        },
        derived_metrics={
            "valuation_risk_label": label,
            "available_multiple_count": len(multiples),
            "valuation_summary": summary,
        },
        benchmark={
            "price_to_sales_elevated": 15,
            "ev_to_sales_elevated": 18,
            "price_to_free_cash_flow_elevated": 60,
        },
        trend={"valuation_pressure": "elevated" if label == "elevated" else "not_elevated" if label in {"low", "moderate"} else "insufficient"},
        source=[provider],
        source_date=source_date,
        confidence=0.68 if multiples else 0.42,
        limitations=limitations,
        missing_data=missing,
        source_status=source_status,
    )


JANE_QUALITY_PRINCIPLES = [
    "Market Monopoly / Moat",
    "Mega Trend Fit",
    "Visionary Founder / CEO",
    "Disruptive Innovation",
    "Scalability",
    "Network Effect",
    "Continuous R&D",
]


def _metric_evidence(label: str, value) -> str:
    return f"{label}: {value if value is not None else 'unavailable'}"


def _quality_source(financial_status: dict) -> str:
    provider = str(financial_status.get("provider") or "")
    if "SEC_companyfacts" in provider or "sec_companyfacts" in provider:
        return "derived_from_mixed_sources"
    if "SEC" in provider:
        return "filing_backed"
    source_type = financial_status.get("source_type")
    if source_type == "live":
        return "derived_live"
    if source_type == "cached_live":
        return "cached_live"
    if source_type == "derived":
        return "derived_live"
    if source_type == "mock":
        return "mock_only"
    return "insufficient"


def _merge_financials_with_sec(yfinance_fundamentals: dict, sec_facts: dict, cross_check: dict) -> dict:
    merged = dict(yfinance_fundamentals)
    if not _sec_available(sec_facts):
        merged["sec_source_basis"] = "insufficient"
        return merged
    mapping = {
        "revenue_yoy_growth_pct": ("derived_metrics", "revenue_yoy_growth_pct"),
        "revenue_3y_cagr_pct": ("derived_metrics", "revenue_3y_cagr_pct"),
        "gross_margin_pct": ("derived_metrics", "gross_margin_pct"),
        "operating_margin_pct": ("derived_metrics", "operating_margin_pct"),
        "net_income_margin_pct": ("derived_metrics", "net_income_margin_pct"),
        "operating_cash_flow_ttm": ("facts", "operating_cash_flow"),
        "capex_ttm": ("facts", "capex"),
        "free_cash_flow_ttm": ("derived_metrics", "fcf"),
        "free_cash_flow_margin_pct": ("derived_metrics", "fcf_margin_pct"),
        "cash_and_equivalents": ("facts", "cash_and_equivalents"),
        "total_debt": ("facts", "total_debt"),
        "net_cash_or_debt": ("derived_metrics", "net_cash_or_debt"),
        "debt_to_equity": ("derived_metrics", "debt_to_equity"),
        "accounts_receivable": ("facts", "accounts_receivable"),
        "receivables_to_revenue_pct": ("derived_metrics", "receivables_to_revenue_pct"),
        "inventory": ("facts", "inventory"),
        "inventory_to_revenue_pct": ("derived_metrics", "inventory_to_revenue_pct"),
        "shares_outstanding": ("facts", "shares_outstanding"),
        "share_dilution_3y_pct": ("derived_metrics", "share_dilution_3y_pct"),
    }
    filing_backed_fields = []
    for target, (section, key) in mapping.items():
        value = (sec_facts.get(section) or {}).get(key)
        if section == "facts" and isinstance(value, dict):
            value = value.get("value")
        if _metric_available(value):
            merged[target] = value
            filing_backed_fields.append(target)
    sec_status = _status_dict(sec_facts.get("source_status"))
    yf_status = _status_dict(yfinance_fundamentals.get("source_status"))
    limitations = sorted(set([
        *yfinance_fundamentals.get("limitations", []),
        *sec_facts.get("limitations", []),
        *cross_check.get("limitations", []),
    ]))
    missing = sorted(set([*yfinance_fundamentals.get("missing_data", []), *sec_facts.get("missing_data", [])]))
    source_status = build_source_status(
        {
            "source_type": "derived",
            "provider": "derived_from_SEC_companyfacts_and_yfinance",
            "source_date": max([item for item in [sec_status.get("source_date"), yf_status.get("source_date")] if item], default=""),
            "limitations": limitations,
            "missing_data": missing,
            "fallback_used": bool(sec_status.get("fallback_used") or yf_status.get("fallback_used")),
            "fallback_reason": sec_status.get("fallback_reason") or yf_status.get("fallback_reason"),
        }
    ).model_dump(mode="json")
    merged.update(
        {
            "source_type": "derived",
            "provider": "derived_from_SEC_companyfacts_and_yfinance",
            "source": ["SEC EDGAR companyfacts", "yfinance"],
            "source_date": source_status.get("source_date", ""),
            "source_status": source_status,
            "sec_source_basis": "derived_from_mixed_sources",
            "filing_backed_fields": filing_backed_fields,
            "fundamentals_cross_check_agreement": cross_check.get("agreement_level"),
            "limitations": limitations,
            "missing_data": missing,
        }
    )
    return merged


def _criterion(
    name: str,
    display_name: str,
    *,
    score: float | None,
    status: str,
    source_quality: str,
    affects_score: bool,
    evidence: list[str] | None = None,
    limitations: list[str] | None = None,
    missing_data: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "display_name": display_name,
        "score": None if score is None else round(max(0, min(100, score)), 2),
        "max_score": 10,
        "status": status,
        "source_quality": source_quality,
        "affects_score": affects_score,
        "evidence": evidence or [],
        "limitations": limitations or [],
        "missing_data": missing_data or [],
    }


def _financial_metric_status(score: float | None) -> str:
    if score is None:
        return "insufficient"
    if score >= 70:
        return "supportive"
    if score >= 45:
        return "neutral"
    return "caution"


def _build_jane_company_quality(financial_quality: ScoreObject, research_context: dict) -> JaneCompanyQuality:
    financials = financial_quality.raw_data
    financial_status = _status_dict(financial_quality.source_status)
    source_quality = _quality_source(financial_status)
    yfinance_limitations = list(financial_quality.limitations or [])
    financial_source_usable = source_quality in {"derived_live", "cached_live", "filing_backed", "derived_from_mixed_sources"}
    if financial_source_usable:
        yfinance_limitations = sorted(set([*yfinance_limitations, "Yfinance fundamentals may combine company-reported values with provider-normalized fields."]))

    revenue_growth = financials.get("revenue_yoy_growth_pct")
    revenue_cagr = financials.get("revenue_3y_cagr_pct")
    gross_margin = financials.get("gross_margin_pct")
    operating_margin = financials.get("operating_margin_pct")
    fcf_margin = financials.get("free_cash_flow_margin_pct")
    fcf = financials.get("free_cash_flow_ttm")
    net_cash = financials.get("net_cash_or_debt")
    debt_to_equity = financials.get("debt_to_equity")
    cash = financials.get("cash_and_equivalents")
    debt = financials.get("total_debt")
    rd_to_revenue = financials.get("rd_to_revenue_pct")
    rd_expense = financials.get("rd_expense_ttm")

    scalability_available = sum(_metric_available(item) for item in [revenue_growth, revenue_cagr, gross_margin, operating_margin, fcf_margin])
    scalability_score = None
    if financial_source_usable and scalability_available >= 3:
        scalability_score = 45
        if (revenue_growth or 0) >= 15 or (revenue_cagr or 0) >= 15:
            scalability_score += 20
        if (gross_margin or 0) >= 45:
            scalability_score += 12
        if (operating_margin or 0) >= 20:
            scalability_score += 12
        if (fcf_margin or 0) >= 10:
            scalability_score += 11
        if (revenue_growth or 0) > 10 and (operating_margin or 0) < 5:
            scalability_score -= 20
    financial_statement_score = None
    if financial_source_usable and sum(_metric_available(item) for item in [revenue_growth, revenue_cagr, gross_margin, operating_margin, fcf]) >= 3:
        financial_statement_score = 45
        if (revenue_growth or 0) > 10 or (revenue_cagr or 0) > 10:
            financial_statement_score += 20
        if (gross_margin or 0) >= 40:
            financial_statement_score += 10
        if (operating_margin or 0) >= 15:
            financial_statement_score += 10
        if (fcf or 0) > 0:
            financial_statement_score += 15
    balance_sheet_score = None
    if financial_source_usable and sum(_metric_available(item) for item in [cash, debt, net_cash, debt_to_equity]) >= 2:
        balance_sheet_score = 50
        if (net_cash or 0) >= 0:
            balance_sheet_score += 25
        if debt_to_equity is not None and debt_to_equity <= 80:
            balance_sheet_score += 15
        if debt_to_equity is not None and debt_to_equity > 150:
            balance_sheet_score -= 20
    cash_flow_score = None
    cash_flow_missing = []
    if financials.get("operating_cash_flow_ttm") is None:
        cash_flow_missing.append("operating cash flow detail")
    if financials.get("capex_ttm") is None:
        cash_flow_missing.append("capex detail")
    if financial_source_usable and _metric_available(fcf):
        cash_flow_score = 50
        if (fcf or 0) > 0:
            cash_flow_score += 25
        if (fcf_margin or 0) >= 10:
            cash_flow_score += 15
        if not cash_flow_missing:
            cash_flow_score += 10

    rd_score = None
    rd_status = "insufficient"
    rd_source_quality = "insufficient"
    if financial_source_usable and (_metric_available(rd_expense) or _metric_available(rd_to_revenue)):
        rd_source_quality = source_quality
        rd_score = 55
        if (rd_to_revenue or 0) >= 8:
            rd_score += 25
        elif (rd_to_revenue or 0) >= 3:
            rd_score += 10
        rd_status = _financial_metric_status(rd_score)

    theme = str(research_context.get("theme") or "").strip()
    criteria = [
        _criterion(
            "monopoly_power",
            "Market Monopoly / Moat",
            score=None,
            status="insufficient",
            source_quality="insufficient",
            affects_score=False,
            evidence=([f"User context theme: {theme}"] if "moat" in theme.lower() else []),
            missing_data=["market share evidence", "patent or moat evidence"],
        ),
        _criterion(
            "mega_trend_fit",
            "Mega Trend Fit",
            score=None,
            status="neutral" if theme else "insufficient",
            source_quality="user_context" if theme else "insufficient",
            affects_score=False,
            evidence=([f"User-provided theme context: {theme}"] if theme else []),
            limitations=["User-provided theme is research context and is not independently verified evidence."],
            missing_data=[] if theme else ["independently verified trend evidence"],
        ),
        _criterion(
            "visionary_founder_ceo",
            "Visionary Founder / CEO",
            score=None,
            status="insufficient",
            source_quality="insufficient",
            affects_score=False,
            missing_data=["CEO/founder live evidence", "management tenure evidence"],
        ),
        _criterion(
            "disruptive_innovation",
            "Disruptive Innovation",
            score=None,
            status="insufficient",
            source_quality="insufficient",
            affects_score=False,
            missing_data=["product disruption evidence", "patent evidence", "technology differentiation evidence"],
        ),
        _criterion(
            "scalability",
            "Scalability",
            score=scalability_score,
            status=_financial_metric_status(scalability_score),
            source_quality=source_quality if scalability_score is not None else "insufficient",
            affects_score=scalability_score is not None,
            evidence=[
                _metric_evidence("Revenue YoY growth pct", revenue_growth),
                _metric_evidence("Revenue 3Y CAGR pct", revenue_cagr),
                _metric_evidence("Gross margin pct", gross_margin),
                _metric_evidence("Operating margin pct", operating_margin),
                _metric_evidence("Free cash flow margin pct", fcf_margin),
            ],
            limitations=yfinance_limitations,
            missing_data=[] if scalability_score is not None else ["revenue growth, margin, and free cash flow margin metrics"],
        ),
        _criterion(
            "network_effect",
            "Network Effect",
            score=None,
            status="insufficient",
            source_quality="insufficient",
            affects_score=False,
            missing_data=["network effect evidence", "ecosystem usage evidence"],
        ),
        _criterion(
            "continuous_r_and_d",
            "Continuous R&D",
            score=rd_score,
            status=rd_status,
            source_quality=rd_source_quality,
            affects_score=rd_score is not None,
            evidence=[_metric_evidence("R&D expense TTM", rd_expense), _metric_evidence("R&D as pct of revenue", rd_to_revenue)] if rd_score is not None else [],
            limitations=yfinance_limitations if rd_score is not None else [],
            missing_data=[] if rd_score is not None else ["R&D expense", "R&D as percentage of revenue"],
        ),
        _criterion(
            "financial_statement_quality",
            "Financial Statement Quality",
            score=financial_statement_score,
            status=_financial_metric_status(financial_statement_score),
            source_quality=source_quality if financial_statement_score is not None else "insufficient",
            affects_score=financial_statement_score is not None,
            evidence=[
                _metric_evidence("Revenue YoY growth pct", revenue_growth),
                _metric_evidence("Revenue 3Y CAGR pct", revenue_cagr),
                _metric_evidence("Gross margin pct", gross_margin),
                _metric_evidence("Operating margin pct", operating_margin),
                _metric_evidence("Free cash flow TTM", fcf),
            ],
            limitations=yfinance_limitations,
            missing_data=[] if financial_statement_score is not None else ["revenue growth, margin, and free cash flow metrics"],
        ),
        _criterion(
            "balance_sheet_strength",
            "Balance Sheet Strength",
            score=balance_sheet_score,
            status=_financial_metric_status(balance_sheet_score),
            source_quality=source_quality if balance_sheet_score is not None else "insufficient",
            affects_score=balance_sheet_score is not None,
            evidence=[
                _metric_evidence("Cash and equivalents", cash),
                _metric_evidence("Total debt", debt),
                _metric_evidence("Net cash or debt", net_cash),
                _metric_evidence("Debt to equity", debt_to_equity),
            ],
            limitations=yfinance_limitations,
            missing_data=[] if balance_sheet_score is not None else ["cash and debt metrics"],
        ),
        _criterion(
            "cash_flow_quality",
            "Cash Flow Quality",
            score=cash_flow_score,
            status=_financial_metric_status(cash_flow_score),
            source_quality=source_quality if cash_flow_score is not None else "insufficient",
            affects_score=cash_flow_score is not None,
            evidence=[
                _metric_evidence("Free cash flow TTM", fcf),
                _metric_evidence("Free cash flow margin pct", fcf_margin),
                _metric_evidence("Operating cash flow TTM", financials.get("operating_cash_flow_ttm")),
                _metric_evidence("CapEx TTM", financials.get("capex_ttm")),
            ],
            limitations=sorted(set([*yfinance_limitations, "Cash-flow quality is conservative when OCF and CapEx detail is unavailable."])),
            missing_data=cash_flow_missing,
        ),
    ]
    affecting = [item for item in criteria if item["affects_score"] and item["score"] is not None]
    score = round(sum(float(item["score"]) for item in affecting) / len(criteria), 2) if affecting else 0
    evidence_count = sum(1 for item in criteria if item["source_quality"] in {"derived_live", "live_backed", "cached_live", "filing_backed", "derived_from_mixed_sources"} and item["affects_score"])
    insufficient_count = sum(1 for item in criteria if item["status"] == "insufficient")
    confidence = round(min(0.78, 0.25 + evidence_count * 0.08), 2)
    label = "evidence_backed" if evidence_count >= 7 and confidence >= 0.70 else "preliminary" if evidence_count else "insufficient_data"
    missing = sorted({missing for item in criteria for missing in item["missing_data"]})
    source_status = build_source_status(
        {
            "source_type": "derived" if evidence_count else "unknown",
            "provider": "derived_from_SEC_companyfacts_and_yfinance_company_quality" if source_quality == "derived_from_mixed_sources" else "derived_from_yfinance_company_quality" if evidence_count else "insufficient_company_quality_evidence",
            "source_date": financial_status.get("source_date", ""),
            "is_fresh": financial_status.get("is_fresh", False),
            "limitations": ["Qualitative principles require evidence and are marked insufficient when not verifiable.", *yfinance_limitations],
            "missing_data": missing,
            "fallback_used": financial_status.get("fallback_used", False),
            "fallback_reason": financial_status.get("fallback_reason"),
        }
    )
    return JaneCompanyQuality(
        score=score,
        confidence=confidence,
        label=label,
        criteria=criteria,
        source_status=source_status,
        limitations=source_status.limitations,
        missing_data=missing,
    )


def _signal(name: str, status: str, source_quality: str, evidence: list[str], limitations: list[str], missing_data: list[str]) -> dict:
    return {
        "name": name,
        "status": status,
        "source_quality": source_quality,
        "evidence": evidence,
        "limitations": limitations,
        "missing_data": missing_data,
    }


def _build_financial_statement_signals(financial_quality: ScoreObject) -> FinancialStatementSignals:
    financials = financial_quality.raw_data
    status = _status_dict(financial_quality.source_status)
    live_like = status.get("source_type") in {"live", "cached_live", "derived"}
    filing_fields = set(financials.get("filing_backed_fields") or [])
    default_source_quality = "derived_from_mixed_sources" if filing_fields else "derived_live" if live_like else "insufficient"
    limitations = list(financial_quality.limitations or [])

    def signal_source_quality(relevant_fields: set[str], *, mixed: bool = False) -> str:
        if relevant_fields & filing_fields:
            return "derived_from_mixed_sources" if mixed else "filing_backed"
        if filing_fields and live_like:
            return "yfinance_backed"
        return default_source_quality

    def available_metric(name: str):
        return financials.get(name) if _metric_available(financials.get(name)) else None

    signals = []
    revenue_growth = available_metric("revenue_yoy_growth_pct")
    revenue_cagr = available_metric("revenue_3y_cagr_pct")
    if live_like and (revenue_growth is not None or revenue_cagr is not None):
        status_name = "supportive" if (revenue_growth or 0) >= 10 or (revenue_cagr or 0) >= 10 else "neutral"
        signal_quality = signal_source_quality({"revenue_yoy_growth_pct", "revenue_3y_cagr_pct"})
        signals.append(_signal("revenue_growth_quality", status_name, signal_quality, [_metric_evidence("Revenue YoY growth pct", revenue_growth), _metric_evidence("Revenue 3Y CAGR pct", revenue_cagr)], limitations, []))
    else:
        signals.append(_signal("revenue_growth_quality", "insufficient", "insufficient", [], limitations, ["revenue_yoy_growth_pct", "revenue_3y_cagr_pct"]))

    operating_margin = available_metric("operating_margin_pct")
    if live_like and operating_margin is not None:
        signal_quality = signal_source_quality({"operating_margin_pct"})
        signals.append(_signal("operating_margin_strength", "supportive" if operating_margin >= 15 else "neutral" if operating_margin >= 5 else "caution", signal_quality, [_metric_evidence("Operating margin pct", operating_margin)], limitations, []))
    else:
        signals.append(_signal("operating_margin_strength", "insufficient", "insufficient", [], limitations, ["operating_margin_pct"]))

    net_income = available_metric("net_income_ttm")
    net_income_margin = available_metric("net_income_margin_pct")
    if live_like and (net_income is not None or net_income_margin is not None):
        ocf = available_metric("operating_cash_flow_ttm")
        if net_income is not None and ocf is not None and net_income > 0 and ocf < net_income * 0.8:
            ni_status = "caution"
        else:
            ni_status = "supportive" if (net_income or 0) > 0 and (net_income_margin or 0) >= 10 else "neutral" if (net_income or 0) > 0 else "caution"
        signal_quality = signal_source_quality({"net_income_margin_pct", "operating_cash_flow_ttm"}, mixed=True)
        signals.append(_signal("net_income_quality", ni_status, signal_quality, [_metric_evidence("Net income TTM", net_income), _metric_evidence("Net income margin pct", net_income_margin), _metric_evidence("Operating cash flow TTM", ocf)], limitations, []))
    else:
        signals.append(_signal("net_income_quality", "insufficient", "insufficient", [], limitations, ["net_income_ttm", "net_income_margin_pct"]))

    ocf = available_metric("operating_cash_flow_ttm")
    if live_like and ocf is not None:
        signal_quality = signal_source_quality({"operating_cash_flow_ttm"})
        signals.append(_signal("operating_cash_flow_quality", "supportive" if ocf > 0 else "caution", signal_quality, [_metric_evidence("Operating cash flow TTM", ocf)], limitations, []))
    else:
        signals.append(_signal("operating_cash_flow_quality", "insufficient", "insufficient", [], limitations, ["operating_cash_flow_ttm"]))

    cash = available_metric("cash_and_equivalents")
    debt = available_metric("total_debt")
    net_cash = available_metric("net_cash_or_debt")
    if live_like and (cash is not None or net_cash is not None):
        signal_quality = signal_source_quality({"cash_and_equivalents", "net_cash_or_debt"})
        signals.append(_signal("cash_safety_buffer", "supportive" if (net_cash or 0) >= 0 else "neutral", signal_quality, [_metric_evidence("Cash and equivalents", cash), _metric_evidence("Net cash or debt", net_cash)], limitations, []))
    else:
        signals.append(_signal("cash_safety_buffer", "insufficient", "insufficient", [], limitations, ["cash_and_equivalents", "net_cash_or_debt"]))

    debt_to_equity = available_metric("debt_to_equity")
    if live_like and (debt is not None or debt_to_equity is not None):
        signal_quality = signal_source_quality({"total_debt", "debt_to_equity"})
        signals.append(_signal("debt_risk", "supportive" if (net_cash or 0) >= 0 or (debt_to_equity is not None and debt_to_equity <= 0.8) else "caution" if debt_to_equity and debt_to_equity > 1.5 else "neutral", signal_quality, [_metric_evidence("Total debt", debt), _metric_evidence("Debt to equity", debt_to_equity)], limitations, []))
    else:
        signals.append(_signal("debt_risk", "insufficient", "insufficient", [], limitations, ["total_debt", "debt_to_equity"]))

    for signal_name, ratio_field, raw_field, missing in [
        ("receivables_vs_revenue_risk", "receivables_to_revenue_pct", "accounts_receivable", ["accounts_receivable", "receivables_to_revenue_pct"]),
        ("inventory_vs_revenue_risk", "inventory_to_revenue_pct", "inventory", ["inventory", "inventory_to_revenue_pct"]),
    ]:
        ratio = available_metric(ratio_field)
        raw = available_metric(raw_field)
        if live_like and ratio is not None:
            signal_quality = signal_source_quality({ratio_field, raw_field})
            signals.append(_signal(signal_name, "caution" if ratio >= 30 else "neutral", signal_quality, [_metric_evidence(raw_field.replace("_", " ").title(), raw), _metric_evidence(ratio_field, ratio)], limitations, []))
        else:
            signals.append(_signal(signal_name, "insufficient", "insufficient", [], limitations, missing))

    capex = available_metric("capex_ttm")
    if live_like and ocf is not None and capex is not None:
        capex_ratio = round(abs(capex) / ocf * 100, 2) if ocf > 0 else None
        signal_quality = signal_source_quality({"operating_cash_flow_ttm", "capex_ttm"})
        signals.append(_signal("capex_vs_ocf_risk", "caution" if capex_ratio is not None and capex_ratio >= 80 else "neutral", signal_quality, [_metric_evidence("Operating cash flow TTM", ocf), _metric_evidence("CapEx TTM", capex), _metric_evidence("CapEx as pct of OCF", capex_ratio)], limitations, []))
    else:
        signals.append(_signal("capex_vs_ocf_risk", "insufficient", "insufficient", [], limitations, ["operating_cash_flow_ttm", "capex_ttm"]))

    dilution = available_metric("share_dilution_3y_pct")
    if live_like and dilution is not None:
        signal_quality = signal_source_quality({"share_dilution_3y_pct"})
        signals.append(_signal("share_dilution_risk", "caution" if dilution >= 10 else "neutral", signal_quality, [_metric_evidence("Share dilution 3Y pct", dilution)], limitations, []))
    else:
        signals.append(_signal("share_dilution_risk", "insufficient", "insufficient", [], limitations, ["share_dilution_3y_pct"]))

    scored = [signal for signal in signals if signal["status"] != "insufficient"]
    score_by_status = {"supportive": 85, "neutral": 60, "caution": 35}
    score = round(sum(score_by_status[signal["status"]] for signal in scored) / len(signals), 2) if scored else 0
    confidence = round(min(0.78, 0.25 + len(scored) * 0.055), 2)
    label = "strong" if score >= 70 and confidence >= 0.55 else "adequate" if score >= 45 else "caution" if scored else "insufficient"
    missing = sorted({item for signal in signals for item in signal["missing_data"]})
    source_status = build_source_status(
        {
            "source_type": "derived" if scored else "unknown",
            "provider": "derived_from_SEC_companyfacts_and_yfinance_financial_statement_signals" if filing_fields else "derived_from_yfinance_financial_statement_signals" if scored else "insufficient_financial_statement_evidence",
            "source_date": status.get("source_date", ""),
            "is_fresh": status.get("is_fresh", False),
            "limitations": limitations,
            "missing_data": missing,
            "fallback_used": status.get("fallback_used", False),
            "fallback_reason": status.get("fallback_reason"),
        }
    )
    return FinancialStatementSignals(
        score=score,
        confidence=confidence,
        label=label,
        signals=signals,
        source_status=source_status,
        limitations=limitations,
        missing_data=missing,
    )


def _limited(items: list[str], fallback: str, limit: int = 3) -> list[str]:
    clean = [str(item) for item in items if item]
    return clean[:limit] or [fallback]


def _excluded_indicator_names(macro_regime) -> list[str]:
    excluded = []
    for item in macro_regime.derived_metrics.get("scoring_model", {}).get("excluded_indicators", []):
        name = str(item.get("name") or "")
        if name == "ism_manufacturing_pmi":
            excluded.append("ISM Manufacturing PMI")
        elif name == "cnn_fear_greed":
            excluded.append("CNN Fear & Greed")
        elif name:
            excluded.append(name)
    return excluded


def _build_data_quality_summary(response: AnalyzeStockResponse) -> dict:
    component_statuses = {
        "macro_environment": _status_dict(response.macro_regime.source_status),
        "company_profile": _status_dict(response.company_profile.get("source_status")),
        "financial_quality": _status_dict(response.financial_quality.source_status),
        "valuation_context": _status_dict(response.valuation_context.source_status),
        "sec_financial_facts": _status_dict(response.sec_financial_facts.get("source_status")),
        "fundamentals_cross_check": _status_dict(response.fundamentals_cross_check.get("source_status")),
        "jane_company_quality": _status_dict(response.jane_company_quality.source_status),
        "financial_statement_signals": _status_dict(response.financial_statement_signals.source_status),
        "legacy_leadership_score": _status_dict(response.leadership_score.source_status),
        "smart_money": _status_dict(response.smart_money.source_status),
        "insider_activity": _status_dict(response.insider_activity.get("source_status")),
        "institutional_13f": _status_dict(response.institutional_13f.get("source_status")),
    }
    quality_criteria = response.jane_company_quality.criteria
    insufficient_evidence_categories = sorted(
        criterion.name for criterion in quality_criteria if criterion.status == "insufficient"
    )
    company_quality_breakdown = {
        "evidence_backed_criteria_count": sum(1 for criterion in quality_criteria if criterion.affects_score and criterion.source_quality in {"live_backed", "derived_live", "cached_live", "filing_backed", "derived_from_mixed_sources"}),
        "insufficient_criteria_count": sum(1 for criterion in quality_criteria if criterion.status == "insufficient"),
        "mock_criteria_count": sum(1 for criterion in quality_criteria if criterion.source_quality == "mock_only"),
        "derived_live_criteria_count": sum(1 for criterion in quality_criteria if criterion.source_quality == "derived_live"),
        "user_context_criteria_count": sum(1 for criterion in quality_criteria if criterion.source_quality == "user_context"),
        "filing_backed_criteria_count": sum(1 for criterion in quality_criteria if criterion.source_quality == "filing_backed"),
        "mixed_source_criteria_count": sum(1 for criterion in quality_criteria if criterion.source_quality == "derived_from_mixed_sources"),
    }
    mock_categories = sorted(
        name for name, status in component_statuses.items() if status.get("source_type") == "mock"
    )
    fallback_categories = sorted(
        name for name, status in component_statuses.items() if status.get("fallback_used") or status.get("source_type") == "fallback"
    )
    missing_source_date_categories = sorted(
        name for name, status in component_statuses.items() if not status.get("source_date") and status.get("source_type") != "unknown"
    )
    live_components = sum(1 for status in component_statuses.values() if status.get("source_type") in {"live", "cached_live", "derived"})
    mock_components = len(mock_categories)
    fallback_components = len(fallback_categories)
    stale_components = sum(
        1
        for status in component_statuses.values()
        if status.get("source_type") in {"live", "cached_live", "fallback", "derived"} and status.get("is_fresh") is False
    )
    legacy_only_mock = set(mock_categories) <= {"legacy_leadership_score"}
    critical_mock = {"company_profile", "financial_quality"} & set(mock_categories)
    if mock_components >= 4 or missing_source_date_categories:
        grade = "D"
    elif {"company_profile", "financial_quality"} & set(mock_categories):
        grade = "C"
    elif critical_mock and fallback_components:
        grade = "B"
    elif critical_mock or fallback_components or fallback_components:
        grade = "B"
    elif legacy_only_mock:
        grade = "B"
    else:
        grade = "A"
    if grade == "A":
        mode = "live_with_fallback" if fallback_components else "mixed_preliminary"
        summary = "Source quality is strong enough for a structured research validation view."
    elif grade == "B":
        mode = "mixed_preliminary"
        summary = "Live or derived source context is present, but some candidate-specific evidence remains preliminary."
    elif grade == "C":
        mode = "mixed_preliminary"
        summary = "Important company or fundamentals evidence remains mock-based or only partially improved."
    else:
        mode = "mostly_mock" if mock_components else "insufficient"
        summary = "Source quality is too limited for more than preliminary research triage."
    confidence_cap_applied = response.research_verdict.confidence <= MOCK_LEADERSHIP_CONFIDENCE_CAP and bool(critical_mock or fallback_components or insufficient_evidence_categories)
    cap_reason = None
    if confidence_cap_applied:
        cap_reason = "Legacy mock leadership, fallback/cached-limited evidence, or insufficient qualitative company-quality evidence caps analyze-stock confidence."
    return {
        "mode": mode,
        "confidence_cap_applied": confidence_cap_applied,
        "confidence_cap_reason": cap_reason,
        "live_components": live_components,
        "mock_components": mock_components,
        "fallback_components": fallback_components,
        "missing_source_date_components": len(missing_source_date_categories),
        "stale_components": stale_components,
        "source_quality_grade": grade,
        "source_quality_summary": summary,
        "mock_evidence_categories": mock_categories,
        "fallback_evidence_categories": fallback_categories,
        "missing_source_date_categories": missing_source_date_categories,
        "excluded_from_scoring": _excluded_indicator_names(response.macro_regime),
        "insufficient_evidence_categories": insufficient_evidence_categories,
        "company_quality": company_quality_breakdown,
        "sec_companyfacts": {
            "available": _status_dict(response.sec_financial_facts.get("source_status")).get("source_type") in {"live", "cached_live"},
            "source_type": _status_dict(response.sec_financial_facts.get("source_status")).get("source_type") or "insufficient",
            "filing_backed_metric_count": sum(1 for item in (response.sec_financial_facts.get("facts") or {}).values() if item),
            "missing_concept_count": len(response.sec_financial_facts.get("missing_data", [])),
            "latest_filing_date": response.sec_financial_facts.get("latest_filing_date"),
            "latest_report_period": response.sec_financial_facts.get("latest_report_period"),
            "agreement_level_with_yfinance": response.fundamentals_cross_check.get("agreement_level", "insufficient"),
        },
    }


def _build_insider_activity(score: ScoreObject) -> dict:
    status = _status_dict(score.source_status or score.raw_data.get("source_status"))
    metrics = score.derived_metrics
    transactions = score.raw_data.get("transactions", []) or []
    total = int(metrics.get("total_transactions_180d") or len(transactions))
    accumulation = int(metrics.get("accumulation_count_180d") or 0)
    disposition = int(metrics.get("disposition_count_180d") or 0)
    neutral_count = max(0, total - accumulation - disposition)
    source_quality = _source_quality_from_status(status, category="insider_activity")
    if source_quality == "mixed_with_fallback":
        summary = "Form 4 evidence is limited because fallback or cached-after-failure source context is present."
    elif total:
        summary = f"Form 4 review found {accumulation} code P accumulation rows and {disposition} code S disposition rows in the lookback window."
    else:
        summary = "No meaningful Form 4 transaction evidence is available in the current source snapshot."
    return {
        **score.model_dump(mode="json"),
        "summary": summary,
        "source_quality": source_quality,
        "form4_evidence": {
            "transactions": transactions,
            "transaction_row_cap": score.raw_data.get("transaction_row_cap"),
            "source_status": status,
            "not_investment_advice": True,
        },
        "accumulation_count": accumulation,
        "disposition_count": disposition,
        "neutral_or_excluded_transaction_count": neutral_count,
        "limitations": score.limitations,
        "missing_data": score.missing_data,
    }


def _build_institutional_13f(score: ScoreObject, ticker: str, sec_filings: dict) -> dict:
    raw = score.raw_data
    candidate = build_candidate_13f_evidence(
        ticker,
        sec_filings.get("institutional_13f_summary") or raw.get("portfolio_summary") or {},
        sec_filings.get("institutional_13f_target_matches") or {"target_matches": raw.get("target_matches", [])},
    )
    candidate_dict = candidate.model_dump(mode="json") if hasattr(candidate, "model_dump") else dict(candidate)
    status = _status_dict(candidate_dict.get("source_status") or score.source_status or raw.get("source_status"))
    candidate_specific = candidate_dict.get("candidate_specific_evidence") or {}
    if candidate_specific.get("matched_in_13f") is False:
        candidate_specific["score_contribution_allowed"] = False
        candidate_specific["interpretation_label"] = "no_reported_13f_position_observed"
    portfolio_context = candidate_dict.get("portfolio_context") or {}
    top_holdings = portfolio_context.get("top_holdings_by_value")
    if isinstance(top_holdings, list):
        portfolio_context["top_holdings_by_value"] = top_holdings[:5]
    return {
        **score.model_dump(mode="json"),
        "candidate_specific_evidence": candidate_specific,
        "portfolio_context": portfolio_context,
        "source_status": status,
        "limitations": sorted(set([*score.limitations, *candidate_dict.get("limitations", [])])),
        "missing_data": sorted(set([*score.missing_data, *candidate_dict.get("missing_data", [])])),
    }


def _build_evidence_matrix(response: AnalyzeStockResponse) -> list[dict]:
    company_status = _status_dict(response.company_profile.get("source_status"))
    financial_status = _status_dict(response.financial_quality.source_status)
    valuation_status = _status_dict(response.valuation_context.source_status)
    sec_status = _status_dict(response.sec_financial_facts.get("source_status"))
    cross_status = _status_dict(response.fundamentals_cross_check.get("source_status"))
    leadership_status = _status_dict(response.leadership_score.source_status)
    smart_status = _status_dict(response.smart_money.source_status)
    insider_status = _status_dict(response.insider_activity.get("source_status"))
    thirteen_f_status = _status_dict(response.institutional_13f.get("source_status"))
    macro_quality = response.macro_regime.macro_data_quality
    thirteen_f_candidate = response.institutional_13f.get("candidate_specific_evidence") or {}
    quality_supportive = [criterion for criterion in response.jane_company_quality.criteria if criterion.status == "supportive"]
    quality_insufficient = [criterion for criterion in response.jane_company_quality.criteria if criterion.status == "insufficient"]
    signal_supportive = [signal for signal in response.financial_statement_signals.signals if signal.status == "supportive"]
    signal_insufficient = [signal for signal in response.financial_statement_signals.signals if signal.status == "insufficient"]
    return [
        {
            "category": "macro_environment",
            "status": _score_status(response.macro_regime.score),
            "score": response.macro_regime.score,
            "confidence": response.macro_regime.confidence,
            "source_quality": "derived_live" if macro_quality and macro_quality.mock_context_score_weight_pct == 0 else _source_quality_from_status(_status_dict(response.macro_regime.source_status), category="macro_environment"),
            "summary": f"Macro score is {response.macro_regime.label} under macro_v12_5.",
            "key_evidence": _limited(
                [
                    f"Active macro weight total: {response.macro_regime.derived_metrics.get('scoring_model', {}).get('total_weight', 100)}",
                    f"Mock context score weight: {getattr(macro_quality, 'mock_context_score_weight_pct', 0) if macro_quality else 0}",
                    f"Excluded from scoring: {', '.join(_excluded_indicator_names(response.macro_regime))}",
                ],
                "Macro regime evidence unavailable.",
            ),
            "limitations": _limited(response.macro_regime.limitations, "No macro limitations listed."),
        },
        {
            "category": "company_profile",
            "status": "insufficient" if company_status.get("source_type") == "mock" else "neutral",
            "score": None,
            "confidence": 0.35 if company_status.get("source_type") == "mock" else 0.65,
            "source_quality": _source_quality_from_status(company_status),
            "summary": "Company profile uses live or cached yfinance context." if company_status.get("source_type") in {"live", "cached_live", "derived"} else "Company profile is mock-based preliminary context.",
            "key_evidence": _limited(
                [
                    str(response.company_profile.get("company_name", "")),
                    str(response.company_profile.get("sector", "")),
                    f"Market cap: {response.company_profile.get('market_cap')}",
                ],
                "Company profile evidence unavailable.",
            ),
            "limitations": _limited(company_status.get("limitations", []), "Company profile remains preliminary."),
        },
        {
            "category": "financial_quality",
            "status": _score_status(response.financial_quality.score),
            "score": response.financial_quality.score,
            "confidence": response.financial_quality.confidence,
            "source_quality": _source_quality_from_status(financial_status),
            "summary": "Financial quality uses live or cached yfinance fundamentals when available.",
            "key_evidence": _limited(
                [
                    f"Revenue TTM: {response.financial_quality.raw_data.get('revenue_ttm')}",
                    f"Revenue YoY growth: {response.financial_quality.raw_data.get('revenue_yoy_growth_pct')}%",
                    f"Gross margin: {response.financial_quality.raw_data.get('gross_margin_pct')}%",
                    f"Free cash flow TTM: {response.financial_quality.raw_data.get('free_cash_flow_ttm')}",
                ],
                "Financial quality evidence unavailable.",
            ),
            "limitations": _limited(response.financial_quality.limitations, "Financial quality source limitations unavailable."),
        },
        {
            "category": "valuation_context",
            "status": "caution" if response.valuation_context.label == "elevated" else "insufficient" if response.valuation_context.label == "insufficient" else "neutral",
            "score": response.valuation_context.score,
            "confidence": response.valuation_context.confidence,
            "source_quality": _source_quality_from_status(valuation_status),
            "summary": response.valuation_context.raw_data.get("valuation_summary", "Valuation context is risk context only."),
            "key_evidence": _limited(
                [
                    f"Price to sales TTM: {response.valuation_context.raw_data.get('price_to_sales_ttm')}",
                    f"EV to sales TTM: {response.valuation_context.raw_data.get('ev_to_sales_ttm')}",
                    f"Valuation risk label: {response.valuation_context.raw_data.get('valuation_risk_label')}",
                ],
                "Valuation context unavailable.",
            ),
            "limitations": _limited(response.valuation_context.limitations, "Valuation source limitations unavailable."),
        },
        {
            "category": "sec_financial_facts",
            "status": "neutral" if sec_status.get("source_type") in {"live", "cached_live"} else "insufficient",
            "score": None,
            "confidence": 0.72 if sec_status.get("source_type") in {"live", "cached_live"} else 0.25,
            "source_quality": _source_quality_from_status(sec_status, category="sec_financial_facts"),
            "summary": "SEC Companyfacts provides official filing-backed financial metric cross-checks.",
            "key_evidence": _limited(
                [
                    f"Filing-backed facts: {sum(1 for item in (response.sec_financial_facts.get('facts') or {}).values() if item)}",
                    f"Invalid derived metrics: {len(response.sec_financial_facts.get('invalid_derived_metrics') or {})}",
                    f"Aligned statement period: {response.sec_financial_facts.get('aligned_statement_period')}",
                    f"Aligned balance sheet period: {response.sec_financial_facts.get('aligned_balance_sheet_period')}",
                    f"Latest filing date: {response.sec_financial_facts.get('latest_filing_date')}",
                ],
                "SEC Companyfacts evidence unavailable.",
                limit=5,
            ),
            "limitations": _limited(response.sec_financial_facts.get("limitations", []), "SEC Companyfacts concept coverage varies by issuer."),
        },
        {
            "category": "fundamentals_cross_check",
            "status": "caution" if response.fundamentals_cross_check.get("agreement_level") == "low" else "neutral" if response.fundamentals_cross_check.get("agreement_level") in {"high", "moderate"} else "insufficient",
            "score": None,
            "confidence": 0.70 if response.fundamentals_cross_check.get("agreement_level") in {"high", "moderate"} else 0.35,
            "source_quality": _source_quality_from_status(cross_status, category="fundamentals_cross_check"),
            "summary": response.fundamentals_cross_check.get("summary", "SEC/yfinance cross-check unavailable."),
            "key_evidence": _limited(
                [
                    f"Agreement level: {response.fundamentals_cross_check.get('agreement_level')}",
                    f"Parser period alignment valid: {bool(response.fundamentals_cross_check.get('parser_period_alignment_valid'))}",
                    f"Provider normalization discrepancies: {bool(response.fundamentals_cross_check.get('provider_normalization_discrepancies'))}",
                    f"Divergence reason: {response.fundamentals_cross_check.get('divergence_reason')}",
                    f"Checked metrics: {len(response.fundamentals_cross_check.get('checked_metrics', []))}",
                    f"Divergent metrics: {sum(1 for item in response.fundamentals_cross_check.get('checked_metrics', []) if item.get('status') == 'divergent')}",
                ],
                "Cross-check evidence unavailable.",
                limit=6,
            ),
            "limitations": _limited(response.fundamentals_cross_check.get("limitations", []), "Cross-check limitations unavailable."),
        },
        {
            "category": "jane_company_quality",
            "status": _score_status(response.jane_company_quality.score),
            "score": response.jane_company_quality.score,
            "confidence": response.jane_company_quality.confidence,
            "source_quality": _source_quality_from_status(_status_dict(response.jane_company_quality.source_status)),
            "summary": "Jane company quality replaces mock leadership as the primary company-quality model.",
            "key_evidence": _limited(
                [
                    f"Evidence-backed criteria: {len(quality_supportive)} supportive",
                    f"Filing-backed criteria: {sum(1 for criterion in response.jane_company_quality.criteria if criterion.source_quality in {'filing_backed', 'derived_from_mixed_sources'})}",
                    f"Insufficient criteria: {len(quality_insufficient)}",
                    f"Label: {response.jane_company_quality.label}",
                ],
                "Jane company quality evidence unavailable.",
            ),
            "limitations": _limited(response.jane_company_quality.limitations, "Jane company quality limitations unavailable."),
        },
        {
            "category": "financial_statement_signals",
            "status": _score_status(response.financial_statement_signals.score),
            "score": response.financial_statement_signals.score,
            "confidence": response.financial_statement_signals.confidence,
            "source_quality": _source_quality_from_status(_status_dict(response.financial_statement_signals.source_status)),
            "summary": "Financial statement signals derive from available yfinance fundamentals and mark unavailable filing detail as insufficient.",
            "key_evidence": _limited(
                [
                    f"Supportive signals: {len(signal_supportive)}",
                    f"Insufficient signals: {len(signal_insufficient)}",
                    f"Label: {response.financial_statement_signals.label}",
                ],
                "Financial statement signal evidence unavailable.",
            ),
            "limitations": _limited(response.financial_statement_signals.limitations, "Financial statement signal limitations unavailable."),
        },
        {
            "category": "legacy_leadership_score",
            "status": "insufficient",
            "score": response.leadership_score.score,
            "confidence": response.leadership_score.confidence,
            "source_quality": "mock_only",
            "summary": "Legacy leadership score is mock-based and replaced by jane_company_quality.",
            "key_evidence": _limited(
                [
                    f"{response.leadership_score.derived_metrics.get('full_score_criteria', 0)} full-score criteria",
                    f"{response.leadership_score.derived_metrics.get('partial_score_criteria', 0)} partial-score criteria",
                ],
                "Legacy leadership evidence unavailable.",
            ),
            "limitations": _limited(response.leadership_score.limitations, "Leadership source limitations unavailable."),
        },
        {
            "category": "smart_money",
            "status": _score_status(response.smart_money.score),
            "score": response.smart_money.score,
            "confidence": response.smart_money.confidence,
            "source_quality": _source_quality_from_status(smart_status),
            "summary": "Aggregate smart-money score combines Form 4, 13F, and mock options context.",
            "key_evidence": _limited([f"Score: {response.smart_money.score}", f"Label: {response.smart_money.label}"], "Smart-money evidence unavailable."),
            "limitations": _limited(response.smart_money.limitations, "Smart-money source limitations unavailable."),
        },
        {
            "category": "insider_activity",
            "status": _score_status(response.insider_activity.get("score")),
            "score": response.insider_activity.get("score"),
            "confidence": float(response.insider_activity.get("confidence") or 0),
            "source_quality": response.insider_activity.get("source_quality", _source_quality_from_status(insider_status)),
            "summary": response.insider_activity.get("summary", "Form 4 evidence unavailable."),
            "key_evidence": [
                f"Code P accumulation rows: {response.insider_activity.get('accumulation_count', 0)}",
                f"Code S disposition rows: {response.insider_activity.get('disposition_count', 0)}",
                f"Neutral or excluded rows: {response.insider_activity.get('neutral_or_excluded_transaction_count', 0)}",
            ],
            "limitations": _limited(response.insider_activity.get("limitations", []), "Form 4 limitations unavailable."),
        },
        {
            "category": "institutional_13f",
            "status": "neutral" if thirteen_f_candidate.get("matched_in_13f") is False else _score_status(response.institutional_13f.get("score")),
            "score": response.institutional_13f.get("score"),
            "confidence": float(response.institutional_13f.get("confidence") or 0),
            "source_quality": _source_quality_from_status(thirteen_f_status),
            "summary": thirteen_f_candidate.get("interpretation_summary") or "13F evidence is delayed quarterly candidate context.",
            "key_evidence": [
                f"Matched in configured 13F: {bool(thirteen_f_candidate.get('matched_in_13f'))}",
                f"Score contribution allowed: {bool(thirteen_f_candidate.get('score_contribution_allowed'))}",
                f"Interpretation: {thirteen_f_candidate.get('interpretation_label', 'insufficient_13f_data')}",
            ],
            "limitations": _limited(response.institutional_13f.get("limitations", []), "13F limitations unavailable."),
        },
        {
            "category": "risk_flags",
            "status": "caution" if response.risk_flags else "neutral",
            "score": None,
            "confidence": 0.65,
            "source_quality": "derived_live",
            "summary": "Risk flags summarize valuation, social heat, financial quality, and macro caution checks.",
            "key_evidence": response.risk_flags or ["No current risk flags listed by deterministic rules."],
            "limitations": ["Risk flags are deterministic research checks and require human review."],
        },
    ]


def _build_manual_checks(response: AnalyzeStockResponse) -> list[dict]:
    dq = response.data_quality_summary
    has_mock = bool(dq.mock_evidence_categories)
    profile_live = "company_profile" not in dq.mock_evidence_categories and "company_profile" not in dq.fallback_evidence_categories
    fundamentals_live = "financial_quality" not in dq.mock_evidence_categories and "financial_quality" not in dq.fallback_evidence_categories
    checks = []
    sec_available = _status_dict(response.sec_financial_facts.get("source_status")).get("source_type") in {"live", "cached_live"}
    if sec_available:
        checks.append(
            {
                "priority": "medium",
                "area": "filings",
                "check": "Review SEC Companyfacts-derived trends against latest 10-K/10-Q narrative.",
                "reason": "Filing-backed numeric trends should be checked against management discussion and notes.",
            }
        )
    if response.sec_financial_facts.get("missing_data"):
        checks.append(
            {
                "priority": "medium",
                "area": "filings",
                "check": "Manually verify missing SEC concepts in latest filing.",
                "reason": "SEC Companyfacts concept coverage varies and missing concepts are not inferred.",
            }
        )
    if has_mock and not profile_live:
        checks.append(
            {
                "priority": "high",
                "area": "source_quality",
                "check": "Verify company profile and fundamentals with live company data.",
                "reason": "Mock evidence is present in score-critical candidate fields.",
            }
        )
    checks.extend(
        [
            {
                "priority": "high",
                "area": "leadership",
                "check": "Verify moat / monopoly power through market share, patents, or ecosystem evidence.",
                "reason": "Monopoly and moat criteria are insufficient until public evidence is reviewed.",
            },
            {
                "priority": "high",
                "area": "leadership",
                "check": "Verify founder/CEO quality and management tenure from public company sources.",
                "reason": "Legacy leadership_score is mock-based and retained only for backward compatibility.",
            },
            {
                "priority": "medium" if fundamentals_live else "high",
                "area": "filings",
                "check": "Verify R&D intensity and product roadmap from latest 10-K/10-Q.",
                "reason": "Continuous R&D and product evidence require filing-level validation.",
            },
            {
                "priority": "medium",
                "area": "company_fundamentals",
                "check": "Check whether network effects are supported by customer/platform/ecosystem evidence.",
                "reason": "Network effect is insufficient without ecosystem or usage evidence.",
            },
            {
                "priority": "medium",
                "area": "filings",
                "check": "Cross-check yfinance fundamentals against SEC filings.",
                "reason": "Yfinance fundamentals are MVP research reference data and should be checked against official filings.",
            },
            {
                "priority": "medium",
                "area": "filings",
                "check": "Review receivables, inventory, OCF, and CapEx trends from official filings.",
                "reason": "Missing detailed statement fields are marked insufficient instead of inferred.",
            },
            {
                "priority": "medium",
                "area": "smart_money",
                "check": "Confirm whether SEC Form 4 evidence is cached or fallback-limited and whether recent filings exist.",
                "reason": "Form 4 source quality can materially affect smart-money interpretation.",
            },
            {
                "priority": "medium",
                "area": "filings",
                "check": "Confirm whether the configured 13F manager reports a candidate-specific position.",
                "reason": "Portfolio context alone is not candidate-specific 13F support.",
            },
            {
                "priority": "medium",
                "area": "valuation",
                "check": "Validate valuation context before raising research priority.",
                "reason": "Valuation uses preliminary proxy context in this phase.",
            },
        ]
    )
    return checks


def _build_score_driver_breakdown(response: AnalyzeStockResponse) -> dict:
    positive = []
    limiting = []
    neutral = []
    macro_quality = next(
        (
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in response.evidence_matrix
            if (item.category if hasattr(item, "category") else item.get("category")) == "macro_environment"
        ),
        {},
    )
    if response.macro_regime.score >= 56:
        positive.append(
            {
                "name": "macro_v12_5_environment",
                "category": "macro_environment",
                "effect": "positive",
                "source_quality": macro_quality.get("source_quality", "derived_live"),
                "summary": "Macro environment is neutral-to-constructive using active scored components.",
            }
        )
    sec_metric_count = sum(1 for item in (response.sec_financial_facts.get("facts") or {}).values() if item)
    agreement = response.fundamentals_cross_check.get("agreement_level")
    if sec_metric_count >= 4:
        positive.append(
            {
                "name": "sec_filing_backed_financial_quality",
                "category": "sec_financial_facts",
                "effect": "positive",
                "source_quality": "filing_backed",
                "summary": "SEC Companyfacts provides filing-backed support for multiple financial metrics.",
            }
        )
    if agreement in {"high", "moderate"}:
        positive.append(
            {
                "name": "fundamentals_cross_check_consistent",
                "category": "fundamentals_cross_check",
                "effect": "positive",
                "source_quality": "derived_from_mixed_sources",
                "summary": "Comparable SEC Companyfacts and yfinance metrics are directionally consistent.",
            }
        )
    elif agreement == "low":
        limiting.append(
            {
                "name": "fundamentals_cross_check_divergent",
                "category": "fundamentals_cross_check",
                "effect": "limiting",
                "source_quality": "derived_from_mixed_sources",
                "summary": response.fundamentals_cross_check.get("summary") or "SEC Companyfacts and yfinance show material comparable differences that need review.",
            }
        )
    if response.sec_financial_facts.get("missing_data"):
        limiting.append(
            {
                "name": "sec_companyfacts_missing_concepts",
                "category": "sec_financial_facts",
                "effect": "insufficient",
                "source_quality": "filing_backed" if sec_metric_count else "insufficient",
                "summary": "Some SEC Companyfacts concepts are unavailable and are listed as missing data.",
            }
        )
    else:
        neutral.append(
            {
                "name": "macro_v12_5_environment",
                "category": "macro_environment",
                "effect": "insufficient" if response.macro_regime.label == "insufficient_data" else "limiting",
                "source_quality": macro_quality.get("source_quality", "insufficient"),
                "summary": "Macro environment is not a strong positive driver in the current score.",
            }
        )
    limiting.append(
        {
            "name": "legacy_leadership_mock_replaced",
            "category": "legacy_leadership_score",
            "effect": "limiting",
            "source_quality": "mock_only",
            "summary": "Legacy leadership evidence remains mock-only and is replaced by evidence-based Jane company quality criteria.",
        }
    )
    criteria_by_name = {criterion.name: criterion for criterion in response.jane_company_quality.criteria}
    for criterion_name, driver_name in [
        ("monopoly_power", "qualitative_moat_evidence_insufficient"),
        ("visionary_founder_ceo", "founder_ceo_evidence_insufficient"),
        ("network_effect", "network_effect_evidence_insufficient"),
        ("disruptive_innovation", "disruptive_innovation_evidence_insufficient"),
    ]:
        criterion = criteria_by_name.get(criterion_name)
        if criterion and criterion.status == "insufficient":
            limiting.append(
                {
                    "name": driver_name,
                    "category": "jane_company_quality",
                    "effect": "insufficient",
                    "source_quality": criterion.source_quality,
                    "summary": f"{criterion.display_name} is marked insufficient because required qualitative evidence is unavailable.",
                }
            )
    for criterion_name, driver_name in [
        ("scalability", "scalability_from_financials"),
        ("balance_sheet_strength", "balance_sheet_strength"),
        ("cash_flow_quality", "cash_flow_quality"),
    ]:
        criterion = criteria_by_name.get(criterion_name)
        if criterion and criterion.status == "supportive":
            positive.append(
                {
                    "name": driver_name,
                    "category": "jane_company_quality",
                    "effect": "positive",
                    "source_quality": criterion.source_quality,
                    "summary": f"{criterion.display_name} is supported by available financial metrics.",
                }
            )
    thirteen_f = response.institutional_13f.get("candidate_specific_evidence") or {}
    if thirteen_f.get("matched_in_13f") and thirteen_f.get("score_contribution_allowed"):
        positive.append(
            {
                "name": "candidate_specific_13f_match",
                "category": "institutional_13f",
                "effect": "positive",
                "source_quality": _source_quality_from_status(_status_dict(response.institutional_13f.get("source_status"))),
                "summary": "Candidate-specific 13F evidence is present and allowed to contribute.",
            }
        )
    else:
        neutral.append(
            {
                "name": "candidate_specific_13f_no_match",
                "category": "institutional_13f",
                "effect": "limiting",
                "source_quality": _source_quality_from_status(_status_dict(response.institutional_13f.get("source_status"))),
                "summary": "No candidate-specific 13F match contributes to the score; portfolio context remains audit context only.",
            }
        )
    if response.insider_activity.get("source_quality") in {"mixed_with_fallback", "insufficient"}:
        limiting.append(
            {
                "name": "form4_limited_source_quality",
                "category": "insider_activity",
                "effect": "limiting",
                "source_quality": response.insider_activity.get("source_quality", "insufficient"),
                "summary": "Form 4 evidence is limited by fallback, cached-after-failure, or insufficient source context.",
            }
        )
    financial_quality = _source_quality_from_status(_status_dict(response.financial_quality.source_status))
    if financial_quality in {"live_backed", "cached_live", "derived_live"} and response.financial_quality.derived_metrics.get("available_core_metric_count", 0) >= 3:
        target = positive if response.financial_quality.score >= 65 else neutral
        target.append(
            {
                "name": "live_financial_quality",
                "category": "financial_quality",
                "effect": "positive" if response.financial_quality.score >= 65 else "limiting",
                "source_quality": financial_quality,
                "summary": "Financial quality uses live or cached company fundamentals with core metrics available.",
            }
        )
    else:
        neutral.append(
            {
                "name": "financial_quality_not_live_confirmed",
                "category": "financial_quality",
                "effect": "insufficient",
                "source_quality": financial_quality,
                "summary": "Missing or mock fundamentals do not contribute as a positive driver.",
            }
        )
    valuation_quality = _source_quality_from_status(_status_dict(response.valuation_context.source_status))
    if response.valuation_context.label == "elevated":
        limiting.append(
            {
                "name": "valuation_context_elevated",
                "category": "valuation_context",
                "effect": "limiting",
                "source_quality": valuation_quality,
                "summary": "Elevated valuation is treated as research risk context only.",
            }
        )
    if response.missing_data:
        limiting.append(
            {
                "name": "missing_data",
                "category": "source_quality",
                "effect": "insufficient",
                "source_quality": response.data_quality_summary.source_quality_grade,
                "summary": "Missing data keeps the report at preliminary validation level.",
            }
        )
    return {
        "final_score": response.research_verdict.score,
        "final_confidence": response.research_verdict.confidence,
        "positive_drivers": positive,
        "negative_or_limiting_drivers": limiting,
        "neutral_drivers": neutral,
    }


def _build_candidate_summary(response: AnalyzeStockResponse) -> dict:
    dq = response.data_quality_summary
    leadership_mock = "legacy_leadership_score" in dq.mock_evidence_categories
    company_mock = "company_profile" in dq.mock_evidence_categories
    fundamentals_mock = "financial_quality" in dq.mock_evidence_categories
    company_live = not company_mock and "company_profile" not in dq.fallback_evidence_categories
    fundamentals_live = not fundamentals_mock and "financial_quality" not in dq.fallback_evidence_categories
    sec_available = bool(dq.sec_companyfacts.get("available"))
    sec_agreement = dq.sec_companyfacts.get("agreement_level_with_yfinance", "insufficient")
    sec_invalid = bool(response.sec_financial_facts.get("invalid_derived_metrics"))
    smart_limited = "smart_money" in dq.fallback_evidence_categories or "insider_activity" in dq.fallback_evidence_categories
    strengths = []
    if response.macro_regime.score >= 56:
        strengths.append("Macro context is neutral-to-constructive under macro_v12_5.")
    if response.smart_money.score >= 50:
        strengths.append("Aggregate smart-money score is neutral or better, with source limitations disclosed.")
    if company_live:
        strengths.append("Company profile is live or cached-live instead of mock-only.")
    if fundamentals_live:
        strengths.append("Financial quality includes live or cached fundamentals context.")
    if sec_available:
        strengths.append("SEC Companyfacts filing-backed financial facts are available for cross-checking.")
    if sec_agreement in {"high", "moderate"}:
        strengths.append("SEC Companyfacts and yfinance are directionally consistent for comparable metrics.")
    supportive_quality = [criterion for criterion in response.jane_company_quality.criteria if criterion.status == "supportive"]
    if any(criterion.name == "scalability" for criterion in supportive_quality):
        strengths.append("Live financial quality supports scalability under Jane company quality criteria.")
    if any(criterion.name == "financial_statement_quality" for criterion in supportive_quality):
        strengths.append("Revenue growth, margin, or free cash flow metrics support financial statement quality.")
    risks = []
    if leadership_mock:
        risks.append("Legacy leadership evidence is mock-based and cannot confirm live leadership quality.")
    if "monopoly_power" in dq.insufficient_evidence_categories:
        risks.append("Qualitative moat/founder/network/disruption evidence remains insufficient.")
    if company_mock:
        risks.append("Company profile remains mock-based.")
    if fundamentals_mock:
        risks.append("Financial quality remains mock-based or incomplete.")
    if sec_invalid:
        risks.append("SEC Companyfacts is available, but some derived metrics require period-alignment review.")
    if sec_agreement == "low":
        risks.append("SEC Companyfacts and yfinance show material discrepancies requiring review.")
    if smart_limited:
        risks.append("Smart-money evidence includes fallback or cached-limited components.")
    if response.risk_flags:
        risks.extend(response.risk_flags[:3])
    missing_or_mock = sorted(
        set(
            [
                *dq.fallback_evidence_categories,
                *response.missing_data[:5],
                *(["founder_ceo_evidence"] if "visionary_founder_ceo" in dq.insufficient_evidence_categories else []),
                *(["moat_or_patent_evidence"] if "monopoly_power" in dq.insufficient_evidence_categories else []),
                *(["network_effect_evidence"] if "network_effect" in dq.insufficient_evidence_categories else []),
                *(["disruptive_innovation_evidence"] if "disruptive_innovation" in dq.insufficient_evidence_categories else []),
                *(["R&D evidence"] if "continuous_r_and_d" in dq.insufficient_evidence_categories else []),
            ]
        )
    )
    env = f"Macro environment is {response.macro_regime.label} with {response.macro_regime.confidence:.2f} confidence."
    if company_live and fundamentals_live:
        company = "Live company profile and fundamentals are available; SEC filing-backed financial facts are available." if sec_available else "Live company profile and fundamentals are available; Jane company quality is partially evidence-backed by financial metrics, while qualitative moat/founder/network/disruption evidence remains insufficient."
        if sec_invalid:
            company = f"{company} SEC Companyfacts is available, but some derived metrics require period-alignment review."
        company = f"{company} SEC/yfinance agreement is {sec_agreement}; qualitative moat/founder/network/disruption evidence remains insufficient."
    elif company_live:
        company = "Live company profile is available; fundamentals and qualitative Jane company quality evidence still need verification."
    else:
        company = "Company evidence remains preliminary because profile, fundamentals, or qualitative company-quality data is incomplete."
    smart = "Smart-money assessment is limited by fallback or cached components." if smart_limited else f"Smart-money assessment is {response.smart_money.label}."
    overall = (
        f"{response.ticker} qualifies as a {response.research_verdict.label} research candidate under the current validation framework. "
        f"Macro context is {response.macro_regime.label}, company profile/fundamentals evidence "
        f"{'uses live or cached sources' if company_live and fundamentals_live else 'remains partly preliminary'}, Jane company quality "
        f"{'is partially evidence-backed by financial metrics' if response.jane_company_quality.label == 'preliminary' else response.jane_company_quality.label}, and smart-money evidence "
        f"{'includes fallback or cached-limited components' if smart_limited else 'is available with disclosed limitations'}. "
        "Further manual validation is required before treating the candidate as high conviction."
    )
    return {
        "ticker": response.ticker,
        "research_priority": response.research_verdict.label,
        "score": response.research_verdict.score,
        "confidence": response.research_verdict.confidence,
        "environment_assessment": env,
        "company_assessment": company,
        "smart_money_assessment": smart,
        "data_quality_assessment": f"Source quality grade {dq.source_quality_grade}: {dq.source_quality_summary}",
        "overall_summary": overall,
        "primary_strengths": strengths or ["No primary strengths are live-confirmed yet."],
        "primary_risks": risks or ["No major deterministic risk flags, but manual verification is still required."],
        "missing_or_mock_evidence": missing_or_mock,
        "next_manual_checks": [
            item.check if hasattr(item, "check") else str(item.get("check", ""))
            for item in response.next_manual_checks
        ],
    }


def analyze_stock(request: AnalyzeStockRequest) -> AnalyzeStockResponse:
    fixture = STOCK_FIXTURES.get(request.ticker, DEFAULT_STOCK)
    market_context = read_market_data()
    macro_snapshot = read_macro_data("normal", market_context_seed=market_context)
    macro_regime = evaluate_macro_regime(macro_snapshot)
    sec_filings = read_sec_filings(request.ticker)
    company_profile = get_company_profile(request.ticker)
    yfinance_fundamentals = get_company_fundamentals(request.ticker)
    sec_financial_facts = get_sec_companyfacts(request.ticker)
    fundamentals_cross_check = _build_fundamentals_cross_check(sec_financial_facts, yfinance_fundamentals)
    company_fundamentals = _merge_financials_with_sec(yfinance_fundamentals, sec_financial_facts, fundamentals_cross_check)
    smart_money_data = {**fixture["smart_money"], **sec_filings}
    engine_context = {
        **fixture,
        **market_context,
        "user_reported_social_heat": request.user_context.social_discussion_level,
        "friends_asking_about_stock": request.user_context.friends_asking_about_stock,
    }
    missing_data = list(fixture["missing_data"])
    if company_profile.get("source_status", {}).get("source_type") not in {"live", "cached_live", "derived"}:
        missing_data.append("live yfinance company profile")
    if company_fundamentals.get("source_status", {}).get("source_type") not in {"live", "cached_live", "derived"}:
        missing_data.append("live yfinance fundamentals")
    if sec_financial_facts.get("source_status", {}).get("source_type") not in {"live", "cached_live"}:
        missing_data.append("SEC Companyfacts filing-backed fundamentals")
    missing_data.extend(company_profile.get("missing_data", []))
    missing_data.extend(company_fundamentals.get("missing_data", []))
    if market_context.get("source_type") != "live":
        missing_data.append("live price history")
    if sec_filings.get("form4_source_status", {}).get("source_type") not in {"live", "cached_live"}:
        missing_data.append("live SEC filing details")
    if sec_filings.get("institutional_13f_source_status", {}).get("source_type") not in {"live", "cached_live"}:
        missing_data.append("live SEC 13F data")
    missing_data.extend(macro_regime.missing_data)
    missing_data = sorted(set(missing_data))
    leadership_score = evaluate_leadership({"ticker": request.ticker, **fixture})
    legacy_limitation = "Legacy leadership_score is mock-based and is retained for backward compatibility only."
    if legacy_limitation not in leadership_score.limitations:
        leadership_score.limitations.append(legacy_limitation)
    leadership_score.deprecated_by = "jane_company_quality"
    leadership_score.affects_score = False
    leadership_score.legacy_affects_score = False
    leadership_score.source_quality = "mock_only"
    market_timing_context = evaluate_market_timing(engine_context)
    overheat_risk = evaluate_overheat(engine_context)
    smart_money = evaluate_smart_money(smart_money_data)
    insider_activity = smart_money.derived_metrics["components"]["insider_form4_signal"]
    institutional_13f = smart_money.derived_metrics["components"]["institutional_support_13f"]
    if not hasattr(insider_activity, "model_dump"):
        insider_activity = ScoreObject.model_validate(insider_activity)
    if not hasattr(institutional_13f, "model_dump"):
        institutional_13f = ScoreObject.model_validate(institutional_13f)
    leadership_status = build_source_status(leadership_score.model_dump(mode="json"))
    leadership_score.source_status = leadership_status
    company_profile_status = build_source_status(company_profile)
    financial_quality = _build_financial_quality_score(company_fundamentals)
    valuation_context = _build_valuation_context(company_profile, company_fundamentals)
    research_context = request.research_context.model_dump(exclude_none=True) if request.research_context else {}
    jane_company_quality = _build_jane_company_quality(financial_quality, research_context)
    financial_statement_signals = _build_financial_statement_signals(financial_quality)
    quality_insufficient = [criterion.name for criterion in jane_company_quality.criteria if criterion.status == "insufficient"]
    missing_data.extend(
        [
            *(["founder_ceo_evidence"] if "visionary_founder_ceo" in quality_insufficient else []),
            *(["moat_or_patent_evidence"] if "monopoly_power" in quality_insufficient else []),
            *(["network_effect_evidence"] if "network_effect" in quality_insufficient else []),
            *(["disruptive_innovation_evidence"] if "disruptive_innovation" in quality_insufficient else []),
            *(["R&D evidence"] if "continuous_r_and_d" in quality_insufficient else []),
        ]
    )
    missing_data = sorted(set(missing_data))
    form4_status = sec_filings.get("form4_source_status", {})
    thirteen_f_status = sec_filings.get("institutional_13f_source_status", {})
    mock_evidence_present = (
        leadership_status.source_type == "mock"
        or company_profile_status.source_type == "mock"
        or bool(financial_quality.source_status and financial_quality.source_status.source_type == "mock")
        or market_context.get("source_type") in {"mock", "fallback"}
    )
    fallback_evidence_present = any(
        status.get("fallback_used") or status.get("source_type") == "fallback"
        for status in [
            form4_status,
            thirteen_f_status,
            _status_dict(smart_money.source_status),
            _status_dict(company_profile.get("source_status")),
            _status_dict(financial_quality.source_status),
            _status_dict(valuation_context.source_status),
        ]
        if status
    )
    macro_provider = macro_regime.source_status.provider if macro_regime.source_status else ""
    live_macro_present = macro_provider == "mixed_FRED_and_yfinance_macro" or macro_regime.source_status and macro_regime.source_status.source_type in {"live", "cached_live", "derived"}
    research_verdict = _research_verdict(
        company_quality_score=jane_company_quality.score,
        company_quality_confidence=jane_company_quality.confidence,
        key_qualitative_insufficient=any(
            name in quality_insufficient
            for name in ["monopoly_power", "visionary_founder_ceo", "network_effect", "disruptive_innovation"]
        ),
        smart_money_score=smart_money.score,
        macro_score=macro_regime.score,
        overheat_score=overheat_risk.score,
        missing_data_count=len(missing_data),
        confidence_inputs=[leadership_score.confidence, smart_money.confidence, macro_regime.confidence, overheat_risk.confidence, financial_quality.confidence],
        mock_evidence_present=mock_evidence_present,
        fallback_evidence_present=fallback_evidence_present,
        live_macro_present=bool(live_macro_present),
    )
    insider_activity_payload = _build_insider_activity(insider_activity)
    institutional_13f_payload = _build_institutional_13f(institutional_13f, request.ticker, sec_filings)

    response = AnalyzeStockResponse(
        ticker=request.ticker,
        analysis_mode="ticker_validation",
        research_verdict=research_verdict,
        candidate_validation_summary={
            "ticker": request.ticker,
            "research_priority": research_verdict.label,
            "score": research_verdict.score,
            "confidence": research_verdict.confidence,
            "environment_assessment": "Pending evidence composition.",
            "company_assessment": "Pending evidence composition.",
            "smart_money_assessment": "Pending evidence composition.",
            "data_quality_assessment": "Pending evidence composition.",
            "overall_summary": "Pending evidence composition.",
            "primary_strengths": [],
            "primary_risks": [],
            "missing_or_mock_evidence": [],
            "next_manual_checks": [],
        },
        evidence_matrix=[],
        data_quality_summary={
            "mode": "insufficient",
            "confidence_cap_applied": False,
            "confidence_cap_reason": None,
            "live_components": 0,
            "mock_components": 0,
            "fallback_components": 0,
            "missing_source_date_components": 0,
            "stale_components": 0,
            "source_quality_grade": "D",
            "source_quality_summary": "Pending evidence composition.",
            "mock_evidence_categories": [],
            "fallback_evidence_categories": [],
            "missing_source_date_categories": [],
            "excluded_from_scoring": [],
        },
        score_driver_breakdown={
            "final_score": research_verdict.score,
            "final_confidence": research_verdict.confidence,
            "positive_drivers": [],
            "negative_or_limiting_drivers": [],
            "neutral_drivers": [],
        },
        next_manual_checks=[],
        company_profile={
            **company_profile,
            "themes": company_profile.get("themes", fixture["themes"]),
            "market_price_source_type": market_context.get("source_type", "mock"),
            "research_context": research_context,
        },
        macro_regime=macro_regime,
        leadership_score=leadership_score,
        jane_company_quality=jane_company_quality,
        financial_statement_signals=financial_statement_signals,
        sec_financial_facts=sec_financial_facts,
        fundamentals_cross_check=fundamentals_cross_check,
        market_timing_context=market_timing_context,
        overheat_risk=overheat_risk,
        smart_money=smart_money,
        insider_activity=insider_activity_payload,
        institutional_13f=institutional_13f_payload,
        financial_quality=financial_quality,
        valuation_context=valuation_context,
        risk_flags=[
            flag
            for flag, present in {
                "valuation_context_elevated": valuation_context.label == "elevated",
                "social_heat_elevated": request.user_context.social_discussion_level == "high",
                "financial_quality_mixed": financial_quality.score < 50,
                "macro_context_cautious": macro_regime.score < 45,
            }.items()
            if present
        ],
        jane_reference_conditions=_build_jane_reference_conditions(macro_snapshot),
        jane_quality_methodology_reference={
            "framework": "Jane 7-principle company quality framework",
            "principles": JANE_QUALITY_PRINCIPLES,
            "affects_score": True,
            "limitations": [
                "Qualitative principles require evidence and are marked insufficient when not verifiable.",
                "User-provided theme is context only and is not independently verified evidence.",
            ],
        },
        missing_data=missing_data,
        human_verification_queue=[
            "Verify company fundamentals with current filings.",
            "Review current news and filings before using this research output.",
        ],
    )
    statuses: list = []
    _enrich_source_status(response, statuses)
    response.source_status = build_source_status(market_context)
    statuses.append(response.source_status)
    response.data_quality = summarize_data_quality(statuses)
    if response.data_quality.mock_components and MOCK_EVIDENCE_LIMITATION not in response.data_quality.limitations:
        response.data_quality.limitations.append(MOCK_EVIDENCE_LIMITATION)
    if macro_regime.macro_data_quality:
        response.data_quality.macro = {
            "provider": macro_regime.source_status.provider if macro_regime.source_status else macro_snapshot.get("provider", "unknown"),
            "live_macro_fields_count": macro_regime.macro_data_quality.live_macro_fields_count,
            "derived_macro_fields_count": macro_regime.macro_data_quality.derived_macro_fields_count,
            "mock_macro_fields_count": macro_regime.macro_data_quality.mock_macro_fields_count,
            "yfinance_macro_fields_count": macro_regime.macro_data_quality.yfinance_macro_fields_count,
            "has_mock_macro_context": macro_regime.macro_data_quality.has_mock_macro_context,
            "mock_context_fields": macro_regime.macro_data_quality.mock_context_fields,
            "fred_backed_fields": macro_regime.macro_data_quality.fred_backed_fields,
            "derived_from_fred_fields": macro_regime.macro_data_quality.derived_from_fred_fields,
            "yfinance_backed_fields": macro_regime.macro_data_quality.yfinance_backed_fields,
            "derived_from_yfinance_fields": macro_regime.macro_data_quality.derived_from_yfinance_fields,
            "excluded_indicators": macro_regime.macro_data_quality.excluded_indicators,
            "scoring": macro_regime.macro_data_quality.scoring,
            "market_context_reused_from_daily_market_data": (macro_regime.raw_data.get("raw_market_context") or {}).get("diagnostics", {}).get("market_context_reused_from_daily_market_data"),
            "confidence_adjustment_applied": macro_regime.macro_data_quality.confidence_adjustment_applied,
        }
    if response.data_quality.fallback_components:
        response.human_verification_queue.append("Review fallback source status because one or more live data sources were unavailable.")
    if response.data_quality.stale_components:
        response.human_verification_queue.append("Review stale live or derived data source status before interpreting scores.")
    if response.data_quality.missing_source_date_components:
        response.human_verification_queue.append("Review components with missing source dates before interpreting scores.")
    response.data_quality_summary = AnalyzeStockDataQualitySummary.model_validate(_build_data_quality_summary(response))
    response.evidence_matrix = [EvidenceMatrixItem.model_validate(item) for item in _build_evidence_matrix(response)]
    response.next_manual_checks = [NextManualCheck.model_validate(item) for item in _build_manual_checks(response)]
    response.score_driver_breakdown = ScoreDriverBreakdown.model_validate(_build_score_driver_breakdown(response))
    response.candidate_validation_summary = CandidateValidationSummary.model_validate(_build_candidate_summary(response))
    return AnalyzeStockResponse.model_validate(_sanitize_api_secret_markers(response.model_dump(mode="json")))
