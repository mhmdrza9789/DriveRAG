from __future__ import annotations

import json
from pathlib import Path

from app.config import PROJECT_ROOT

PROCESSED_ROOT = PROJECT_ROOT / "data" / "processed"


def save_processed_locally(
    processed_data: dict, source_type: str, filename: str
) -> Path:
    safe_name = Path(filename.replace("\\", "/")).name
    safe_source_type = Path(source_type.replace("\\", "/")).name

    output_dir = PROCESSED_ROOT / safe_source_type
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{safe_name}.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=2)

    return output_path
