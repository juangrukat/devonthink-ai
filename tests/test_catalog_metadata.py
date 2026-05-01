from __future__ import annotations

from collections import Counter

from app.tools.risk import VALID_RISK_CLASSES
from app.tools.signal import VALID_SIGNAL_TIERS
from app.tools.tool_catalog import VALID_MUTATION_SCOPES
from scripts.build_tool_catalog import build_tools


REQUIRED_METADATA = {
    "safety_class",
    "supports_dry_run",
    "supports_plan",
    "supports_verify",
    "requires_confirmation",
    "mutation_scope",
    "signal_tier",
}


def test_every_catalog_entry_declares_d2_metadata() -> None:
    entries = build_tools()

    assert entries
    for entry in entries:
        assert REQUIRED_METADATA <= entry.keys(), entry["name"]
        assert entry["safety_class"] in VALID_RISK_CLASSES
        assert isinstance(entry["supports_dry_run"], bool)
        assert isinstance(entry["supports_plan"], bool)
        assert isinstance(entry["supports_verify"], bool)
        assert isinstance(entry["requires_confirmation"], bool)
        assert entry["mutation_scope"] in VALID_MUTATION_SCOPES
        assert entry["signal_tier"] in VALID_SIGNAL_TIERS


def test_catalog_plan_support_requires_verify_support() -> None:
    for entry in build_tools():
        if entry["supports_plan"]:
            assert entry["supports_verify"], entry["name"]


def test_catalog_has_representative_safety_classes() -> None:
    counts = Counter(entry["safety_class"] for entry in build_tools())

    assert counts["read_only"] > 0
    assert counts["writes_content"] > 0
    assert counts["destructive"] > 0
