"""Risk metadata helpers for DEVONthink tool envelopes."""

from __future__ import annotations

from typing import Final


VALID_RISK_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "read_only",
        "analysis_only",
        "writes_metadata",
        "writes_content",
        "moves_records",
        "creates_records",
        "communication_write",
        "bulk_write",
        "maintenance_write",
        "destructive",
        "arbitrary_applescript",
    }
)


def validate_risk_class(risk_class: str) -> str:
    """Return a normalized risk class or raise when it is not part of the contract."""
    normalized = (risk_class or "").strip()
    if normalized not in VALID_RISK_CLASSES:
        allowed = ", ".join(sorted(VALID_RISK_CLASSES))
        raise ValueError(f"unknown risk class: {risk_class!r}. Expected one of: {allowed}")
    return normalized
