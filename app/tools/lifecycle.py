"""Plan/apply/verify lifecycle tools for DEVONthink operations."""

from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.tools.envelope import envelope_error, envelope_success
from app.tools.operations import reminder_ops
from app.tools.telemetry import wrap_tool_call
from app.tools.tool_catalog import build_description, catalog_entry

PLAN_TTL_SECONDS = 300
PLAN_STORE: dict[str, dict[str, Any]] = {}


def _duration_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _error(code: str, message: str, risk_class: str, started: float, repair_options: list[str] | None = None) -> dict[str, Any]:
    return envelope_error(
        code=code,
        message=message,
        risk_class=risk_class,
        duration_ms=_duration_ms(started),
        repair_options=repair_options,
    )


def clear_plan_store() -> None:
    """Clear in-memory lifecycle plans. Intended for tests."""
    PLAN_STORE.clear()


def _load_plan(plan_id: str, started: float) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    cleaned = (plan_id or "").strip()
    if not cleaned:
        return None, _error("plan_id_required", "plan_id is required.", "writes_metadata", started)
    plan = PLAN_STORE.get(cleaned)
    if plan is None:
        return None, _error("plan_not_found", f"No plan found for plan_id: {cleaned}", "writes_metadata", started)
    return plan, None


def devonthink_plan_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """Create a confirmation-gated plan for a supported DEVONthink operation."""
    started = time.perf_counter()
    try:
        normalized = reminder_ops.normalize_operation(operation or {})
    except ValueError as exc:
        return _error("invalid_operation", str(exc), "writes_metadata", started)
    risk_class = reminder_ops.risk_class_for(normalized)
    before, response = reminder_ops.find_reminder(normalized["record_uuid"], normalized["reminder_id"])
    if response and response.get("ok") is not True:
        message = response.get("error", {}).get("message", "Could not list reminders.")
        return _error("target_lookup_failed", message, risk_class, started)
    if before is None:
        return _error(
            "reminder_not_found",
            f"Reminder not found for id: {normalized['reminder_id']}",
            risk_class,
            started,
            ["Run devonthink-list-reminders and re-plan with an existing reminder id."],
        )

    expires_at = _utc_now() + timedelta(seconds=PLAN_TTL_SECONDS)
    plan_id = f"plan_{uuid4().hex}"
    token = secrets.token_urlsafe(24)
    after = reminder_ops.planned_after(normalized, before)
    plan = {
        "plan_id": plan_id,
        "operation": normalized,
        "before": before,
        "after": after,
        "confirmation_token": token,
        "expires_at": expires_at,
        "applied": False,
        "applied_at": None,
        "verification": None,
    }
    PLAN_STORE[plan_id] = plan
    return envelope_success(
        data={
            "plan_id": plan_id,
            "operation_kind": normalized["kind"],
            "needs_confirmation": True,
            "confirmation": {"token": token, "expires_at": _iso(expires_at)},
            "before": before,
            "after": after,
        },
        risk_class=risk_class,
        duration_ms=_duration_ms(started),
    )


def devonthink_apply_operation(plan_id: str, confirmation_token: str) -> dict[str, Any]:
    """Apply a previously planned DEVONthink operation after stale-plan checks."""
    started = time.perf_counter()
    plan, error = _load_plan(plan_id, started)
    if error:
        return error
    assert plan is not None
    operation = plan["operation"]
    risk_class = reminder_ops.risk_class_for(operation)
    if plan["applied"]:
        return _error("plan_already_applied", f"Plan already applied: {plan_id}", risk_class, started)
    if _utc_now() > plan["expires_at"]:
        return _error("confirmation_expired", f"Confirmation token expired for plan_id: {plan_id}", risk_class, started)
    if not secrets.compare_digest(confirmation_token or "", plan["confirmation_token"]):
        return _error("confirmation_invalid", "confirmation_token does not match this plan.", risk_class, started)

    current, response = reminder_ops.find_reminder(operation["record_uuid"], operation["reminder_id"])
    if response and response.get("ok") is not True:
        message = response.get("error", {}).get("message", "Could not list reminders.")
        return _error("target_lookup_failed", message, risk_class, started)
    if current != plan["before"]:
        return _error(
            "stale_plan",
            "Reminder state changed after the plan was created.",
            risk_class,
            started,
            ["Re-run devonthink-plan-operation against the current reminder state."],
        )

    apply_response = reminder_ops.apply_operation(operation)
    if apply_response.get("ok") is not True:
        message = apply_response.get("error", {}).get("message", "Operation failed.")
        code = apply_response.get("error", {}).get("code", "apply_failed")
        return _error(code, message, risk_class, started)

    verification = reminder_ops.verify_operation(operation, plan["after"])
    plan["applied"] = True
    plan["applied_at"] = _utc_now()
    plan["verification"] = verification
    return envelope_success(
        data={
            "plan_id": plan_id,
            "operation_kind": operation["kind"],
            "status": "completed",
            "applied_at": _iso(plan["applied_at"]),
            "result": apply_response.get("data"),
            "verification": verification,
        },
        risk_class=risk_class,
        duration_ms=_duration_ms(started),
    )


