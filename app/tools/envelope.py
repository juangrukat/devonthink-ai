"""Shared response envelope helpers for DEVONthink MCP tools."""

from __future__ import annotations

from typing import Any

from app.tools.risk import validate_risk_class
from app.tools.signal import confidence_metadata, signal_metadata

CONTRACT_VERSION = "1.0"


def _contract() -> dict[str, str]:
    return {"contract_version": CONTRACT_VERSION, "response_shape": "standard_envelope"}


def _warning_for_alias(key: str) -> dict[str, str]:
    return {
        "code": "deprecated_top_level_field",
        "field": key,
        "message": f"Top-level '{key}' is deprecated; use data.{key} instead.",
    }


def _observability(
    *,
    duration_ms: int | None,
    warnings: list[dict[str, Any]] | None,
    aliases: dict[str, Any] | None,
) -> dict[str, Any]:
    all_warnings = list(warnings or [])
    for key in (aliases or {}):
        all_warnings.append(_warning_for_alias(key))
    result: dict[str, Any] = {"warnings": all_warnings}
    if duration_ms is not None:
        result["duration_ms"] = duration_ms
    return result


def envelope_success(
    *,
    data: dict[str, Any],
    risk_class: str,
    duration_ms: int | None = None,
    aliases: dict[str, Any] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    confidence_score: float = 1.0,
    confidence_rationale: str = "Direct DEVONthink AppleScript result.",
    signal_tier: str = "authoritative",
) -> dict[str, Any]:
    """Build a successful standard envelope.

    ``aliases`` preserves previous top-level response fields for one migration
    window while making ``data`` the canonical response location.
    """
    safety_class = validate_risk_class(risk_class)
    response: dict[str, Any] = {
        "ok": True,
        "data": data,
        "contract": _contract(),
        "judgment": {
            "decision": "allow",
            "risk": {"safety_class": safety_class},
            "signal": signal_metadata(signal_tier),
        },
        "confidence": confidence_metadata(confidence_score, confidence_rationale),
        "observability": _observability(duration_ms=duration_ms, warnings=warnings, aliases=aliases),
    }
    response.update(aliases or {})
    return response


def envelope_error(
    *,
    code: str,
    message: str,
    risk_class: str,
    duration_ms: int | None = None,
    repair_options: list[str] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    confidence_score: float = 1.0,
    signal_tier: str = "authoritative",
) -> dict[str, Any]:
    """Build a failed standard envelope with actionable repair guidance."""
    cleaned_code = (code or "").strip()
    if not cleaned_code:
        raise ValueError("envelope_error requires a non-empty code")
    safety_class = validate_risk_class(risk_class)
    return {
        "ok": False,
        "data": None,
        "error": {
            "code": cleaned_code,
            "message": message,
            "repair_options": repair_options or ["Review the input and retry with corrected values."],
        },
        "contract": _contract(),
        "judgment": {
            "decision": "block",
            "risk": {"safety_class": safety_class},
            "signal": signal_metadata(signal_tier),
        },
        "confidence": confidence_metadata(confidence_score, "Tool blocked before applying a change."),
        "observability": _observability(duration_ms=duration_ms, warnings=warnings, aliases=None),
    }
