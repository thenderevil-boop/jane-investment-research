from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.manual_evidence import ManualQualitativeEvidence, ManualQualitativeEvidencePatch
from backend.app.schemas.operations_diagnostics import OperationsDiagnosticsResponse
from backend.app.schemas.operations_settings import SEC13FManagerUniverseSettings
from backend.app.schemas.stock_analysis import AnalyzeStockResponse, QualitativeEvidenceInput
from backend.app.utils.forbidden_language import detect_forbidden_language

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_schema() -> dict:
    return json.loads(_read("schemas/analyze_stock.schema.json"))


def _load_manual_evidence_schema() -> dict:
    return json.loads(_read("schemas/manual_evidence.schema.json"))


def _load_manual_evidence_dashboard_schema() -> dict:
    return json.loads(_read("schemas/manual_evidence_dashboard.schema.json"))


def _normalize(value: dict) -> dict:
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False))


def test_committed_analyze_stock_schema_matches_pydantic_response_schema() -> None:
    committed = _normalize(_load_schema())
    generated = _normalize(AnalyzeStockResponse.model_json_schema())

    assert committed == generated


def test_phase27b_qualitative_evidence_metadata_contract_is_documented() -> None:
    props = QualitativeEvidenceInput.model_json_schema()["properties"]

    for field in ["criterion_id", "criterion_name", "submetric"]:
        assert field in props
        assert field in _read("docs/API_SPEC.md")
        assert field in _read("frontend/src/types.ts")

    criterion_id_schema = props["criterion_id"]["anyOf"][0]
    assert criterion_id_schema["minimum"] == 1
    assert criterion_id_schema["maximum"] == 20


def test_phase28_and_phase29_response_fields_are_in_schema_docs_and_types() -> None:
    schema = _load_schema()
    top_level_props = schema["properties"]
    defs = schema["$defs"]
    api_spec = _read("docs/API_SPEC.md")
    frontend_types = _read("frontend/src/types.ts")

    for field in ["jane_criteria_coverage", "validation_os_report"]:
        assert field in top_level_props
        assert field in api_spec
        assert field in frontend_types

    for definition in [
        "JaneCriterionCoverageItem",
        "JaneCriteriaCoverageMatrix",
        "ValidationOSEvidenceGap",
        "ValidationOSReport",
    ]:
        assert definition in defs
        assert definition in frontend_types


def test_phase61_research_workflow_summary_contract_is_documented() -> None:
    schema = _load_schema()
    top_level_props = schema["properties"]
    defs = schema["$defs"]
    api_spec = _read("docs/API_SPEC.md")
    changelog = _read("docs/CHANGELOG.md")
    frontend_types = _read("frontend/src/types.ts")

    assert "research_workflow_summary" in top_level_props
    assert "research_workflow_summary" in api_spec
    assert "research_workflow_summary" in changelog
    assert "research_workflow_summary" in frontend_types
    assert "ResearchWorkflowSummary" in defs
    assert "ResearchWorkflowSummary" in frontend_types
    for status in [
        "high_conviction_candidate",
        "watchlist_candidate",
        "needs_evidence_before_research",
        "deprioritize_data_gaps",
    ]:
        assert status in api_spec
        assert status in frontend_types


def test_phase33_research_note_workflow_contract_is_documented() -> None:
    schema = _load_schema()
    evidence_item_props = schema["$defs"]["QualitativeEvidenceAssessmentItem"]["properties"]
    manual_evidence_props = ManualQualitativeEvidence.model_json_schema()["properties"]
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    frontend_types = _read("frontend/src/types.ts")

    for field in ["note_title", "research_question", "thesis_direction", "workflow_status"]:
        assert field in evidence_item_props
        assert field in manual_evidence_props
        assert field in api_spec
        assert field in readme
        assert field in changelog
        assert field in frontend_types

    assert "ManualEvidenceThesisDirection" in frontend_types
    assert "ManualEvidenceWorkflowStatus" in frontend_types


def test_phase49_evidence_freshness_contract_is_documented() -> None:
    schema = _load_schema()
    top_level_props = schema["properties"]
    defs = schema["$defs"]
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    frontend_types = _read("frontend/src/types.ts")

    for field in ["evidence_freshness_policy", "stale_review_queue"]:
        assert field in top_level_props
        assert field in api_spec
        assert field in readme
        assert field in changelog
        assert field in frontend_types

    for definition in ["EvidenceFreshnessPolicy", "StaleReviewQueue", "StaleReviewQueueItem"]:
        assert definition in defs
        assert definition in frontend_types

    for token in ["phase49_evidence_freshness_v1", "refresh_or_archive", "verify_or_refresh_source"]:
        assert token in api_spec
        assert token in frontend_types


