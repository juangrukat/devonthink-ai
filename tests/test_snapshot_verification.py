from __future__ import annotations

import json
from pathlib import Path

from app.tools import devonthink_link_tools as L
from app.tools import lifecycle
from app.tools.envelope import envelope_success
from app.tools.operations import reminder_ops
from app.tools import snapshot_index


def _write_snapshot(root: Path, name: str, adjacency: dict) -> Path:
    base = root / f"{name}.json"
    meta = root / f"{name}.meta.json"
    base.write_text(json.dumps(adjacency))
    meta.write_text(json.dumps({"started_at": "2026-05-01T00:00:00+00:00", "snapshot_generated_by": "devonthink-link-traverse-folder"}))
    return base


def test_compare_snapshots_includes_confidence_risk_and_verification(tmp_path) -> None:
    baseline = _write_snapshot(tmp_path, "baseline_20260501T000000", {"A": {"connectivity_shape": "isolated", "outgoing": []}})
    current = _write_snapshot(
        tmp_path,
        "current_20260501T000100",
        {"A": {"connectivity_shape": "hub", "outgoing": [{"target": "B", "reason_code": "explicit_item_link"}]}},
    )

    response = L.devonthink_link_compare_snapshots(str(baseline), str(current), plan_id="plan_1")

    assert response["ok"] is True
    assert response["data"]["confidence"]["score"] > 0
    assert response["data"]["risk"]["safety_class"] == "analysis_only"
    assert response["data"]["verification"]["checks"]
    assert response["data"]["plan_id"] == "plan_1"


def test_apply_with_capture_snapshot_records_index(monkeypatch, tmp_path) -> None:
    lifecycle.clear_plan_store()
    monkeypatch.setattr(snapshot_index, "INDEX_PATH", tmp_path / "snapshot_plan_index.json")
    monkeypatch.setattr(lifecycle, "record_snapshot", snapshot_index.record_snapshot)
    reminders = [{"id": "1", "due_date": "old", "alarm": "sound"}]

    def fake_list(record_uuid: str) -> dict:
        return envelope_success(data={"record_uuid": record_uuid, "reminders": [dict(item) for item in reminders]}, risk_class="read_only")

    def fake_apply(operation: dict) -> dict:
        reminders[0]["due_date"] = operation["due_date"]
        reminders[0]["alarm"] = operation["alarm"]
        return envelope_success(data=operation, risk_class="writes_metadata")

    def fake_traverse_folder(**kwargs):
        return {"ok": True, "data": {"snapshot_paths": {"adjacency_json": str(tmp_path / "post.json")}}}

    monkeypatch.setattr(reminder_ops, "list_reminders", fake_list)
    monkeypatch.setattr(reminder_ops, "apply_operation", fake_apply)
    monkeypatch.setattr(L, "devonthink_link_traverse_folder", fake_traverse_folder)

    plan = lifecycle.devonthink_plan_operation(
        {"kind": "Reminder.Update", "record_uuid": "REC", "reminder_id": "1", "due_date": "new", "alarm": "notification"}
    )
    applied = lifecycle.devonthink_apply_operation(
        plan["data"]["plan_id"],
        plan["data"]["confirmation"]["token"],
        policy={"capture_snapshot": True, "snapshot_folder_ref": "FOLDER", "snapshot_dir": str(tmp_path)},
    )

    assert applied["data"]["post_apply_snapshot_id"] == str(tmp_path / "post.json")
    assert snapshot_index.load_index()[plan["data"]["plan_id"]]["snapshot_id"] == str(tmp_path / "post.json")


def test_prune_protects_snapshot_referenced_by_plan(monkeypatch, tmp_path) -> None:
    base = _write_snapshot(tmp_path, "old_20200101T000000", {"A": {"connectivity_shape": "isolated"}})
    _write_snapshot(tmp_path, "new_20260501T000000", {"A": {"connectivity_shape": "hub"}})
    monkeypatch.setattr(L, "referenced_snapshots", lambda: {str(base): "plan_1"})

    response = L.devonthink_link_prune_snapshots(
        snapshot_dir=str(tmp_path),
        retention={"keep_last_n": 1, "keep_daily_for": 0, "keep_weekly_for": 0, "keep_monthly_for": 0},
        mode="report",
    )

    protected = response["data"]["protected"]
    assert any(item.get("reason") == "referenced_by_applied_plan" for item in protected)
