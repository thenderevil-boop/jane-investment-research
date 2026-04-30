from __future__ import annotations

import argparse
import json
import sys

from backend.app.data_sources.live_macro_fred import FredFetchError, search_fred_series


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search FRED series metadata without printing secrets.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        results = search_fred_series(args.query, limit=args.limit)
        print(json.dumps({"query": args.query, "results": results}, indent=2, sort_keys=True))
        return 0
    except FredFetchError:
        print(json.dumps({"query": args.query, "results": [], "sanitized_error": "FRED series search failed."}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
