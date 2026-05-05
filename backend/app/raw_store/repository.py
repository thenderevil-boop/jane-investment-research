from __future__ import annotations

import sys

from backend.app.raw_store import _repository_impl as _repository_impl

# Phase 15.5 raw-store facade. New code should prefer focused modules such as
# market_cache, macro_cache, sec_cache, company_cache, snapshot, and
# price_reference_cache. The historical repository module remains an alias to
# the implementation module so existing imports and monkeypatches keep working.
_repository_impl.__doc__ = __doc__
sys.modules[__name__] = _repository_impl
