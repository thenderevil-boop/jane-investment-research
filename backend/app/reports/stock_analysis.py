from __future__ import annotations

from backend.app.data_sources.mock_data import DEFAULT_STOCK, MOCK_SOURCE_DATE, STOCK_FIXTURES
from backend.app.engines.leadership_engine import evaluate_leadership
from backend.app.engines.macro_regime_engine import evaluate_macro_regime
from backend.app.engines.market_timing_engine import evaluate_market_timing
from backend.app.engines.overheat_engine import evaluate_overheat
from backend.app.engines.sec_13f_target_matching import build_candidate_13f_evidence
from backend.app.engines.smart_money_engine import evaluate_smart_money
from backend.app.pipelines.mock_pipeline import _build_jane_reference_conditions, _enrich_source_status, score_object
from backend.app.raw_store.repository import get_company_fundamentals, get_company_profile, read_macro_data, read_market_data, read_sec_filings
from backend.app.schemas.common import ScoreObject
from backend.app.schemas.stock_analysis import (
    AnalyzeStockDataQualitySummary,
    AnalyzeStockRequest,
    AnalyzeStockResponse,
    CandidateValidationSummary,
    EvidenceMatrixItem,
    NextManualCheck,
    ResearchVerdict,
    ScoreDriverBreakdown,
)
from backend.app.utils.freshness import build_source_status, summarize_data_quality

MOCK_LEADERSHIP_CONFIDENCE_CAP = 0.72
MOCK_EVIDENCE_LIMITATION = "Mock evidence limits analyze-stock confidence; treat mock-based components as preliminary validation only."


def _research_verdict(
    *,
    leadership_percent: float,
    smart_money_score: float,
    macro_score: float,
    overheat_score: float,
    missing_data_count: int,
    confidence_inputs: list[float],
    mock_evidence_present: bool = False,
    fallback_evidence_present: bool = False,
    live_macro_present: bool = False,
) -> ResearchVerdict:
    raw_score = leadership_percent * 0.45 + smart_money_score * 0.25 + macro_score * 0.20 + max(0, 100 - overheat_score) * 0.10
    missing_penalty = min(25, missing_data_count * 3)
    score = round(max(0, min(100, raw_score - missing_penalty)), 2)
    confidence = max(0.15, min(1, (sum(confidence_inputs) / len(confidence_inputs)) - min(0.35, missing_data_count * 0.03)))
    if mock_evidence_present:
        confidence = min(confidence, MOCK_LEADERSHIP_CONFIDENCE_CAP)
    if fallback_evidence_present:
        confidence = min(confidence, 0.75)
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
    if mock_evidence_present:
        limiters.append("Leadership or company-related evidence is mock-based.")
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


