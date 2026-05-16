from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.schemas.daily_report import DailyResearchReport
from backend.app.schemas.stock_analysis import AnalyzeStockResponse


def write_schema(path: str, schema: dict) -> None:
    Path(path).write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    write_schema("schemas/analyze_stock.schema.json", AnalyzeStockResponse.model_json_schema())
    write_schema("schemas/daily_report.schema.json", DailyResearchReport.model_json_schema())


if __name__ == "__main__":
    main()
