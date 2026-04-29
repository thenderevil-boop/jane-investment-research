from __future__ import annotations

from copy import deepcopy
from typing import Any

MANAGER_MAP_LIMITATION = "Manager name is resolved from a bounded local map and may not be authoritative."


def normalize_cik(cik: str) -> str:
    digits = "".join(ch for ch in str(cik or "").strip() if ch.isdigit())
    return digits.zfill(10) if digits else ""


LOCAL_MANAGER_MAP: dict[str, dict[str, Any]] = {
    "0001067983": {
        "manager_cik": "0001067983",
        "manager_name": "Berkshire Hathaway Inc.",
        "aliases": ["BERKSHIRE HATHAWAY INC", "Berkshire Hathaway"],
        "confidence_source": "local_static_map",
        "limitations": [MANAGER_MAP_LIMITATION],
    },
    "0000102909": {
        "manager_cik": "0000102909",
        "manager_name": "Vanguard Group Inc.",
        "aliases": ["VANGUARD GROUP INC", "Vanguard Group"],
        "confidence_source": "local_static_map",
        "limitations": [MANAGER_MAP_LIMITATION],
    },
    "0001061768": {
        "manager_cik": "0001061768",
        "manager_name": "BlackRock Inc.",
        "aliases": ["BLACKROCK INC", "BlackRock"],
        "confidence_source": "local_static_map",
        "limitations": [MANAGER_MAP_LIMITATION],
    },
    "0001166559": {
        "manager_cik": "0001166559",
        "manager_name": "Bill & Melinda Gates Foundation Trust",
        "aliases": ["BILL & MELINDA GATES FOUNDATION TRUST", "Bill & Melinda Gates Foundation Trust"],
        "confidence_source": "local_static_map",
        "limitations": [MANAGER_MAP_LIMITATION],
    },
}


def get_manager_metadata_by_cik(cik: str) -> dict[str, Any]:
    normalized = normalize_cik(cik)
    metadata = LOCAL_MANAGER_MAP.get(normalized)
    if metadata:
        return deepcopy(metadata)
    return {
        "manager_cik": normalized,
        "manager_name": normalized or str(cik or "").strip(),
        "aliases": [],
        "confidence_source": "unmapped_local_static_map",
        "limitations": [],
    }


def resolve_manager_name(cik: str) -> str:
    return str(get_manager_metadata_by_cik(cik).get("manager_name") or normalize_cik(cik) or cik)
