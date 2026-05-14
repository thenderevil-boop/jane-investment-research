from __future__ import annotations

import importlib


def test_runtime_dependency_imports_succeed_without_live_api_calls():
    for module_name in ["httpx", "pandas", "yfinance"]:
        assert importlib.import_module(module_name) is not None
