"""Signal and confidence helpers for DEVONthink tool envelopes."""

from __future__ import annotations

from typing import Final


VALID_SIGNAL_TIERS: Final[frozenset[str]] = frozenset({"authoritative", "structural", "inferred"})


def signal_metadata(signal_tier: str = "authoritative") -> dict[str, str]:
    """Build normalized signal metadata for an envelope."""
    normalized = (signal_tier or "").strip()
    if normalized not in VALID_SIGNAL_TIERS:
        allowed = ", ".join(sorted(VALID_SIGNAL_TIERS))
        raise ValueError(f"unknown signal tier: {signal_tier!r}. Expected one of: {allowed}")
    return {"tier": normalized}


def confidence_metadata(score: float = 1.0, rationale: str = "Direct DEVONthink AppleScript result.") -> dict[str, float | str]:
    """Build a bounded confidence block."""
    bounded_score = max(0.0, min(1.0, float(score)))
    return {"score": bounded_score, "rationale": rationale}
