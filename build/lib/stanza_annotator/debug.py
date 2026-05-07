from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def write_debug_file(
    *,
    debug_dir: Path,
    annotated_document: BaseModel,
    metadata: dict[str, Any],
    raw_document: dict[str, Any] | None = None,
) -> Path:
    debug_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = debug_dir / f"annotation-{stamp}.json"

    payload: dict[str, Any] = {
        "metadata": metadata,
        "annotated_document": annotated_document.model_dump(mode="json"),
    }
    if raw_document is not None:
        payload["raw_document"] = raw_document

    path.write_text(_to_json(payload), encoding="utf-8")
    return path


def _to_json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
