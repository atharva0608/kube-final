# execution

## Purpose
The execution module provides the complete operator-facing execution lifecycle: a pre-execution plan summary for final review, a real-time progress view during active execution, and a historical record of past executions. It is the most time-sensitive UI in the platform because operators may need to monitor an in-flight execution and understand exactly which step is running before triggering a manual rollback.

## Responsibilities
- **Pre-execution view:** Show the execution plan summary before the operator starts execution:
  - Nodes to provision (count and instance types)
  - Nodes to drain (count and names)
  - Workloads to migrate (count and list)
  - Estimated duration in minutes
- **Real-time progress view (during execution):**
  - List each execution step with its status: `pending` / `running` / `success` / `failed`
  - Show the current step name prominently with elapsed time
  - Show affected workloads per step
  - On step completion, show `state_before` and `state_after` (expandable JSON diff)
  - If rollback is triggered, switch to rollback progress view (showing rollback steps)
- Poll execution status every 10 s while status is `executing`.
- **Execution history table:** Past executions with:
  - Status (`success` / `rolled_back` / `aborted`)
  - Start timestamp and duration
  - `nodes_provisioned`, `nodes_drained`, `workloads_migrated`
  - `savings_realised_monthly` (USD)
- Allow clicking a past execution to view its full step log.

## Inputs
- **Source:** `POST /clusters/:id/executions` request — trigger new execution (usually called automatically after recommendation approval, but surfaced here for operator visibility)
- **Source:** `GET /clusters/:id/executions` response — `Array<{ execution_id, status, started_at, completed_at, nodes_provisioned, nodes_drained, workloads_migrated, savings_realised_monthly }>`
- **Source:** `GET /clusters/:id/executions/:exec_id`
- **Format:**
```json
{
  "execution_id": "string",
  "status": "executing | success | rolled_back | aborted",
  "started_at": "string",
  "completed_at": "string | null",
  "steps": [
    {
      "step_name": "string",
      "status": "pending | running | success | failed",
      "started_at": "string | null",
      "completed_at": "string | null",
      "affected_workloads": ["string"],
      "state_before": "object | null",
      "state_after": "object | null"
    }
  ],
  "nodes_provisioned": "number",
  "nodes_drained": "number",
  "workloads_migrated": "number",
  "savings_realised_monthly": "number | null",
  "rollback_steps": "array | null"
}
```
- **Source:** Route parameters `cluster_id`, `exec_id` from React Router

## Outputs
- **Destination:** `POST /clusters/:id/executions` — trigger execution
- **Destination:** `GET /clusters/:id/executions` — list executions
- **Destination:** `GET /clusters/:id/executions/:exec_id` — fetch execution detail
- **Format:** JSON

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `execution_history`, `execution_locks`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/clusters/:id/executions` | Trigger a new execution |
| `GET` | `/clusters/:id/executions` | Fetch execution history list |
| `GET` | `/clusters/:id/executions/:exec_id` | Fetch full execution detail with step log |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` hooks** — `usePolling` (10 s when status is `executing`)
- **`frontend/shared` components** — `DataTable` (history table), `StatusBadge` (step status, execution status), JSON diff viewer (state_before/state_after), `Spinner`, `Toast`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for execution API responses

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |
| `VITE_POLLING_INTERVAL_MS` | Polling interval during active execution | `10000` |

## Error Handling
- **Failed step:** A `failed` step status is shown in red with the error message from `state_after.error`. If the execution engine has triggered automatic rollback, the view transitions to rollback progress automatically.
- **Execution lock conflict:** If `POST /clusters/:id/executions` returns 409 (execution already in progress), the UI shows the currently running execution rather than starting a new one.
- **Polling during execution:** If the API becomes temporarily unavailable mid-execution, the polling continues retrying with exponential backoff; a yellow "Connectivity issue – retrying" banner is shown.
- **Aborted execution:** An `aborted` execution shows the reason (e.g., `lock_expired`, `manual_abort`) and links to the relevant support documentation.

## Future Enhancements
- Manual abort button during execution (requires backend support for graceful mid-execution abort).
- Live log streaming (WebSocket) per step, replacing polling.
- Execution comparison: side-by-side view of two past executions.
- Savings tracking: cumulative realised savings chart over time across all executions.
