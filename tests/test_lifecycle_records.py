from __future__ import annotations

import pytest

from app.tools import lifecycle
from app.tools.envelope import envelope_success
from app.tools.operations import record_ops


@pytest.fixture(autouse=True)
def reset_plan_store() -> None:
    lifecycle.clear_plan_store()


def _install_fake_records(monkeypatch, records: dict[str, dict]) -> None:
    def fake_snapshot(record_uuid: str):
        record = records.get(record_uuid)
        if record is None:
            return None, {"ok": False, "error": "not found"}
        return dict(record), envelope_success(data=dict(record), risk_class="read_only")

    def fake_snapshot_records(record_uuids: list[str]):
        return [dict(records[value]) for value in record_uuids], None

    def fake_validate(destination_group_uuid: str):
        record = records.get(destination_group_uuid)
        if not record or record.get("record_type") != "group":
            return None, {"ok": False, "error": "Destination group not found."}
        return dict(record), None

    def fake_apply(operation: dict):
        if operation["kind"] == "Record.MetadataUpdate":
            for uuid in operation["record_uuids"]:
                if "tags" in operation:
                    records[uuid]["tags"] = list(operation["tags"])
                if "comment" in operation:
                    records[uuid]["comment"] = operation["comment"]
                if "label" in operation:
                    records[uuid]["label"] = operation["label"]
                if "rating" in operation:
                    records[uuid]["rating"] = operation["rating"]
            return envelope_success(data={"updated": len(operation["record_uuids"])}, risk_class="writes_metadata")
        records[operation["record_uuid"]]["parent_uuid"] = operation["destination_group_uuid"]
        records[operation["record_uuid"]]["location"] = records[operation["destination_group_uuid"]]["location"]
        return envelope_success(data=dict(records[operation["record_uuid"]]), risk_class="moves_records")

    monkeypatch.setattr(record_ops, "snapshot_record", fake_snapshot)
    monkeypatch.setattr(record_ops, "snapshot_records", fake_snapshot_records)
    monkeypatch.setattr(record_ops, "validate_destination", fake_validate)
    monkeypatch.setattr(record_ops, "apply_operation", fake_apply)


def test_metadata_update_plan_apply_verify_single_record(monkeypatch) -> None:
    records = {"REC": {"uuid": "REC", "tags": [], "comment": "", "label": 0, "rating": 0}}
    _install_fake_records(monkeypatch, records)

    plan = lifecycle.devonthink_plan_operation(
        {"kind": "Record.MetadataUpdate", "record_uuids": ["REC"], "tags": ["todo"], "comment": "review", "label": 4}
    )
    applied = lifecycle.devonthink_apply_operation(plan["data"]["plan_id"], plan["data"]["confirmation"]["token"])

    assert applied["ok"] is True
    assert applied["data"]["verification"]["status"] == "verified"


def test_metadata_update_batch_rejects_stale_plan_with_drifted_uuid(monkeypatch) -> None:
    records = {
        "A": {"uuid": "A", "tags": [], "comment": "", "label": 0},
        "B": {"uuid": "B", "tags": [], "comment": "", "label": 0},
        "C": {"uuid": "C", "tags": [], "comment": "", "label": 0},
    }
    _install_fake_records(monkeypatch, records)
    plan = lifecycle.devonthink_plan_operation(
        {"kind": "Record.MetadataUpdate", "record_uuids": ["A", "B", "C"], "tags": ["done"]}
    )

    records["B"]["comment"] = "drifted"
    applied = lifecycle.devonthink_apply_operation(plan["data"]["plan_id"], plan["data"]["confirmation"]["token"])

    assert applied["ok"] is False
    assert applied["error"]["code"] == "stale_plan"
    assert applied["observability"]["warnings"][0]["drifted_uuids"] == ["B"]


def test_move_plan_rejects_missing_destination(monkeypatch) -> None:
    records = {"REC": {"uuid": "REC", "record_type": "txt", "location": "/Inbox", "parent_uuid": "OLD"}}
    _install_fake_records(monkeypatch, records)

    plan = lifecycle.devonthink_plan_operation(
        {"kind": "Record.Move", "record_uuid": "REC", "destination_group_uuid": "MISSING"}
    )

    assert plan["ok"] is False
    assert plan["error"]["code"] == "destination_not_found"


def test_move_apply_verify_confirms_location_and_parent(monkeypatch) -> None:
    records = {
        "REC": {"uuid": "REC", "record_type": "txt", "location": "/Inbox", "parent_uuid": "OLD"},
        "DEST": {"uuid": "DEST", "record_type": "group", "location": "/Archive"},
    }
    _install_fake_records(monkeypatch, records)

    plan = lifecycle.devonthink_plan_operation(
        {"kind": "Record.Move", "record_uuid": "REC", "destination_group_uuid": "DEST"}
    )
    applied = lifecycle.devonthink_apply_operation(plan["data"]["plan_id"], plan["data"]["confirmation"]["token"])

    assert applied["ok"] is True
    assert all(check["passed"] for check in applied["data"]["verification"]["checks"])
