from __future__ import annotations

import sys

from backend.app.pipelines import research_pipeline as _research_pipeline

# Phase 15.5 compatibility shim. The main daily research pipeline now lives in
# research_pipeline.py; this module remains import-compatible for older tests
# and callers, including monkeypatches against backend.app.pipelines.mock_pipeline.
sys.modules[__name__] = _research_pipeline
