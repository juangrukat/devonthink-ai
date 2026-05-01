from __future__ import annotations

import pytest

from app.tools.envelope import envelope_error, envelope_success
from app.tools import devonthink_reminder_tools as reminder_tools

RECORD_UUID = "5038E0B0-2134-4CDA-B443-6558CE283BCC"
ENVELOPE_KEYS = {"ok", "data", "contract", "judgment", "confidence", "observability"}


def test_success_envelope_contains_contract_keys() -> None:
    result = envelope_success(
        data={"record_uuid": "5038E0B0-2134-4CDA-B443-6558CE283BCC"},
        risk_class="read_only",
        aliases={"record_uuid": "5038E0B0-2134-4CDA-B443-6558CE283BCC"},
    )

    assert {"ok", "data", "contract", "judgment", "confidence", "observability"} <= result.keys()
    assert result["contract"]["contract_version"] == "1.0"
    assert result["record_uuid"] == result["data"]["record_uuid"]
    assert result["observability"]["warnings"][0]["field"] == "record_uuid"


def test_error_envelope_requires_code() -> None:
    with pytest.raises(ValueError, match="requires a non-empty code"):
        envelope_error(code="", message="Nope.", risk_class="read_only")


def test_success_envelope_rejects_unknown_risk_class() -> None:
    with pytest.raises(ValueError, match="unknown risk class"):
        envelope_success(data={}, risk_class="mystery")


def test_error_envelope_blocks_with_repair_options() -> None:
    result = envelope_error(
        code="invalid_uuid",
        message="record_uuid is invalid.",
        risk_class="read_only",
        repair_options=["Use a DEVONthink UUID."],
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_uuid"
    assert result["judgment"]["decision"] == "block"
    assert result["error"]["repair_options"] == ["Use a DEVONthink UUID."]


@pytest.mark.parametrize(
    ("tool_call", "expected_risk"),
    [
        (lambda: reminder_tools.devonthink_list_reminders(RECORD_UUID), "read_only"),
        (lambda: reminder_tools.devonthink_update_reminder(RECORD_UUID, "1", "2026-05-01T09:00:00"), "writes_metadata"),
        (lambda: reminder_tools.devonthink_delete_reminder(RECORD_UUID, "1"), "destructive"),
    ],
)
def test_reminder_success_responses_use_standard_envelope(monkeypatch, tool_call, expected_risk) -> None:
    monkeypatch.setattr(reminder_tools, "run_applescript", lambda *args, **kwargs: "")

    result = tool_call()

    assert ENVELOPE_KEYS <= result.keys()
    assert result["ok"] is True
    assert result["contract"]["contract_version"] == "1.0"
    assert result["judgment"]["risk"]["safety_class"] == expected_risk
