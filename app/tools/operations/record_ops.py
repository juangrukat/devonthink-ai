"""Record operation handlers for plan/apply/verify lifecycle tools."""

from __future__ import annotations

from typing import Any

import app.tools.devonthink_tools as devonthink_tools

SUPPORTED_RECORD_KINDS = {"Record.MetadataUpdate", "Record.Move"}
METADATA_FIELDS = ("tags", "comment", "comment_mode", "merge_tags", "label", "rating")
SNAPSHOT_FIELDS = ("uuid", "name", "type", "record_type", "location", "location_with_name", "parent_uuid", "tags", "comment", "label", "rating", "locked")


def normalize_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a record lifecycle operation."""
    kind = operation.get("kind")
    if kind not in SUPPORTED_RECORD_KINDS:
        raise ValueError("operation.kind must be one of: Record.MetadataUpdate, Record.Move")

    if kind == "Record.MetadataUpdate":
        record_uuids = operation.get("record_uuids")
        if not isinstance(record_uuids, list) or not record_uuids:
            raise ValueError("operation.record_uuids must contain at least one record UUID")
        normalized: dict[str, Any] = {
            "kind": kind,
            "record_uuids": [str(value).strip() for value in record_uuids if str(value).strip()],
        }
        if not normalized["record_uuids"]:
            raise ValueError("operation.record_uuids must contain at least one record UUID")
        for field in METADATA_FIELDS:
            if field in operation:
                normalized[field] = operation[field]
        if not any(field in normalized for field in ("tags", "comment", "label", "rating")):
            raise ValueError("Record.MetadataUpdate requires at least one of tags, comment, label, or rating")
        normalized.setdefault("comment_mode", "replace")
        normalized.setdefault("merge_tags", True)
        return normalized

    record_uuid = str(operation.get("record_uuid", "")).strip()
    destination_group_uuid = str(operation.get("destination_group_uuid", "")).strip()
    if not record_uuid:
        raise ValueError("operation.record_uuid is required")
    if not destination_group_uuid:
        raise ValueError("operation.destination_group_uuid is required")
    return {
        "kind": kind,
        "record_uuid": record_uuid,
        "destination_group_uuid": destination_group_uuid,
    }


def risk_class_for(operation: dict[str, Any]) -> str:
    """Return the safety class for a record operation."""
    if operation["kind"] == "Record.Move":
        return "moves_records"
    return "writes_metadata"


def snapshot_record(record_uuid: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return a stable record snapshot plus the low-level response."""
    response = devonthink_tools.devonthink_get_record_by_uuid(record_uuid)
    if response.get("ok") is not True:
        return None, response
    data = response.get("data") or {}
    return {field: data.get(field) for field in SNAPSHOT_FIELDS if field in data}, response


def snapshot_records(record_uuids: list[str]) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    """Return snapshots for multiple records, failing on the first unreadable record."""
    snapshots = []
    for record_uuid in record_uuids:
        snapshot, response = snapshot_record(record_uuid)
        if response and response.get("ok") is not True:
            return None, response
        snapshots.append(snapshot or {})
    return snapshots, None


def validate_destination(destination_group_uuid: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Validate that a destination group exists and appears writable."""
    destination, response = snapshot_record(destination_group_uuid)
    if response and response.get("ok") is not True:
        return None, response
    record_type = str((destination or {}).get("record_type") or (destination or {}).get("type") or "").strip().lower()
    if record_type != "group":
        return None, {"ok": False, "error": "Destination record is not a group."}
    if (destination or {}).get("locked"):
        return None, {"ok": False, "error": "Destination group is locked."}
    return destination, None


def planned_after(operation: dict[str, Any], before: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]] | dict[str, Any]:
    """Compute expected post-apply record state from the operation payload."""
    if operation["kind"] == "Record.MetadataUpdate":
        rows = [dict(row) for row in before]  # type: ignore[arg-type]
        for row in rows:
            if "tags" in operation:
                new_tags = [str(value) for value in (operation.get("tags") or [])]
                if operation.get("merge_tags", True):
                    merged = list(row.get("tags") or [])
                    for tag in new_tags:
                        if tag not in merged:
                            merged.append(tag)
                    row["tags"] = merged
                else:
                    row["tags"] = new_tags
            if "comment" in operation:
                old = str(row.get("comment") or "")
                new = str(operation.get("comment") or "")
                mode = operation.get("comment_mode", "replace")
                if mode == "append" and old and new:
                    row["comment"] = f"{old}\n{new}"
                elif mode == "prepend" and old and new:
                    row["comment"] = f"{new}\n{old}"
                elif mode in {"append", "prepend"}:
                    row["comment"] = old or new
                else:
                    row["comment"] = new
            if "label" in operation:
                row["label"] = operation.get("label")
            if "rating" in operation:
                row["rating"] = operation.get("rating")
        return rows

    after = dict(before)  # type: ignore[arg-type]
    destination, _ = validate_destination(operation["destination_group_uuid"])
    after["parent_uuid"] = operation["destination_group_uuid"]
    if destination:
        after["location"] = destination.get("location_with_name") or destination.get("location")
    return after


def apply_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """Apply a normalized record operation using low-level tools."""
    if operation["kind"] == "Record.MetadataUpdate":
        kwargs = {field: operation[field] for field in METADATA_FIELDS if field in operation}
        return devonthink_tools.devonthink_batch_update_record_metadata(operation["record_uuids"], **kwargs)
    return devonthink_tools.devonthink_move(operation["record_uuid"], operation["destination_group_uuid"])


def verify_operation(operation: dict[str, Any], after: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    """Verify current record state against an operation's expected state."""
    if operation["kind"] == "Record.MetadataUpdate":
        current, response = snapshot_records(operation["record_uuids"])
        if response and response.get("ok") is not True:
            return {"status": "failed", "checks": [{"name": "record_state_readable", "passed": False, "details": response.get("error", "Could not read records.")}]}
        checks = []
        for expected, actual in zip(after, current or [], strict=False):  # type: ignore[arg-type]
            uuid = expected.get("uuid")
            for field in ("tags", "comment", "label", "rating"):
                if field in expected:
                    checks.append(
                        {
                            "name": f"{field}_matches",
                            "record_uuid": uuid,
                            "passed": actual.get(field) == expected.get(field),
                            "details": f"{field} matches planned value.",
                        }
                    )
        return {"status": "verified" if all(check["passed"] for check in checks) else "failed", "checks": checks}

    current, response = snapshot_record(operation["record_uuid"])
    if response and response.get("ok") is not True:
        return {"status": "failed", "checks": [{"name": "record_state_readable", "passed": False, "details": response.get("error", "Could not read record.")}]}
    expected = after  # type: ignore[assignment]
    checks = [
        {
            "name": "parent_uuid_matches",
            "record_uuid": operation["record_uuid"],
            "passed": bool(current and current.get("parent_uuid") == expected.get("parent_uuid")),
            "details": "Record parent UUID matches planned destination.",
        },
        {
            "name": "location_matches",
            "record_uuid": operation["record_uuid"],
            "passed": bool(current and current.get("location") == expected.get("location")),
            "details": "Record location matches planned destination.",
        },
    ]
    return {"status": "verified" if all(check["passed"] for check in checks) else "failed", "checks": checks}