def _source_quality_from_status(status: dict, *, category: str = "") -> str:
    source_type = status.get("source_type")
    provider = str(status.get("provider") or "")
    fallback_used = bool(status.get("fallback_used")) or source_type == "fallback"
    if category == "macro_environment" and source_type == "derived" and provider.startswith("mixed_FRED"):
        return "derived_live"
    if fallback_used:
        return "mixed_with_fallback"
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
        "leadership_score": _status_dict(response.leadership_score.source_status),
        "smart_money": _status_dict(response.smart_money.source_status),
        "insider_activity": _status_dict(response.insider_activity.get("source_status")),
        "institutional_13f": _status_dict(response.institutional_13f.get("source_status")),
    }
    mock_categories = sorted(
        name for name, status in component_statuses.items() if status.get("source_type") == "mock"
    )
    fallback_categories = sorted(
        name for name, status in component_statuses.items() if status.get("fallback_used") or status.get("source_type") == "fallback"
    )
    missing_source_date_categories = sorted(
        name for name, status in component_statuses.items() if not status.get("source_date")
    )
    live_components = sum(1 for status in component_statuses.values() if status.get("source_type") in {"live", "cached_live", "derived"})
    mock_components = len(mock_categories)
    fallback_components = len(fallback_categories)
    stale_components = sum(
        1
        for status in component_statuses.values()
        if status.get("source_type") in {"live", "cached_live", "fallback", "derived"} and status.get("is_fresh") is False
    )
    critical_mock = {"company_profile", "financial_quality", "leadership_score"} & set(mock_categories)
    if mock_components >= 4 or missing_source_date_categories:
        grade = "D"
    elif {"company_profile", "financial_quality"} & set(mock_categories):
        grade = "C"
    elif critical_mock and fallback_components:
        grade = "B"
    elif critical_mock or fallback_components:
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
    confidence_cap_applied = response.research_verdict.confidence <= MOCK_LEADERSHIP_CONFIDENCE_CAP and bool(critical_mock or fallback_components)
    cap_reason = None
    if confidence_cap_applied:
        cap_reason = "Mock leadership evidence or fallback/cached-limited evidence caps analyze-stock confidence."
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
    leadership_status = _status_dict(response.leadership_score.source_status)
    smart_status = _status_dict(response.smart_money.source_status)
    insider_status = _status_dict(response.insider_activity.get("source_status"))
    thirteen_f_status = _status_dict(response.institutional_13f.get("source_status"))
    macro_quality = response.macro_regime.macro_data_quality
    thirteen_f_candidate = response.institutional_13f.get("candidate_specific_evidence") or {}
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
            "category": "leadership_score",
            "status": _score_status(response.leadership_score.score / response.leadership_score.max_score * 100),
            "score": response.leadership_score.score,
            "confidence": response.leadership_score.confidence,
            "source_quality": _source_quality_from_status(leadership_status),
            "summary": "Jane 20-item leadership score is preliminary while source evidence remains mock-based.",
            "key_evidence": _limited(
                [
                    f"{response.leadership_score.derived_metrics.get('full_score_criteria', 0)} full-score criteria",
                    f"{response.leadership_score.derived_metrics.get('partial_score_criteria', 0)} partial-score criteria",
                ],
                "Leadership evidence unavailable.",
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
                "priority": "high" if "leadership_score" in dq.mock_evidence_categories else "medium",
                "area": "leadership",
                "check": "Replace mock leadership evidence with live public evidence.",
                "reason": "Jane 20-item leadership quality should not be treated as live-confirmed while mock-based.",
            },
            {
                "priority": "medium" if fundamentals_live else "high",
                "area": "filings",
                "check": "Review latest 10-K/10-Q footnotes and segment trends.",
                "reason": "Automated fundamentals require human review against filed disclosures and segment context.",
            },
            {
                "priority": "medium",
                "area": "company_fundamentals",
                "check": "Confirm whether reported fundamentals align with external thesis.",
                "reason": "User-provided research context remains separate from source evidence.",
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
    leadership_quality = _source_quality_from_status(_status_dict(response.leadership_score.source_status))
    if leadership_quality == "mock_only":
        limiting.append(
            {
                "name": "preliminary_positive_but_mock_limited",
                "category": "leadership_score",
                "effect": "limiting",
                "source_quality": leadership_quality,
                "summary": "Leadership score is numerically supportive but mock-only, so it limits conviction instead of acting as live-confirmed evidence.",
            }
        )
    elif response.leadership_score.score >= 12:
        positive.append(
            {
                "name": "leadership_score",
                "category": "leadership_score",
                "effect": "positive",
                "source_quality": leadership_quality,
                "summary": "Leadership evidence clears the watchlist-level threshold.",
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
    leadership_mock = "leadership_score" in dq.mock_evidence_categories
    company_mock = "company_profile" in dq.mock_evidence_categories
    fundamentals_mock = "financial_quality" in dq.mock_evidence_categories
    company_live = not company_mock and "company_profile" not in dq.fallback_evidence_categories
    fundamentals_live = not fundamentals_mock and "financial_quality" not in dq.fallback_evidence_categories
    smart_limited = "smart_money" in dq.fallback_evidence_categories or "insider_activity" in dq.fallback_evidence_categories
    strengths = []
    if response.macro_regime.score >= 56:
        strengths.append("Macro context is neutral-to-constructive under macro_v12_5.")
    if response.smart_money.score >= 50:
        strengths.append("Aggregate smart-money score is neutral or better, with source limitations disclosed.")
    if response.leadership_score.score >= 12 and not leadership_mock:
        strengths.append("Leadership score clears watchlist-level threshold with non-mock source context.")
    elif response.leadership_score.score >= 12:
        strengths.append("Mock leadership score clears watchlist-level threshold but remains preliminary.")
    if company_live:
        strengths.append("Company profile is live or cached-live instead of mock-only.")
    if fundamentals_live:
        strengths.append("Financial quality includes live or cached fundamentals context.")
    risks = []
    if leadership_mock:
        risks.append("Leadership evidence is mock-based and cannot confirm live leadership quality.")
    if company_mock:
        risks.append("Company profile remains mock-based.")
    if fundamentals_mock:
        risks.append("Financial quality remains mock-based or incomplete.")
    if smart_limited:
        risks.append("Smart-money evidence includes fallback or cached-limited components.")
    if response.risk_flags:
        risks.extend(response.risk_flags[:3])
    missing_or_mock = sorted(set([*dq.mock_evidence_categories, *dq.fallback_evidence_categories, *response.missing_data[:5]]))
    env = f"Macro environment is {response.macro_regime.label} with {response.macro_regime.confidence:.2f} confidence."
    if company_live and fundamentals_live and leadership_mock:
        company = "Live company profile and fundamentals are available; leadership evidence remains mock-based until a later phase."
    elif company_live:
        company = "Live company profile is available; fundamentals or leadership evidence still needs verification."
    else:
        company = "Company evidence remains preliminary because profile, fundamentals, or leadership data is mock-based."
    smart = "Smart-money assessment is limited by fallback or cached components." if smart_limited else f"Smart-money assessment is {response.smart_money.label}."
    overall = (
        f"{response.ticker} qualifies as a {response.research_verdict.label} research candidate under the current validation framework. "
        f"Macro context is {response.macro_regime.label}, company profile/fundamentals evidence "
        f"{'uses live or cached sources' if company_live and fundamentals_live else 'remains partly preliminary'}, leadership evidence "
        f"{'remains mock-based' if leadership_mock else 'has source metadata'}, and smart-money evidence "
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
    company_fundamentals = get_company_fundamentals(request.ticker)
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
    market_timing_context = evaluate_market_timing(engine_context)
    overheat_risk = evaluate_overheat(engine_context)
    smart_money = evaluate_smart_money(smart_money_data)
    insider_activity = smart_money.derived_metrics["components"]["insider_form4_signal"]
    institutional_13f = smart_money.derived_metrics["components"]["institutional_support_13f"]
    if not hasattr(insider_activity, "model_dump"):
        insider_activity = ScoreObject.model_validate(insider_activity)
    if not hasattr(institutional_13f, "model_dump"):
        institutional_13f = ScoreObject.model_validate(institutional_13f)
    leadership_percent = leadership_score.score / leadership_score.max_score * 100
    leadership_status = build_source_status(leadership_score.model_dump(mode="json"))
    company_profile_status = build_source_status(company_profile)
    financial_quality = _build_financial_quality_score(company_fundamentals)
    valuation_context = _build_valuation_context(company_profile, company_fundamentals)
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
    research_context = request.research_context.model_dump(exclude_none=True) if request.research_context else {}
    research_verdict = _research_verdict(
        leadership_percent=leadership_percent,
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
    return response
