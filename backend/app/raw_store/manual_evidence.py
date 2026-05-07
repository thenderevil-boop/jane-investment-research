from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app import config
from backend.app.schemas.manual_evidence import (
    ManualQualitativeEvidence,
    ManualQualitativeEvidenceCreate,
    ManualQualitativeEvidencePatch,
    utc_now_iso,
)


def _store_dir() -> Path:
    path = config.MANUAL_EVIDENCE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ticker_key(ticker: str) -> str:
    return "".join(ch for ch in ticker.strip().upper() if ch.isalnum())[:10] or "UNKNOWN"


def _path_for_ticker(ticker: str) -> Path:
    return _store_dir() / f"{_ticker_key(ticker)}.json"


def _read_ticker_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("evidence"), list):
        return [item for item in payload["evidence"] if isinstance(item, dict)]
    return []


def _write_ticker_file(ticker: str, rows: list[dict[str, Any]]) -> None:
    path = _path_for_ticker(ticker)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
    try:
        tmp.replace(path)
    except PermissionError:
        path.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            tmp.unlink()
        except OSError:
            pass


def list_manual_evidence(ticker: str | None = None) -> list[dict[str, Any]]:
    if ticker:
        return _read_ticker_file(_path_for_ticker(ticker))
    rows: list[dict[str, Any]] = []
    for path in sorted(_store_dir().glob("*.json")):
        rows.extend(_read_ticker_file(path))
    return rows


def get_manual_evidence(evidence_id: str) -> dict[str, Any] | None:
    for item in list_manual_evidence():
        if item.get("evidence_id") == evidence_id:
            return item
    return None


def create_manual_evidence(evidence: ManualQualitativeEvidenceCreate | ManualQualitativeEvidence | dict[str, Any]) -> dict[str, Any]:
    model = evidence if isinstance(evidence, ManualQualitativeEvidence) else ManualQualitativeEvidence.model_validate(evidence.model_dump(mode="json") if hasattr(evidence, "model_dump") else evidence)
    row = model.model_dump(mode="json")
    rows = list_manual_evidence(model.ticker)
    rows = [item for item in rows if item.get("evidence_id") != model.evidence_id]
    rows.append(row)
    _write_ticker_file(model.ticker, rows)
    return row


def update_manual_evidence(evidence_id: str, patch: ManualQualitativeEvidencePatch | dict[str, Any]) -> dict[str, Any] | None:
    existing = get_manual_evidence(evidence_id)
    if not existing:
        return None
    patch_model = patch if isinstance(patch, ManualQualitativeEvidencePatch) else ManualQualitativeEvidencePatch.model_validate(patch)
    updates = patch_model.model_dump(mode="json", exclude_none=True)
    updated = {
        **existing,
        **updates,
        "evidence_id": existing["evidence_id"],
        "ticker": existing["ticker"],
        "criterion": existing["criterion"],
        "evidence_type": existing["evidence_type"],
        "user_provided": True,
        "created_at": existing.get("created_at") or utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    model = ManualQualitativeEvidence.model_validate(updated)
    rows = list_manual_evidence(model.ticker)
    rows = [model.model_dump(mode="json") if item.get("evidence_id") == evidence_id else item for item in rows]
    _write_ticker_file(model.ticker, rows)
    return model.model_dump(mode="json")


def delete_manual_evidence(evidence_id: str) -> dict[str, Any] | None:
    return update_manual_evidence(evidence_id, {"review_status": "archived"})


def load_manual_evidence_for_ticker(ticker: str) -> list[dict[str, Any]]:
    return list_manual_evidence(ticker)
