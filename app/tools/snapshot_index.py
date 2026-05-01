"""Small plan-to-snapshot audit index for lifecycle verification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INDEX_PATH = Path(__file__).resolve().parents[1] / "data" / "snapshot_plan_index.json"


def load_index(path: Path | None = None) -> dict[str, Any]:
    """Load the snapshot audit index."""
    target = path or INDEX_PATH
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_index(index: dict[str, Any], path: Path | None = None) -> None:
    """Persist the snapshot audit index."""
    target = path or INDEX_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def record_snapshot(plan_id: str, snapshot_id: str, *, path: Path | None = None) -> None:
    """Record that a plan produced or references a post-apply snapshot."""
    index = load_index(path)
    index[plan_id] = {
        "snapshot_id": snapshot_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    save_index(index, path)


def referenced_snapshots(*, path: Path | None = None) -> dict[str, str]:
    """Return snapshot_id -> plan_id mappings."""
    result = {}
    for plan_id, item in load_index(path).items():
        if isinstance(item, dict) and item.get("snapshot_id"):
            result[str(item["snapshot_id"])] = str(plan_id)
    return result