def test_phase51_foreign_filer_diagnostics_contract_is_documented() -> None:
    schema = _load_schema()
    top_level_props = schema["properties"]
    defs = schema["$defs"]
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    frontend_types = _read("frontend/src/types.ts")

    assert "foreign_filer_coverage_diagnostics" in top_level_props
    assert "ForeignFilerCoverageDiagnostics" in defs
    assert "ForeignFilerCoverageLimitation" in defs
    assert "ForeignFilerManualCheck" in defs

    for text in [api_spec, readme, changelog, frontend_types]:
        assert "foreign_filer_coverage_diagnostics" in text

    for token in ["sec_companyfacts", "sec_form4", "fmp_transcript", "local_filings", "manual_verification_required"]:
        assert token in api_spec
        assert token in frontend_types


def test_phase53_uspto_activation_and_adr_grade_explanation_contract_is_documented() -> None:
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    data_sources = _read("docs/DATA_SOURCES.md")
    framework = _read("docs/JANE_FRAMEWORK_MAPPING.md")

    for text in [api_spec, readme, changelog, data_sources, framework]:
        assert "Phase 53" in text
        assert "USE_LIVE_USPTO_PATENTS_DATA" in text
        assert "shortRatio" in text
        assert "source coverage" in text or "source-quality" in text

    assert "Grade D" in api_spec
    assert "company-quality weakness" in api_spec
    assert "yfinance short-interest" in api_spec


def test_phase54_adr_manual_evidence_library_review_queue_contract_is_documented() -> None:
    manual_schema_props = _load_manual_evidence_schema()["properties"]
    dashboard_defs = _load_manual_evidence_dashboard_schema()["$defs"]
    dashboard_queue_schema = dashboard_defs.get("ManualEvidenceDashboardQueueItem") or dashboard_defs.get("queueItem")
    assert dashboard_queue_schema is not None
    dashboard_queue_props = dashboard_queue_schema["properties"]
    patch_props = ManualQualitativeEvidencePatch.model_json_schema()["properties"]
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    data_sources = _read("docs/DATA_SOURCES.md")
    framework = _read("docs/JANE_FRAMEWORK_MAPPING.md")
    frontend_types = _read("frontend/src/types.ts")
    evidence_library = _read("frontend/src/pages/EvidenceLibrary.tsx")

    adr_fields = [
        "adr_evidence_type",
        "document_title",
        "document_date",
        "filing_period",
        "local_market",
        "local_ticker",
        "adr_review_label",
        "adr_review_guidance",
        "affects_score",
        "not_investment_advice",
    ]
    for field in adr_fields:
        assert field in dashboard_queue_props
        assert field in frontend_types
        for text in [api_spec, readme, changelog, data_sources, framework]:
            assert field in text

    for field in ["adr_evidence_type", "document_title", "document_date", "filing_period", "quoted_text", "local_market", "local_ticker", "translation_note"]:
        assert field in manual_schema_props
        assert field in patch_props
        assert field in evidence_library

    for token in ["Phase 54", "source_date", "review queue", "without fetching URLs", "does not change scoring"]:
        assert token in api_spec or token in readme or token in changelog


def test_phase55_coverage_matrix_auto_evidence_expansion_contract_is_documented() -> None:
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    data_sources = _read("docs/DATA_SOURCES.md")
    framework = _read("docs/JANE_FRAMEWORK_MAPPING.md")
    frontend_types = _read("frontend/src/types.ts")

    for text in [api_spec, readme, changelog, data_sources, framework]:
        assert "Phase 55" in text
        assert "USE_LIVE_USPTO_PATENTS_DATA" in text
        assert "jane_theme_alignment" in text
        assert "institutional_support" in text
        assert "fund_support" in text
        assert "does not change final score" in text or "without changing final scoring" in text or "Preserved final score" in text

    for token in ["user_context", "filing_backed", "sec_13f", "financial_proxy_source"]:
        assert token in api_spec
        assert token in frontend_types


