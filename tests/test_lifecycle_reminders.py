from __future__ import annotations

from datetime import timedelta

import pytest

from app.tools import lifecycle
from app.tools.envelope import envelope_success
from app.tools.operations import reminder_ops

RECORD_UUID = "5038E0B0-2134-4CDA-B443-6558CE283BCC"


@pytest.fixture(autouse=True)
def reset_plan_store() -> None:
    lifecycle.clear_plan_store()


def _install_fake_reminders(monkeypatch, reminders: list[dict[str, str]]) -> None:
    def fake_list(record_uuid: str) -> dict:
        assert record_uuid == RECORD_UUID
        return envelope_success(data={"record_uuid": record_uuid, "reminders": [dict(item) for item in reminders]}, risk_class="read_only")

    def fake_apply(operation: dict) -> dict:
        if operation["kind"] == "Reminder.Delete":
            reminders[:] = [item for item in reminders if item["id"] != operation["reminder_id"]]
            return envelope_success(data={"record_uuid": RECORD_UUID, "reminder_id": operation["reminder_id"]}, risk_class="destructive")
        for item in reminders:
            if item["id"] == operation["reminder_id"]:
                item["due_date"] = operation["due_date"]
                item["alarm"] = operation["alarm"]
        return envelope_success(data=operation, risk_class="writes_metadata")

    monkeypatch.setattr(reminder_ops, "list_reminders", fake_list)
    monkeypatch.setattr(reminder_ops, "apply_operation", fake_apply)


def test_update_plan_apply_verify_happy_path(monkeypatch) -> None:
    reminders = [{"id": "1", "due_date": "old", "alarm": "sound"}]
    _install_fake_reminders(monkeypatch, reminders)

    plan = lifecycle.devonthink_plan_operation(
        {
            "kind": "Reminder.Update",
            "record_uuid": RECORD_UUID,
            "reminder_id": "1",
            "due_date": "2026-05-01T09:00:00",
            "alarm": "notification",
        }
    )
    assert plan["data"]["needs_confirmation"] is True

    applied = lifecycle.devonthink_apply_operation(
        plan["data"]["plan_id"],
        plan["data"]["confirmation"]["token"],
    )

    assert applied["ok"] is True
    assert applied["data"]["status"] == "completed"
    assert all(check["passed"] for check in applied["data"]["verification"]["checks"])


def test_delete_plan_apply_verify_happy_path(monkeypatch) -> None:
    reminders = [{"id": "1", "due_date": "old", "alarm": "sound"}]
    _install_fake_reminders(monkeypatch, reminders)

    plan = lifecycle.devonthink_plan_operation(
        {"kind": "Reminder.Delete", "record_uuid": RECORD_UUID, "reminder_id": "1"}
    )
    applied = lifecycle.devonthink_apply_operation(
        plan["data"]["plan_id"],
        plan["data"]["confirmation"]["token"],
    )

    assert applied["ok"] is True
    assert applied["data"]["status"] == "completed"
    assert applied["data"]["verification"]["checks"][0]["name"] == "reminder_absent"
    assert applied["data"]["verification"]["checks"][0]["passed"] is True


def test_apply_rejects_stale_plan(monkeypatch) -> None:
    reminders = [{"id": "1", "due_date": "old", "alarm": "sound"}]
    _install_fake_reminders(monkeypatch, reminders)
    plan = lifecycle.devonthink_plan_operation(
        {
            "kind": "Reminder.Update",
            "record_uuid": RECORD_UUID,
            "reminder_id": "1",
            "due_date": "new",
            "alarm": "notification",
        }
    )

    reminders[0]["alarm"] = "speech"
    applied = lifecycle.devonthink_apply_operation(plan["data"]["plan_id"], plan["data"]["confirmation"]["token"])

    assert applied["ok"] is False
    assert applied["error"]["code"] == "stale_plan"


def test_apply_rejects_expired_confirmation(monkeypatch) -> None:
    reminders = [{"id": "1", "due_date": "old", "alarm": "sound"}]
    _install_fake_reminders(monkeypatch, reminders)
    plan = lifecycle.devonthink_plan_operation(
        {"kind": "Reminder.Delete", "record_uuid": RECORD_UUID, "reminder_id": "1"}
    )
    lifecycle.PLAN_STORE[plan["data"]["plan_id"]]["expires_at"] = lifecycle._utc_now() - timedelta(seconds=1)

    applied = lifecycle.devonthink_apply_operation(plan["data"]["plan_id"], plan["data"]["confirmation"]["token"])

    assert applied["ok"] is False
    assert applied["error"]["code"] == "confirmation_expired"


def test_apply_rejects_replayed_plan(monkeypatch) -> None:
    reminders = [{"id": "1", "due_date": "old", "alarm": "sound"}]
    _install_fake_reminders(monkeypatch, reminders)
    plan = lifecycle.devonthink_plan_operation(
        {"kind": "Reminder.Delete", "record_uuid": RECORD_UUID, "reminder_id": "1"}
    )
    token = plan["data"]["confirmation"]["token"]

    first = lifecycle.devonthink_apply_operation(plan["data"]["plan_id"], token)
    second = lifecycle.devonthink_apply_operation(plan["data"]["plan_id"], token)

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["error"]["code"] == "plan_already_applied"
