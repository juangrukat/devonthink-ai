"""Reminder operation handlers for plan/apply/verify lifecycle tools."""

from __future__ import annotations

from typing import Any

import app.tools.devonthink_reminder_tools as reminder_tools

SUPPORTED_REMINDER_KINDS = {"Reminder.Update", "Reminder.Delete"}


def normalize_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a reminder lifecycle operation."""
    kind = operation.get("kind")
    if kind not in SUPPORTED_REMINDER_KINDS:
        raise ValueError("operation.kind must be one of: Reminder.Update, Reminder.Delete")
    record_uuid = str(operation.get("record_uuid", "")).strip()
    reminder_id = str(operation.get("reminder_id", "")).strip()
    if not record_uuid:
        raise ValueError("operation.record_uuid is required")
    if not reminder_id:
        raise ValueError("operation.reminder_id is required")
    normalized = {"kind": kind, "record_uuid": record_uuid, "reminder_id": reminder_id}
    if kind == "Reminder.Update":
        due_date = str(operation.get("due_date", "")).strip()
        alarm = str(operation.get("alarm", "notification")).strip().lower()
        if not due_date:
            raise ValueError("operation.due_date is required for Reminder.Update")
        if alarm not in reminder_tools.VALID_ALARMS:
            allowed = ", ".join(sorted(reminder_tools.VALID_ALARMS))
            raise ValueError(f"operation.alarm must be one of: {allowed}")
        normalized.update({"due_date": due_date, "alarm": alarm})
    return normalized


def risk_class_for(operation: dict[str, Any]) -> str:
    """Return the safety class for a reminder operation."""
    if operation["kind"] == "Reminder.Delete":
        return "destructive"
    return "writes_metadata"


def list_reminders(record_uuid: str) -> dict[str, Any]:
    """List reminders through the low-level reminder tool."""
    return reminder_tools.devonthink_list_reminders(record_uuid)


def find_reminder(record_uuid: str, reminder_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return a reminder row plus the low-level list response."""
    response = list_reminders(record_uuid)
    if response.get("ok") is not True:
        return None, response
    for reminder in response["data"]["reminders"]:
        if reminder.get("id") == reminder_id:
            return reminder, response
    return None, response


def planned_after(operation: dict[str, Any], before: dict[str, Any]) -> dict[str, Any] | None:
    """Compute the expected post-apply reminder state."""
    if operation["kind"] == "Reminder.Delete":
        return None
    after = dict(before)
    after["due_date"] = operation["due_date"]
    after["alarm"] = operation["alarm"]
    return after


def apply_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """Apply a normalized reminder operation using the low-level reminder tools."""
    if operation["kind"] == "Reminder.Delete":
        return reminder_tools.devonthink_delete_reminder(operation["record_uuid"], operation["reminder_id"])
    return reminder_tools.devonthink_update_reminder(
        operation["record_uuid"],
        operation["reminder_id"],
        operation["due_date"],
        operation["alarm"],
    )


def verify_operation(operation: dict[str, Any], after: dict[str, Any] | None) -> dict[str, Any]:
    """Verify current reminder state against an operation's expected state."""
    current, response = find_reminder(operation["record_uuid"], operation["reminder_id"])
    if response and response.get("ok") is not True:
        return {
            "status": "failed",
            "checks": [
                {
                    "name": "reminder_state_readable",
                    "passed": False,
                    "details": response.get("error", {}).get("message", "Could not list reminders."),
                }
            ],
        }
    if operation["kind"] == "Reminder.Delete":
        absent = current is None
        return {
            "status": "verified" if absent else "failed",
            "checks": [{"name": "reminder_absent", "passed": absent, "details": "Reminder is absent after delete."}],
        }
    checks = [
        {
            "name": "due_date_matches",
            "passed": bool(current and after and current.get("due_date") == after.get("due_date")),
            "details": "Reminder due date matches planned value.",
        },
        {
            "name": "alarm_matches",
            "passed": bool(current and after and current.get("alarm") == after.get("alarm")),
            "details": "Reminder alarm matches planned value.",
        },
    ]
    return {"status": "verified" if all(check["passed"] for check in checks) else "failed", "checks": checks}
