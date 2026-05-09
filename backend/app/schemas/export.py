from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.schemas.common import DataSourceStatus
from backend.app.schemas.stock_analysis import AnalyzeStockRequest


ExportFormat = Literal["json", "markdown"]


def new_export_id() -> str:
    return f"export_{uuid4().hex}"


def new_backup_id() -> str:
    return f"backup_{uuid4().hex}"


class AnalyzeStockExportRequest(AnalyzeStockRequest):
    format: ExportFormat = "json"
    include_raw_evidence: bool = False
    include_manual_evidence: bool = True
    include_candidate_metadata: bool = False
    redact_sensitive_fields: bool = True


class AnalyzeStockExportResponse(BaseModel):
    export_id: str = Field(default_factory=new_export_id)
    generated_at: str
    ticker: str
    format: ExportFormat
    filename: str
    content_type: str
    report: dict[str, Any] | str
    source_status: DataSourceStatus
    not_investment_advice: bool = True


class LocalBackupMetadata(BaseModel):
    backup_id: str = Field(default_factory=new_backup_id)
    generated_at: str
    schema_version: Literal["phase25_local_backup_v1"] = "phase25_local_backup_v1"
    not_investment_advice: bool = True
    limitations: list[str] = Field(default_factory=lambda: [
        "Local backup contains user-provided workflow metadata and evidence records.",
        "Manual evidence is not independently verified.",
        "Candidate status is not investment advice.",
        "Import or restore is not implemented in Phase 25.",
    ])


class LocalBackupExportResponse(BaseModel):
    backup_metadata: LocalBackupMetadata
    manual_evidence: dict[str, Any] | None = None
    candidate_workspace: dict[str, Any] | None = None
    source_status: DataSourceStatus
    not_investment_advice: bool = True
