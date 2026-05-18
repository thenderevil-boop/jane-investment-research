from __future__ import annotations

from backend.app import config
from backend.app.data.manager_map import get_manager_metadata_by_cik, resolve_manager_name
from backend.app.data_sources.sec_edgar_13f import LOCAL_MANAGER_CIKS
from backend.app.raw_store import _repository_impl as repository


EXPECTED_DEFAULT_13F_MANAGERS = [
    "0001067983",  # Berkshire Hathaway Inc.
    "0000102909",  # Vanguard Group Inc.
    "0001364742",  # BlackRock Inc.
    "0000093751",  # State Street Corp.
    "0001214717",  # Geode Capital Management LLC
]


def test_phase318_default_13f_manager_universe_is_diversified_and_ordered():
    assert config.DEFAULT_SEC_13F_TARGET_MANAGERS == EXPECTED_DEFAULT_13F_MANAGERS
    assert config.SEC_13F_TARGET_MANAGERS == ",".join(EXPECTED_DEFAULT_13F_MANAGERS)
    assert repository._target_13f_managers({}) == EXPECTED_DEFAULT_13F_MANAGERS


def test_phase318_explicit_empty_manager_config_preserves_fixture_fallback(monkeypatch):
    monkeypatch.setattr(config, "SEC_13F_TARGET_MANAGERS", "")
    assert repository._target_13f_managers({"institution_name": "fixture_manager"}) == ["fixture_manager"]
    assert repository._target_13f_managers({}) == ["mock_manager"]


def test_phase318_default_manager_metadata_and_aliases_are_locally_resolved():
    assert resolve_manager_name("0001364742") == "BlackRock Inc."
    assert resolve_manager_name("0000093751") == "State Street Corp."
    assert resolve_manager_name("0001214717") == "Geode Capital Management LLC"
    assert LOCAL_MANAGER_CIKS["blackrock inc"] == "0001364742"
    assert LOCAL_MANAGER_CIKS["state street"] == "0000093751"
    assert LOCAL_MANAGER_CIKS["geode capital"] == "0001214717"
    for cik in EXPECTED_DEFAULT_13F_MANAGERS:
        metadata = get_manager_metadata_by_cik(cik)
        assert metadata["confidence_source"] == "local_static_map"
        assert metadata["manager_name"]
