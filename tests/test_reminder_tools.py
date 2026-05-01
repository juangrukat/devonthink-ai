from __future__ import annotations

from app.tools import devonthink_reminder_tools as reminder_tools

RECORD_UUID = "5038E0B0-2134-4CDA-B443-6558CE283BCC"


def test_list_reminders_parses_rows(monkeypatch) -> None:
    monkeypatch.setattr(
        reminder_tools,
        "run_applescript",
        lambda *args, **kwargs: "1\tFriday, May 1, 2026 at 9:00:00 AM\tnotification\n2\tSaturday, May 2, 2026 at 9:00:00 AM\tsound",
    )

    result = reminder_tools.devonthink_list_reminders(RECORD_UUID)

    assert result["ok"] is True
    assert result["data"]["reminders"][0]["id"] == "1"
    assert result["data"]["reminders"][1]["alarm"] == "sound"
    assert result["reminders"][0]["id"] == "1"
    assert result["observability"]["warnings"][0]["code"] == "deprecated_top_level_field"


def test_update_reminder_validates_alarm() -> None:
    result = reminder_tools.devonthink_update_reminder(
        RECORD_UUID,
        "1",
        "2026-05-01T09:00:00",
        "invalid",
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_input"
    assert "alarm must be one of" in result["error"]["message"]


def test_update_reminder_maps_alarm_in_script(monkeypatch) -> None:
    calls = []

    def fake_run(script, args=None, *, tool_name=None):
        calls.append((script, args, tool_name))
        return ""

    monkeypatch.setattr(reminder_tools, "run_applescript", fake_run)

    result = reminder_tools.devonthink_update_reminder(
        RECORD_UUID,
        "1",
        "2026-05-01T09:00:00",
        "sound",
    )

    assert result["ok"] is True
    assert calls[0][1] == [RECORD_UUID, "1", "2026-05-01T09:00:00", "sound"]
    assert 'alarmText is "sound"' in calls[0][0]


def test_delete_reminder_passes_record_and_reminder_id(monkeypatch) -> None:
    calls = []

    def fake_run(script, args=None, *, tool_name=None):
        calls.append((script, args, tool_name))
        return ""

    monkeypatch.setattr(reminder_tools, "run_applescript", fake_run)

    result = reminder_tools.devonthink_delete_reminder(RECORD_UUID, "3")

    assert result["ok"] is True
    assert result["data"]["record_uuid"] == RECORD_UUID
    assert result["record_uuid"] == RECORD_UUID
    assert calls[0][1] == [RECORD_UUID, "3"]


def test_invalid_record_uuid_returns_error_envelope() -> None:
    result = reminder_tools.devonthink_list_reminders("not-a-uuid")

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_uuid"
    assert result["judgment"]["decision"] == "block"
    assert result["error"]["repair_options"]
