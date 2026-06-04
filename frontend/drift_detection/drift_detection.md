# drift_detection

## Purpose
The drift detection module provides a live status panel that shows operators the current state of their approved execution plan relative to the actual cluster state. When the cluster drifts from what was planned (node changes, pod rescheduling, resource profile changes), this module surfaces the diff and allows the operator to take corrective action—either accept a patch or trigger a full reanalysis.

## Responsibilities
- Show the current plan state: `valid` / `drifted` / `invalidated` / `stale`.
- For `drifted` (patchable) state: render a diff viewer listing each changed element with:
  - `drift_type` (e.g., `node_added`, `node_removed`, `pod_rescheduled`, `resource_profile_changed`)
  - `severity` (`low` / `medium` / `high`)
  - `patchable` indicator (whether the plan can auto-patch without full reanalysis)
  - Affected workloads list
- Show plan delta history: timestamp of the most recent patch, what was changed, and the patch version number.
- For `invalidated` state: show the reason for invalidation (e.g., `new_workload_added`, `pdb_violated`, `spot_risk_spike`) and a "Trigger Reanalysis" button.
- Manual re-check trigger button: `POST /clusters/:id/drift/recheck` for operators who want to force an immediate drift check.
- Poll drift status every 30 s when plan state is `drifted` or `invalidated` to pick up automatic patch outcomes.

## Inputs
- **Source:** `GET /clusters/:id/drift`
- **Format:**
```json
{
  "plan_state": "valid | drifted | invalidated | stale",
  "checked_at": "ISO8601 timestamp",
  "invalidation_reason": "string | null",
  "drift_items": [
    {
      "drift_type": "string",
      "severity": "low | medium | high",
      "patchable": "boolean",
      "affected_workloads": ["string"]
    }
  ],
  "plan_delta_history": [
    {
      "patched_at": "string",
      "patch_version": "number",
      "changes_summary": "string"
    }
  ]
}
```
- **Source:** `POST /clusters/:id/drift/recheck` response — `{ status: 'recheck_scheduled' }`
- **Source:** Route parameter `cluster_id` from React Router

## Outputs
- **Destination:** `POST /clusters/:id/drift/recheck` — trigger manual drift re-check
- **Format:** Empty body

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `drift_events`, `plan_deltas`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id/drift` | Fetch current drift status and diff |
| `POST` | `/clusters/:id/drift/recheck` | Trigger immediate drift re-check |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` hooks** — `usePolling` (30 s interval when state is `drifted` or `invalidated`)
- **`frontend/shared` components** — `StatusBadge` (plan state, drift severity), `DataTable` (drift item list), `Modal` (reanalysis confirmation), `Toast`, `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for drift status response

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |
| `VITE_DRIFT_POLL_INTERVAL_MS` | Polling interval when plan is drifted/invalidated | `30000` |

## Error Handling
- **Recheck throttle:** If the operator clicks "Re-check" more than once within 60 seconds, the button is disabled and a tooltip explains that a recheck is already in progress.
- **`invalidated` with no reason:** If `invalidation_reason` is null (data inconsistency), the UI shows "Unknown reason — contact support" with a reference ID.
- **API error on status fetch:** Error card with retry; polling is paused during error state.
- **`stale` state:** When the plan state is `stale` (plan was never approved, or the last approved plan expired), a contextual message directs the operator to the recommendations module to generate and approve a new plan.

## Future Enhancements
- Push notification when drift state transitions from `valid` to `drifted` (WebSocket or browser notification).
- Detailed workload-level diff showing state_before and state_after for each affected workload.
- Auto-patch preview: show what the patched plan would look like before confirming.
