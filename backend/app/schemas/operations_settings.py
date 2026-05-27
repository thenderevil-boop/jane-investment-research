from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app import config

ManagerUniverseSource = Literal["local_settings", "startup_env", "bundled_starter_universe"]


def normalize_cik(value: str) -> str:
    raw = "".join(ch for ch in str(value).strip() if ch.isdigit())
    if not raw or len(raw) > 10:
        raise ValueError("manager CIK must contain 1-10 digits")
    return raw.zfill(10)


class SEC13FManagerUniverseUpdate(BaseModel):
    manager_ciks: list[str] = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("manager_ciks")
    @classmethod
    def validate_manager_ciks(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            cik = normalize_cik(item)
            if cik not in normalized:
                normalized.append(cik)
        if not normalized:
            raise ValueError("at least one manager CIK is required")
        return normalized


class SEC13FManagerUniverseSettings(BaseModel):
    version: Literal["phase63_13f_manager_universe_settings_v1"] = "phase63_13f_manager_universe_settings_v1"
    source: ManagerUniverseSource
    effective_manager_ciks: list[str]
    local_manager_ciks: list[str] = Field(default_factory=list)
    startup_env_manager_ciks: list[str] = Field(default_factory=list)
    bundled_starter_manager_ciks: list[str] = Field(default_factory=lambda: list(config.DEFAULT_SEC_13F_TARGET_MANAGERS))
    bundled_starter_count: int = Field(default_factory=lambda: len(config.DEFAULT_SEC_13F_TARGET_MANAGERS))
    editable: bool = True
    precedence: list[ManagerUniverseSource] = Field(default_factory=lambda: ["local_settings", "startup_env", "bundled_starter_universe"])
    note: str | None = None
    warnings: list[str] = Field(default_factory=list)
    not_investment_advice: bool = True