def devonthink_verify_operation(plan_id: str) -> dict[str, Any]:
    """Verify a plan's expected post-state against current DEVONthink reminder state."""
    started = time.perf_counter()
    plan, error = _load_plan(plan_id, started)
    if error:
        return error
    assert plan is not None
    operation = plan["operation"]
    risk_class = reminder_ops.risk_class_for(operation)
    verification = reminder_ops.verify_operation(operation, plan["after"])
    plan["verification"] = verification
    return envelope_success(
        data={
            "plan_id": plan_id,
            "operation_kind": operation["kind"],
            "status": verification["status"],
            "verification": verification,
        },
        risk_class=risk_class,
        duration_ms=_duration_ms(started),
    )


def lifecycle_tool_catalog_entries() -> list[dict[str, Any]]:
    identifier_guidance = "Accepts lifecycle plan identifiers and operation objects for supported reminder operations."
    common = {
        "group": "devonthink.native",
        "tier": "advanced",
        "status": "active",
        "overlap_family": "devonthink-lifecycle",
        "source_path": "app/tools/lifecycle.py",
        "executable": "python",
        "priority": 70,
        "default_exposed": False,
        "accepted_identifiers": ["record_uuid"],
        "preferred_identifier": "record_uuid",
        "identifier_guidance": identifier_guidance,
        "profile_availability": ["minimal", "canonical", "full"],
        "tags": ["devonthink", "lifecycle", "plan-apply-verify"],
        "supports_plan": True,
        "supports_verify": True,
        "requires_confirmation": True,
        "mutation_scope": "single_record",
        "signal_tier": "authoritative",
    }
    return [
        catalog_entry(
            name="devonthink-plan-operation",
            description=build_description(
                summary="Plan a supported DEVONthink operation and return before/after state plus a confirmation token.",
                use_when="you need to stage a Reminder.Update or Reminder.Delete operation before applying it.",
                identifier_guidance=identifier_guidance,
                safety_class="writes_metadata",
                prefer_when="you want stale-target protection before changing a reminder.",
                example='{"operation":{"kind":"Reminder.Update","record_uuid":"5038E0B0-2134-4CDA-B443-6558CE283BCC","reminder_id":"1","due_date":"2026-05-01T09:00:00","alarm":"notification"}}',
            ),
            canonical_tool="devonthink-plan-operation",
            catalog_path="catalog-runtime/tools/devonthink.native/advanced/devonthink-plan-operation.json",
            safety_class="writes_metadata",
            prefer_when="you want stale-target protection before changing a reminder.",
            example='{"operation":{"kind":"Reminder.Update","record_uuid":"5038E0B0-2134-4CDA-B443-6558CE283BCC","reminder_id":"1","due_date":"2026-05-01T09:00:00","alarm":"notification"}}',
            **common,
        ),
        catalog_entry(
            name="devonthink-apply-operation",
            description=build_description(
                summary="Apply a previously planned DEVONthink operation after confirmation and stale-plan checks.",
                use_when="you have a plan_id and confirmation token from devonthink-plan-operation.",
                identifier_guidance=identifier_guidance,
                safety_class="writes_metadata",
                prefer_when="you are ready to apply a staged reminder operation.",
                example='{"plan_id":"plan_...","confirmation_token":"..."}',
            ),
            canonical_tool="devonthink-apply-operation",
            catalog_path="catalog-runtime/tools/devonthink.native/advanced/devonthink-apply-operation.json",
            safety_class="writes_metadata",
            prefer_when="you are ready to apply a staged reminder operation.",
            example='{"plan_id":"plan_...","confirmation_token":"..."}',
            **common,
        ),
        catalog_entry(
            name="devonthink-verify-operation",
            description=build_description(
                summary="Verify a planned DEVONthink operation against current state.",
                use_when="you need to re-check whether a planned/applied reminder operation's expected post-state holds.",
                identifier_guidance=identifier_guidance,
                safety_class="read_only",
                prefer_when="you want post-apply evidence without applying another change.",
                example='{"plan_id":"plan_..."}',
            ),
            canonical_tool="devonthink-verify-operation",
            catalog_path="catalog-runtime/tools/devonthink.native/advanced/devonthink-verify-operation.json",
            safety_class="read_only",
            requires_confirmation=False,
            mutation_scope="none",
            prefer_when="you want post-apply evidence without applying another change.",
            example='{"plan_id":"plan_..."}',
            **{key: value for key, value in common.items() if key not in {"requires_confirmation", "mutation_scope"}},
        ),
    ]


def register_lifecycle_tools(mcp: Any) -> None:
    """Register lifecycle tools."""
    catalog = {entry["name"]: entry for entry in lifecycle_tool_catalog_entries()}

    @mcp.tool(name="devonthink-plan-operation", description=catalog["devonthink-plan-operation"]["description"])
    def _devonthink_plan_operation(operation: dict[str, Any]) -> dict[str, Any]:
        return wrap_tool_call("devonthink-plan-operation", devonthink_plan_operation, operation=operation)

    @mcp.tool(name="devonthink-apply-operation", description=catalog["devonthink-apply-operation"]["description"])
    def _devonthink_apply_operation(plan_id: str, confirmation_token: str) -> dict[str, Any]:
        return wrap_tool_call(
            "devonthink-apply-operation",
            devonthink_apply_operation,
            plan_id=plan_id,
            confirmation_token=confirmation_token,
        )

    @mcp.tool(name="devonthink-verify-operation", description=catalog["devonthink-verify-operation"]["description"])
    def _devonthink_verify_operation(plan_id: str) -> dict[str, Any]:
        return wrap_tool_call("devonthink-verify-operation", devonthink_verify_operation, plan_id=plan_id)