def test_phase57_macro_flow_signal_breakdown_contract_is_documented() -> None:
    schema = _load_schema()
    defs = schema["$defs"]
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    data_sources = _read("docs/DATA_SOURCES.md")
    framework = _read("docs/JANE_FRAMEWORK_MAPPING.md")
    frontend_types = _read("frontend/src/types.ts")
    stock_research = _read("frontend/src/pages/StockResearch.tsx")

    assert "macro_flow_signal_breakdown" in schema["properties"]
    assert "MacroFlowSignalBreakdown" in defs
    assert "MacroFlowSignalItem" in defs

    for text in [api_spec, readme, changelog, data_sources, framework, frontend_types, stock_research]:
        assert "macro_flow_signal_breakdown" in text
        assert "phase57_macro_flow_signal_breakdown_v1" in text

    for text in [api_spec, readme, changelog, data_sources, framework]:
        assert "Phase 57" in text
        assert "not a trading signal" in text
        assert "does not change final score" in text or "does not change final scoring" in text

    for token in ["macro_signals", "flow_signals", "final_score_unchanged", "not_investment_advice"]:
        assert token in api_spec
        assert token in frontend_types


def test_phase58_company_event_signal_breakdown_contract_is_documented() -> None:
    schema = _load_schema()
    defs = schema["$defs"]
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    data_sources = _read("docs/DATA_SOURCES.md")
    framework = _read("docs/JANE_FRAMEWORK_MAPPING.md")
    frontend_types = _read("frontend/src/types.ts")
    stock_research = _read("frontend/src/pages/StockResearch.tsx")

    assert "company_event_signal_breakdown" in schema["properties"]
    assert "CompanyEventSignalBreakdown" in defs
    assert "CompanyEventSignalItem" in defs

    for text in [api_spec, readme, changelog, data_sources, framework, frontend_types, stock_research]:
        assert "company_event_signal_breakdown" in text
        assert "phase58_company_event_signal_breakdown_v1" in text

    for text in [api_spec, readme, changelog, data_sources, framework]:
        assert "Phase 58" in text
        assert "lock-up" in text.lower()
        assert "not a trading signal" in text
        assert "does not change final score" in text or "does not change final scoring" in text

    for token in ["event_signals", "insider_summary", "institutional_summary", "options_summary", "lockup_summary", "final_score_unchanged", "not_investment_advice"]:
        assert token in api_spec
        assert token in frontend_types


def test_phase59_platform_business_quality_card_contract_is_documented() -> None:
    schema = _load_schema()
    defs = schema["$defs"]
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    data_sources = _read("docs/DATA_SOURCES.md")
    framework = _read("docs/JANE_FRAMEWORK_MAPPING.md")
    frontend_types = _read("frontend/src/types.ts")
    stock_research = _read("frontend/src/pages/StockResearch.tsx")

    assert "platform_business_quality_card" in schema["properties"]
    assert "PlatformBusinessQualityCard" in defs
    assert "PlatformBusinessQualityMetric" in defs

    for text in [api_spec, readme, changelog, data_sources, framework, frontend_types, stock_research]:
        assert "platform_business_quality_card" in text
        assert "phase59_platform_business_quality_card_v1" in text

    for text in [api_spec, readme, changelog, data_sources, framework]:
        assert "Phase 59" in text
        assert "GMV" in text
        assert "take rate" in text
        assert "does not change final score" in text or "does not change final scoring" in text

    for token in ["gmv_growth", "take_rate", "net_dollar_retention", "runway", "network_effect", "ltv_cac", "final_score_unchanged", "not_investment_advice"]:
        assert token in api_spec
        assert token in frontend_types


def test_phase52_adr_manual_evidence_contract_is_documented() -> None:
    schema = _load_schema()
    input_props = QualitativeEvidenceInput.model_json_schema()["properties"]
    assessment_props = schema["$defs"]["QualitativeEvidenceAssessmentItem"]["properties"]
    manual_evidence_props = ManualQualitativeEvidence.model_json_schema()["properties"]
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    framework = _read("docs/JANE_FRAMEWORK_MAPPING.md")
    frontend_types = _read("frontend/src/types.ts")

    fields = [
        "adr_evidence_type",
        "document_title",
        "document_date",
        "filing_period",
        "quoted_text",
        "local_market",
        "local_ticker",
        "translation_note",
    ]
    for field in fields:
        assert field in input_props
        assert field in assessment_props
        assert field in manual_evidence_props
        for text in [api_spec, readme, changelog, framework, frontend_types]:
            assert field in text

    for token in ["annual_report", "local_regulatory_filing", "filing_backed", "missing_source_date", "ADR Manual Evidence Intake"]:
        assert token in api_spec
        assert token in changelog
        if token not in {"missing_source_date", "ADR Manual Evidence Intake"}:
            assert token in frontend_types


