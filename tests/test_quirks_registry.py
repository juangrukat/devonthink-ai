from __future__ import annotations

import json

from app.tools.devonthink_quirks_tools import QUIRKS_PATH, devonthink_inspect_quirks


def test_quirks_registry_entries_have_required_shape() -> None:
    entries = json.loads(QUIRKS_PATH.read_text())
    required = {
        "id",
        "title",
        "affected_tools",
        "operations",
        "record_types",
        "applescript_commands",
        "severity",
        "mitigation",
        "signal_tier_impact",
    }
    assert len(entries) >= 8
    assert all(required <= set(entry) for entry in entries)


def test_lookup_by_tool_returns_database_scope_quirk() -> None:
    response = devonthink_inspect_quirks(tool="devonthink-search-records")
    ids = {entry["id"] for entry in response["data"]["quirks"]}
    assert "database_uuid_search_scope_requires_incoming_group" in ids


def test_lookup_by_high_severity_returns_seed_entries() -> None:
    response = devonthink_inspect_quirks(severity="high")
    ids = {entry["id"] for entry in response["data"]["quirks"]}
    assert {"type_is_enum_not_string", "database_uuid_search_scope_requires_incoming_group"} <= ids


def test_inspect_quirks_uses_standard_envelope() -> None:
    response = devonthink_inspect_quirks(record_type="markdown")
    assert response["ok"] is True
    assert {"ok", "data", "contract", "judgment", "confidence", "observability"} <= set(response)
