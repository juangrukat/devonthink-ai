"""Shared tool contract metadata helpers for DEVONthink MCP."""

from __future__ import annotations

from typing import Any

from app.tools.risk import validate_risk_class
from app.tools.signal import VALID_SIGNAL_TIERS

VALID_MUTATION_SCOPES = {"none", "single_record", "batch", "database", "system"}


def _default_requires_confirmation(safety_class: str) -> bool:
    return safety_class not in {"read_only", "analysis_only"}


def _default_mutation_scope(safety_class: str, accepted_identifiers: list[str]) -> str:
    if safety_class in {"read_only", "analysis_only"}:
        return "none"
    if safety_class in {"arbitrary_applescript", "maintenance_write", "communication_write"}:
        return "system"
    if "database_uuid" in accepted_identifiers:
        return "database"
    if safety_class == "bulk_write":
        return "batch"
    return "single_record"
def build_description(
    *,
    summary: str,
    use_when: str,
    identifier_guidance: str,
    safety_class: str,
    prefer_when: str,
    example: str,
    degradation_contract: str | None = None,
) -> str:
    lines = [
        summary.strip(),
        f"Use when: {use_when.strip()}",
        f"Identifiers: {identifier_guidance.strip()}",
        f"Safety: {safety_class.strip()}",
        f"Prefer this when: {prefer_when.strip()}",
    ]
    if degradation_contract:
        lines.append(f"Degradation: {degradation_contract.strip()}")
    lines.append(f"Example: {example.strip()}")
    return " ".join(lines)


def catalog_entry(
    *,
    name: str,
    description: str,
    group: str,
    tier: str,
    status: str,
    canonical_tool: str,
    overlap_family: str | None,
    source_path: str,
    catalog_path: str,
    executable: str,
    priority: int,
    default_exposed: bool,
    accepted_identifiers: list[str],
    preferred_identifier: str | None,
    identifier_guidance: str,
    safety_class: str,
    profile_availability: list[str],
    prefer_when: str,
    example: str,
    degradation_contract: str | None = None,
    tags: list[str] | None = None,
    input_schema: dict[str, Any] | None = None,
    invocation_pitfalls: list[str] | None = None,
    supports_dry_run: bool = False,
    supports_plan: bool = False,
    supports_verify: bool = False,
    requires_confirmation: bool | None = None,
    mutation_scope: str | None = None,
    signal_tier: str = "authoritative",
) -> dict[str, Any]:
    normalized_safety_class = validate_risk_class(safety_class)
    normalized_signal_tier = (signal_tier or "").strip()
    if normalized_signal_tier not in VALID_SIGNAL_TIERS:
        allowed = ", ".join(sorted(VALID_SIGNAL_TIERS))
        raise ValueError(f"unknown signal tier: {signal_tier!r}. Expected one of: {allowed}")
    normalized_mutation_scope = mutation_scope or _default_mutation_scope(normalized_safety_class, accepted_identifiers)
    if normalized_mutation_scope not in VALID_MUTATION_SCOPES:
        allowed = ", ".join(sorted(VALID_MUTATION_SCOPES))
        raise ValueError(f"unknown mutation scope: {mutation_scope!r}. Expected one of: {allowed}")
    if supports_plan and not supports_verify:
        raise ValueError(f"{name} cannot support plan without verify support")

    return {
        "name": name,
        "description": description,
        "group": group,
        "tier": tier,
        "status": status,
        "canonical_tool": canonical_tool,
        "overlap_family": overlap_family,
        "source_path": source_path,
        "catalog_path": catalog_path,
        "executable": executable,
        "priority": priority,
        "default_exposed": default_exposed,
        "accepted_identifiers": accepted_identifiers,
        "preferred_identifier": preferred_identifier,
        "identifier_guidance": identifier_guidance,
        "safety_class": normalized_safety_class,
        "supports_dry_run": supports_dry_run,
        "supports_plan": supports_plan,
        "supports_verify": supports_verify,
        "requires_confirmation": (
            _default_requires_confirmation(normalized_safety_class)
            if requires_confirmation is None
            else requires_confirmation
        ),
        "mutation_scope": normalized_mutation_scope,
        "signal_tier": normalized_signal_tier,
        "profile_availability": profile_availability,
        "prefer_when": prefer_when,
        "degradation_contract": degradation_contract,
        "example": example,
        "tags": tags or [],
        "input_schema": input_schema or {},
        "invocation_pitfalls": invocation_pitfalls or [],
    }