def test_phase62_operations_diagnostics_contract_is_documented() -> None:
    committed = _normalize(json.loads(_read("schemas/operations_diagnostics.schema.json")))
    generated = _normalize(OperationsDiagnosticsResponse.model_json_schema())
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    data_sources = _read("docs/DATA_SOURCES.md")
    framework = _read("docs/JANE_FRAMEWORK_MAPPING.md")
    frontend_types = _read("frontend/src/types.ts")

    assert committed == generated
    for token in [
        "phase62_operations_diagnostics_v1",
        "operations/diagnostics",
        "Provider Health",
        "Coverage Readiness",
        "13F Runtime Universe",
        "api_key_values_returned",
        "C18",
        "C19",
    ]:
        assert token in api_spec
        assert token in readme
        assert token in changelog
        assert token in data_sources
        assert token in framework

    for token in ["OperationsDiagnostics", "api_key_values_returned", "CoverageReadinessRow", "ProviderDiagnosticRow"]:
        assert token in frontend_types


def test_phase64_evidence_gap_inbox_contract_is_documented() -> None:
    schema = _load_schema()
    top_level_props = schema["properties"]
    defs = schema["$defs"]
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    data_sources = _read("docs/DATA_SOURCES.md")
    framework = _read("docs/JANE_FRAMEWORK_MAPPING.md")
    product = _read("docs/PRODUCT_BASELINE.md")
    architecture = _read("docs/ARCHITECTURE_BASELINE.md")
    roadmap = _read("docs/ROADMAP.md")
    frontend_types = _read("frontend/src/types.ts")

    assert "evidence_gap_inbox" in top_level_props
    for definition in ["EvidenceGapInbox", "EvidenceGapInboxItem", "EvidenceGapInboxSummary"]:
        assert definition in defs
        assert definition in frontend_types

    for token in [
        "phase64_evidence_gap_inbox_v1",
        "manual_evidence_required",
        "source_setup_required",
        "provider_cache_refresh_required",
        "adr_or_foreign_filer_limitation",
    ]:
        for text in [api_spec, readme, changelog, data_sources, framework, product, architecture, roadmap, frontend_types]:
            assert token in text

    for token in ["affects_score=false", "final_score_unchanged=true"]:
        for text in [api_spec, readme, changelog, data_sources, framework, product, roadmap]:
            assert token in text



def test_phase69_manual_evidence_quality_loop_contract_is_documented() -> None:
    schema = _load_schema()
    defs = schema["$defs"]
    manual_schema_props = _load_manual_evidence_schema()["properties"]
    patch_props = ManualQualitativeEvidencePatch.model_json_schema()["properties"]
    evidence_item_props = defs["QualitativeEvidenceAssessmentItem"]["properties"]
    gap_item_props = defs["EvidenceGapInboxItem"]["properties"]
    coverage_item_props = defs["JaneCriterionCoverageItem"]["properties"]
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    data_sources = _read("docs/DATA_SOURCES.md")
    framework = _read("docs/JANE_FRAMEWORK_MAPPING.md")
    product = _read("docs/PRODUCT_BASELINE.md")
    architecture = _read("docs/ARCHITECTURE_BASELINE.md")
    roadmap = _read("docs/ROADMAP.md")
    frontend_types = _read("frontend/src/types.ts")
    stock_research = _read("frontend/src/pages/StockResearch.tsx")

    assert "ManualEvidenceResolution" in defs
    assert "manual_evidence_resolution" in gap_item_props
    assert "manual_evidence_resolution" in coverage_item_props

    quality_fields = [
        "linked_gap_id",
        "linked_criterion_id",
        "linked_submetrics",
        "resolution_status",
        "missing_required_fields",
        "review_state",
        "freshness_state",
        "evidence_quality_note",
        "affects_score",
        "final_score_unchanged",
        "not_investment_advice",
    ]
    for field in quality_fields:
        assert field in manual_schema_props
        assert field in evidence_item_props
        assert field in api_spec
        assert field in frontend_types

    for field in ["linked_gap_id", "linked_criterion_id", "linked_submetrics"]:
        assert field in patch_props

    for token in [
        "manual_evidence_resolution",
        "ManualEvidenceResolution",
        "resolved_for_review",
        "pending_review",
        "incomplete",
        "stale",
        "unresolved",
    ]:
        assert token in api_spec
        assert token in frontend_types

    for token in ["manual_evidence_resolution", "ManualEvidenceResolution", "Linked manual evidence", "Final score unchanged"]:
        assert token in stock_research

    for text in [api_spec, readme, changelog, data_sources, framework, product, architecture, roadmap]:
        assert "Phase 69" in text
        assert "Manual Evidence Quality Loop" in text
        assert "manual_evidence_resolution" in text
        assert "does not change" in text or "without changing" in text

    for token in ["affects_score=false", "final_score_unchanged=true", "not_investment_advice=true"]:
        assert token in api_spec
        assert token in readme
        assert token in product
        assert token in roadmap



