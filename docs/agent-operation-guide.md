# Agent Operation Guide

DEVONthink mutating workflows use a plan/apply/verify lifecycle where available. Standard
envelope responses put canonical payloads under `data`, with `judgment`, `confidence`, and
`observability` blocks available for caller policy.

## Reminder Operations

Use `devonthink-plan-operation` before changing or deleting a reminder. The plan response includes
the current `before` reminder state, expected `after` state, a `plan_id`, and a short-lived
confirmation token.

```json
{
  "operation": {
    "kind": "Reminder.Update",
    "record_uuid": "5038E0B0-2134-4CDA-B443-6558CE283BCC",
    "reminder_id": "1",
    "due_date": "2026-05-01T09:00:00",
    "alarm": "notification"
  }
}
```

Then call `devonthink-apply-operation` with the `plan_id` and confirmation token. Apply re-reads the
reminder first; if the `before` state has changed, it returns `error.code = "stale_plan"` and the
caller should create a new plan. Use `devonthink-verify-operation` to re-check the expected post-state
without applying another change.

## Record Operations

`devonthink-plan-operation` also supports `Record.MetadataUpdate` and `Record.Move`.
Metadata plans include full before/after state for every changed field across the batch; if any
record drifts before apply, the whole batch is blocked with `error.code = "stale_plan"` and
`observability.warnings[].drifted_uuids`.

```json
{
  "operation": {
    "kind": "Record.MetadataUpdate",
    "record_uuids": ["5038E0B0-2134-4CDA-B443-6558CE283BCC"],
    "tags": ["review"],
    "comment": "Needs follow-up",
    "comment_mode": "append"
  }
}
```

Move plans use `Record.Move`, validate that the destination group exists, and verify both
`parent_uuid` and `location` after apply.

## Link Act Tools

For link maintenance actions, run report mode first and keep the returned `data.plan_id`.
Apply mode requires that plan ID and checks the actionable-row hash before writing:

- `devonthink-link-maintenance-pass`
- `devonthink-link-repair-links`
- `devonthink-link-build-hub`
- `devonthink-link-enrich-metadata`

Missing plans return `plan_id_required`; expired plans return `plan_expired`; changed rows return
`stale_plan`.

## Snapshots

Apply calls may opt into audit snapshots with `policy.capture_snapshot=true`. When captured,
`devonthink-apply-operation` returns `data.post_apply_snapshot_id` and records the plan-to-snapshot
link in the local snapshot index so pruning can protect the audit trail.

`devonthink-link-compare-snapshots` now returns structured `verification.checks`, `confidence`,
`risk`, and optional `plan_id` evidence without changing snapshot files on disk.

## AppleScript Quirks

Use `devonthink-inspect-quirks` before fallback scripting or risky tool selection. It filters the
curated registry by tool, operation, record type, AppleScript command, and severity.
