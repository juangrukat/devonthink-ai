"""Machine-readable AppleScript quirks registry tools."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.tools.envelope import envelope_success
from app.tools.telemetry import wrap_tool_call
from app.tools.tool_catalog import build_description, catalog_entry

QUIRKS_PATH = Path(__file__).resolve().parents[1] / "data" / "devonthink_quirks.json"


def _duration_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def load_quirks() -> list[dict[str, Any]]:
    """Load curated DEVONthink AppleScript quirks from disk."""
    return json.loads(QUIRKS_PATH.read_text(encoding="utf-8"))


def _matches_list(values: list[str], needle: str | None) -> bool:
    if not needle:
        return True
    cleaned = needle.strip().lower()
    return any(cleaned in str(value).lower() for value in values)


def devonthink_inspect_quirks(
    tool: str | None = None,
    operation: str | None = None,
    record_type: str | None = None,
    applescript_command: str | None = None,
    severity: str | None = None,
) -> dict[str, Any]:
    """Inspect curated AppleScript quirks, optionally filtered by tool or command context."""
    started = time.perf_counter()
    severity_filter = (severity or "").strip().lower()
    entries = []
    for entry in load_quirks():
        if severity_filter and entry["severity"] != severity_filter:
            continue
        if not _matches_list(entry["affected_tools"], tool):
            continue
        if not _matches_list(entry["operations"], operation):
            continue
        if not _matches_list(entry["record_types"], record_type):
            continue
        if not _matches_list(entry["applescript_commands"], applescript_command):
            continue
        entries.append(entry)
    return envelope_success(
        data={
            "quirks": entries,
            "count": len(entries),
            "filters": {
                "tool": tool,
                "operation": operation,
                "record_type": record_type,
                "applescript_command": applescript_command,
                "severity": severity,
            },
        },
        risk_class="read_only",
        duration_ms=_duration_ms(started),
        confidence_rationale="Curated local AppleScript quirks registry.",
        signal_tier="authoritative",
    )


def quirks_tool_catalog_entries() -> list[dict[str, Any]]:
    identifier_guidance = "Accepts optional filters for tool name, operation, record type, AppleScript command, and severity."
    return [
        catalog_entry(
            name="devonthink-inspect-quirks",
            description=build_description(
                summary="Inspect curated DEVONthink AppleScript compatibility quirks as structured data.",
                use_when="you need to understand known AppleScript pitfalls before choosing or applying a DEVONthink tool.",
                identifier_guidance=identifier_guidance,
                safety_class="read_only",
                prefer_when="you want machine-readable compatibility guidance rather than README prose.",
                example='{"tool":"devonthink-search-records","severity":"high"}',
            ),
            group="devonthink.native",
            tier="canonical",
            status="active",
            canonical_tool="devonthink-inspect-quirks",
            overlap_family="devonthink-quirks",
            source_path="app/tools/devonthink_quirks_tools.py",
            catalog_path="catalog-runtime/tools/devonthink.native/canonical/devonthink-inspect-quirks.json",
            executable="python",
            priority=100,
            default_exposed=True,
            accepted_identifiers=[],
            preferred_identifier=None,
            identifier_guidance=identifier_guidance,
            safety_class="read_only",
            supports_dry_run=True,
            supports_plan=False,
            supports_verify=False,
            requires_confirmation=False,
            mutation_scope="none",
            signal_tier="authoritative",
            profile_availability=["minimal", "canonical", "full"],
            prefer_when="you need AppleScript quirk guidance before tool selection or fallback scripting.",
            example='{"tool":"devonthink-search-records","severity":"high"}',
            tags=["devonthink", "quirks", "applescript", "compatibility"],
        )
    ]


def register_devonthink_quirks_tools(mcp: Any) -> None:
    """Register quirks registry tools."""
    catalog = {entry["name"]: entry for entry in quirks_tool_catalog_entries()}

    @mcp.tool(name="devonthink-inspect-quirks", description=catalog["devonthink-inspect-quirks"]["description"])
    def _devonthink_inspect_quirks(
        tool: str | None = None,
        operation: str | None = None,
        record_type: str | None = None,
        applescript_command: str | None = None,
        severity: str | None = None,
    ) -> dict[str, Any]:
        return wrap_tool_call(
            "devonthink-inspect-quirks",
            devonthink_inspect_quirks,
            tool=tool,
            operation=operation,
            record_type=record_type,
            applescript_command=applescript_command,
            severity=severity,
        )