def test_phase64a_roadmap_baseline_sync_is_documented() -> None:
    roadmap = _read("docs/ROADMAP.md")
    product = _read("docs/PRODUCT_BASELINE.md")
    architecture = _read("docs/ARCHITECTURE_BASELINE.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")

    for text in [roadmap, product, architecture, readme, changelog]:
        assert "Phase 64A" in text
        assert "Phase 61" in text
        assert "Phase 62" in text
        assert "Phase 63" in text
        assert "Phase 64 Evidence Gap Inbox" in text

    for token in [
        "current baseline",
        "Evidence Gap Inbox",
        "Manual Research Queue",
        "automatic future-theme discovery",
        "ranking",
        "Documentation-only",
    ]:
        assert token in roadmap or token in changelog or token in readme

    assert "does not change backend logic" in readme or "no backend logic" in changelog



def test_phase63_editable_13f_manager_universe_contract_is_documented() -> None:
    committed = _normalize(json.loads(_read("schemas/operations_13f_manager_universe_settings.schema.json")))
    generated = _normalize(SEC13FManagerUniverseSettings.model_json_schema())
    api_spec = _read("docs/API_SPEC.md")
    readme = _read("README.md")
    changelog = _read("docs/CHANGELOG.md")
    data_sources = _read("docs/DATA_SOURCES.md")
    framework = _read("docs/JANE_FRAMEWORK_MAPPING.md")
    frontend_types = _read("frontend/src/types.ts")

    assert committed == generated
    for token in [
        "phase63_13f_manager_universe_settings_v1",
        "operations/settings/13f-manager-universe",
        "local_settings",
        "startup_env",
        "bundled_starter_universe",
        "does not change scoring",
    ]:
        assert token in api_spec
        assert token in readme
        assert token in changelog
        assert token in data_sources
        assert token in framework

    for token in ["SEC13FManagerUniverseSettings", "phase63_13f_manager_universe_settings_v1", "local_settings"]:
        assert token in frontend_types



def test_phase_status_documents_are_at_phase30_or_newer() -> None:
    for path in ["README.md", "AGENTS.md", "docs/API_SPEC.md", "docs/CHANGELOG.md"]:
        text = _read(path)
        assert "Phase 30" in text, path

    readme = _read("README.md")
    agents = _read("AGENTS.md")
    changelog = _read("docs/CHANGELOG.md")
    assert "contract" in readme.lower()
    assert "contract" in agents.lower()
    assert "contract" in changelog.lower()


def test_live_analyze_stock_payload_has_documented_phase28_and_phase29_fields() -> None:
    response = client.post("/api/analyze-stock", json={"ticker": "NVDA", "market": "US"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["not_investment_advice"] is True
    assert "jane_criteria_coverage" in payload
    assert "validation_os_report" in payload
    assert payload["validation_os_report"]["not_investment_advice"] is True
    assert payload["jane_criteria_coverage"]["not_investment_advice"] is True
    assert detect_forbidden_language(payload) == []

def test_phase70_candidate_readiness_comparison_contract_is_documented() -> None:
    candidate_schema = json.loads((ROOT / "schemas/candidate_workspace.schema.json").read_text(encoding="utf-8"))
    readiness_schema = candidate_schema["$defs"]["CandidateReadinessComparisonResponse"]
    props = readiness_schema["properties"]
    api_spec = (ROOT / "docs/API_SPEC.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8")
    frontend_types = (ROOT / "frontend/src/types.ts").read_text(encoding="utf-8")

    for field in [
        "version",
        "summary",
        "items",
        "ranking_policy",
        "affects_score",
        "final_score_unchanged",
        "not_investment_advice",
    ]:
        assert field in props

    for token in [
        "phase70_candidate_readiness_comparison_v1",
        "CandidateReadinessComparison",
        "readiness_state",
        "evidence_completeness",
        "top_gap",
        "next_action",
        "not_ranked_by_score_or_recommendation",
        "affects_score=false",
        "final_score_unchanged=true",
        "not_investment_advice=true",
    ]:
        assert token in api_spec
        assert token in frontend_types or token.startswith("affects_score") or token.startswith("final_score") or token.startswith("not_investment")

    for doc in [readme, changelog, api_spec]:
        assert "Phase 70" in doc
        assert "Candidate Readiness Comparison" in doc
