# Agent Operation Guide

DEVONthink mutating workflows use a plan/apply/verify lifecycle where available.

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
