from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app import config
from backend.app.schemas.candidate_workspace import CandidateResearchItem, CandidateResearchItemCreate, CandidateResearchItemPatch, utc_now_iso


class CandidateWorkspaceStoreError(RuntimeError):
    pass


def _store_dir() -> Path:
    path = config.CANDIDATE_WORKSPACE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _store_path() -> Path:
    return _store_dir() / "candidates.json"


def _read_rows() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CandidateWorkspaceStoreError("Candidate workspace JSON store is invalid.") from exc
    except OSError as exc:
        raise CandidateWorkspaceStoreError("Candidate workspace JSON store could not be read.") from exc
    rows = payload.get("candidates") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise CandidateWorkspaceStoreError("Candidate workspace JSON store has an invalid shape.")
    return [item for item in rows if isinstance(item, dict)]


def _write_rows(rows: list[dict[str, Any]]) -> None:
    path = _store_path()
    tmp = path.with_suffix(".tmp")
    payload = {"candidates": rows}
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    try:
        tmp.replace(path)
    except PermissionError:
        path.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            tmp.unlink()
        except OSError:
            pass


def list_candidate_items(include_archived: bool = False) -> list[dict[str, Any]]:
    rows = _read_rows()
    if not include_archived:
        rows = [item for item in rows if item.get("status") != "archived"]
    return rows


def get_candidate_item(candidate_id: str) -> dict[str, Any] | None:
    return next((item for item in _read_rows() if item.get("candidate_id") == candidate_id), None)


def create_candidate_item(item: CandidateResearchItemCreate | CandidateResearchItem | dict[str, Any]) -> dict[str, Any]:
    raw = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
    model = item if isinstance(item, CandidateResearchItem) else CandidateResearchItem.model_validate(raw)
    rows = _read_rows()
    rows = [row for row in rows if row.get("candidate_id") != model.candidate_id]
    rows.append(model.model_dump(mode="json"))
    _write_rows(rows)
    return model.model_dump(mode="json")


def update_candidate_item(candidate_id: str, patch: CandidateResearchItemPatch | dict[str, Any]) -> dict[str, Any] | None:
    rows = _read_rows()
    existing = next((item for item in rows if item.get("candidate_id") == candidate_id), None)
    if not existing:
        return None
    patch_model = patch if isinstance(patch, CandidateResearchItemPatch) else CandidateResearchItemPatch.model_validate(patch)
    updates = patch_model.model_dump(mode="json", exclude_none=True)
    updated = {
        **existing,
        **updates,
        "candidate_id": existing["candidate_id"],
        "ticker": existing["ticker"],
        "market": existing.get("market", "US"),
        "created_at": existing.get("created_at") or utc_now_iso(),
        "updated_at": utc_now_iso(),
        "not_investment_advice": True,
    }
    model = CandidateResearchItem.model_validate(updated)
    next_rows = [model.model_dump(mode="json") if item.get("candidate_id") == candidate_id else item for item in rows]
    _write_rows(next_rows)
    return model.model_dump(mode="json")


def archive_candidate_item(candidate_id: str) -> dict[str, Any] | None:
    return update_candidate_item(candidate_id, {"status": "archived"})
