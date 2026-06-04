# rollback

## Purpose
The rollback module provides a dedicated status viewer for rollback operations that are triggered either automatically by the execution engine (on health-check failure) or manually by the operator. It is a separate feature area because rollback events are high-urgency and operators need focused, uncluttered visibility into the recovery process without the noise of the broader execution view.

## Responsibilities
- Display the current rollback status when an active rollback is in progress, showing each rollback step and its status (`pending` / `running` / `success` / `failed`).
- Show recovery validation results upon rollback completion: which nodes were successfully restored to On-Demand, which pods are confirmed running, and whether any pods remain in a degraded state.
- Rollback history table: list past rollback events with execution ID, rollback reason, rollback duration, and final status (`rolled_back` confirmed / `rollback_failed`).
- Link each rollback history entry to the originating execution for context.
- The module reads rollback data from the same `GET /clusters/:id/executions/:exec_id` endpoint used by the execution module; rollback data is embedded in the execution detail response under `rollback_steps`.

## Inputs
- **Source:** `GET /clusters/:id/executions/:exec_id`
- **Format (rollback-relevant fields):**
```json
{
  "execution_id": "string",
  "status": "rolled_back | rollback_failed",
  "rollback_steps": [
    {
      "step_name": "string",
      "status": "pending | running | success | failed",
      "started_at": "string | null",
      "completed_at": "string | null",
      "affected_nodes": ["string"],
      "affected_pods": ["string"],
      "state_before": "object | null",
      "state_after": "object | null"
    }
  ],
  "rollback_reason": "string",
  "rollback_started_at": "string",
  "rollback_completed_at": "string | null",
  "recovery_validation": {
    "nodes_restored": ["string"],
    "pods_running": ["string"],
    "pods_degraded": ["string"]
  }
}
```
- **Source:** `GET /clusters/:id/executions` — to build the rollback history list (filters executions where `status = 'rolled_back'`)
- **Source:** Route parameters `cluster_id`, `exec_id` from React Router

## Outputs
- **Destination:** HTTP GET requests to backend API (read-only; rollback is triggered by the execution engine, not by this UI module directly)
- **Format:** N/A (no mutation calls)

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `execution_history`, `rollback_snapshots`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id/executions/:exec_id` | Fetch execution detail including rollback steps and recovery validation |
| `GET` | `/clusters/:id/executions` | Fetch execution list filtered to rolled-back executions for history |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` hooks** — `usePolling` (10 s while rollback is in progress)
- **`frontend/shared` components** — `DataTable` (rollback history), `StatusBadge` (rollback step status, final status), `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for execution/rollback API responses
- **`frontend/execution`** — Shared execution detail endpoint; rollback view is often a sub-view within the execution context

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |
| `VITE_POLLING_INTERVAL_MS` | Polling interval while rollback is in progress | `10000` |

## Error Handling
- **Rollback still in progress:** The module polls every 10 s while `rollback_completed_at` is null; a progress indicator is shown.
- **`pods_degraded` after rollback:** If `recovery_validation.pods_degraded` is non-empty, a red alert is shown listing degraded pods with a link to the Kubernetes documentation for manual recovery.
- **`rollback_failed` status:** If the rollback itself failed, a high-severity error banner is shown with the failure details from the last `rollback_step` in `failed` status, and a link to the BalanceKube support escalation page.
- **Rollback not yet triggered:** If the operator navigates to this module when no rollback exists for the selected execution, an informational message is shown: "No rollback has been triggered for this execution."

## Future Enhancements
- Manual rollback trigger button (currently rollback is engine-triggered; surface a manual "Force Rollback" for the operator while execution is still in progress).
- Rollback dry-run preview: show what state the cluster would return to before confirming.
- Post-rollback health summary email/Slack notification.
