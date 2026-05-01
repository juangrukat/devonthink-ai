from __future__ import annotations

import json
import os
from datetime import timedelta

from app.tools import devonthink_link_tools as L


def test_repair_apply_requires_plan_id(monkeypatch) -> None:
    monkeypatch.setattr(L, "_get_record", lambda ref: {"uuid": ref, "type": "markdown", "locked": False, "database_read_only": False})
    monkeypatch.setattr(L, "_get_record_text", lambda ref, max_chars=100000: "body")

    result = L.devonthink_link_repair_links("REC", mode="apply")

    assert result["ok"] is False
    assert result["error"]["code"] == "plan_id_required"


def test_repair_report_apply_with_valid_plan(monkeypatch) -> None:
    text = {"value": "See 5038E0B0-2134-4CDA-B443-6558CE283BCC"}
    monkeypatch.setattr(L, "_get_record", lambda ref: {"uuid": ref, "reference_url": f"x-devonthink-item://{ref}", "type": "markdown", "locked": False, "database_read_only": False})
    monkeypatch.setattr(L, "_get_record_text", lambda ref, max_chars=100000: text["value"])
    monkeypatch.setattr(L, "_assert_content_writable", lambda rec, operation: None)
    monkeypatch.setattr(L, "_set_plain_text", lambda ref, new_text: text.update(value=new_text))

    report = L.devonthink_link_repair_links("REC", mode="report")
    applied = L.devonthink_link_repair_links("REC", mode="apply", plan_id=report["data"]["plan_id"])

    assert applied["ok"] is True
    assert applied["data"]["changed"] is True


def test_repair_apply_rejects_stale_plan(monkeypatch) -> None:
    text = {"value": "See 5038E0B0-2134-4CDA-B443-6558CE283BCC"}
    monkeypatch.setattr(L, "_get_record", lambda ref: {"uuid": ref, "reference_url": f"x-devonthink-item://{ref}", "type": "markdown", "locked": False, "database_read_only": False})
    monkeypatch.setattr(L, "_get_record_text", lambda ref, max_chars=100000: text["value"])

    report = L.devonthink_link_repair_links("REC", mode="report")
    text["value"] = "changed"
    applied = L.devonthink_link_repair_links("REC", mode="apply", plan_id=report["data"]["plan_id"])

    assert applied["ok"] is False
    assert applied["error"]["code"] == "stale_plan"


def test_apply_rejects_expired_plan(monkeypatch) -> None:
    monkeypatch.setattr(L, "_get_record", lambda ref: {"uuid": ref, "type": "markdown", "locked": False, "database_read_only": False})
    monkeypatch.setattr(L, "_get_record_text", lambda ref, max_chars=100000: "body")
    report = L.devonthink_link_repair_links("REC", mode="report")
    L.LINK_PLAN_STORE[report["data"]["plan_id"]]["expires_at"] = L.datetime.now(L.timezone.utc) - timedelta(seconds=1)

    applied = L.devonthink_link_repair_links("REC", mode="apply", plan_id=report["data"]["plan_id"])

    assert applied["ok"] is False
    assert applied["error"]["code"] == "plan_expired"


def test_report_actionable_rows_shape_stable(monkeypatch) -> None:
    monkeypatch.setattr(L, "_get_record", lambda ref: {"uuid": ref, "type": "markdown", "locked": False, "database_read_only": False})
    monkeypatch.setattr(L, "_get_record_text", lambda ref, max_chars=100000: "body")

    report = L.devonthink_link_repair_links("REC", mode="report")

    assert set(report["data"]["actionable_rows"]) == {"unresolved_item_links", "unresolved_wikilinks", "tombstone_uuids", "raw_uuids"}


def test_maintenance_report_apply_with_no_drift_succeeds(monkeypatch, tmp_path) -> None:
    L.clear_link_plan_store()
    folder_uuid = "11111111-1111-4111-8111-111111111111"

    baseline = tmp_path / "maintenance_11111111_20260501T120000.json"
    baseline_meta = tmp_path / "maintenance_11111111_20260501T120000.meta.json"
    report_snapshot = tmp_path / "maintenance_11111111_20260501T120100.json"
    report_meta = tmp_path / "maintenance_11111111_20260501T120100.meta.json"
    apply_snapshot = tmp_path / "maintenance_11111111_20260501T120200.json"
    apply_meta = tmp_path / "maintenance_11111111_20260501T120200.meta.json"

    old_adj = {
        "REC": {
            "meta": {"uuid": "REC", "name": "Deleted note"},
            "connectivity_shape": "isolated",
            "incoming": [],
            "outgoing": [],
            "wikilinks": [],
        }
    }
    current_adj = {}

    baseline.write_text(json.dumps(old_adj))
    baseline_meta.write_text(json.dumps({"folder_uuid": folder_uuid, "started_at": "2026-05-01T12:00:00+00:00"}))
    report_snapshot.write_text(json.dumps(current_adj))
    report_meta.write_text(json.dumps({"folder_uuid": folder_uuid, "started_at": "2026-05-01T12:01:00+00:00"}))

    # Make auto-discovery choose baseline -> report during report mode.
    os.utime(baseline, (1, 1))
    os.utime(baseline_meta, (1, 1))
    os.utime(report_snapshot, (2, 2))
    os.utime(report_meta, (2, 2))
    traversals = iter(
        [
            {
                "snapshot_paths": {"adjacency_json": str(report_snapshot), "meta_json": str(report_meta)},
                "adjacency_map": current_adj,
            },
            {
                "snapshot_paths": {"adjacency_json": str(apply_snapshot), "meta_json": str(apply_meta)},
                "adjacency_map": current_adj,
                "write_apply_snapshot": True,
            },
        ]
    )

    def fake_traverse_folder(**kwargs):
        data = next(traversals)
        if data.get("write_apply_snapshot"):
            apply_snapshot.write_text(json.dumps(current_adj))
            apply_meta.write_text(json.dumps({"folder_uuid": folder_uuid, "started_at": "2026-05-01T12:02:00+00:00"}))
            os.utime(apply_snapshot, (3, 3))
            os.utime(apply_meta, (3, 3))
        return {
            "ok": True,
            "data": {
                **data,
                "shape_distribution": {},
                "traversal_meta": {
                    "folder_uuid": folder_uuid,
                    "records_processed": 0,
                    "records_skipped": 0,
                    "total_records": 0,
                },
            },
            "observability": {"warnings": [], "stats": {}},
        }

    monkeypatch.setattr(L, "_get_record", lambda ref: {"uuid": folder_uuid, "name": "Folder", "type": "group"})
    monkeypatch.setattr(L, "devonthink_link_traverse_folder", fake_traverse_folder)
    monkeypatch.setattr(L, "devonthink_link_prune_snapshots", lambda **kwargs: {"ok": True, "data": {"mode": "report"}})

    report = L.devonthink_link_maintenance_pass(folder_uuid, mode="report", snapshot_dir=str(tmp_path))
    applied = L.devonthink_link_maintenance_pass(
        folder_uuid,
        mode="apply",
        snapshot_dir=str(tmp_path),
        plan_id=report["data"]["plan_id"],
    )

    assert report["ok"] is True
    assert len(report["data"]["actionable_rows"]) == 1
    assert applied["ok"] is True
