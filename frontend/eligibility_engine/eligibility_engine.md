# eligibility_engine

## Purpose
The eligibility engine module provides a structured verdict browser that shows operators exactly why each workload was or was not deemed eligible for Spot placement. It surfaces the full chain of reasoning—hard blocks, conditional warnings, positive signals, and operator overrides—so operators can act on the information and understand what changes would unlock a blocked workload.

## Responsibilities
- List all workloads for a cluster with their eligibility verdict (`ELIGIBLE` / `ELIGIBLE_WITH_CONDITIONS` / `NOT_ELIGIBLE`).
- Per-workload verdict detail panel:
  - Display all `decision_reasons` in a structured list, each with a rule ID, description, and severity.
  - Show hard block rules with their specific IDs (HARD-001 through HARD-006) and a plain-language explanation of the block.
  - List conditional warnings separately (e.g., OOM risk, low data maturity, high spot risk score).
  - Show positive signals (rules that support eligibility) even for blocked workloads, with a callout: "Fix the hard block above and this workload would be eligible."
- Operator override controls:
  - Toggle `spot_eligible=true` to force-enable a blocked workload.
  - Toggle `spot_eligible=false` to force-disable an otherwise eligible workload.
  - Add a mandatory note when applying an override (free-text reason).
- List all active operator overrides for the cluster, showing workload name, override direction, applied_by, and note.
- Filter workload list by verdict type.

## Inputs
- **Source:** `GET /clusters/:id/workloads/:id/eligibility`
- **Format:**
```json
{
  "workload_id": "string",
  "verdict": "ELIGIBLE | ELIGIBLE_WITH_CONDITIONS | NOT_ELIGIBLE",
  "decision_reasons": [
    {
      "rule_id": "string",
      "description": "string",
      "severity": "HARD_BLOCK | CONDITIONAL | POSITIVE",
      "category": "string"
    }
  ]
}
```
- **Source:** `POST /clusters/:id/overrides` request body — `{ workload_id, spot_eligible: boolean, note: string }`
- **Source:** `GET /clusters/:id/overrides` response — `Array<{ override_id, workload_id, spot_eligible, applied_by, applied_at, note }>`
- **Source:** Route parameters `cluster_id`, `workload_id` from React Router

## Outputs
- **Destination:** `POST /clusters/:id/overrides` — submit operator override
- **Destination:** `GET /clusters/:id/workloads/:id/eligibility` — fetch verdict detail
- **Destination:** `GET /clusters/:id/overrides` — fetch current override list
- **Format:** JSON

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads/writes to: `eligibility_verdicts`, `operator_overrides`, `decision_reasons`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id/workloads/:id/eligibility` | Fetch eligibility verdict and decision reasons |
| `POST` | `/clusters/:id/overrides` | Submit an operator override for a workload |
| `GET` | `/clusters/:id/overrides` | List all active operator overrides for the cluster |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` components** — `DataTable`, `Modal` (override confirmation with mandatory note field), `StatusBadge` (verdict, rule severity), `Toast`, `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for eligibility and override API responses; note field minimum length validation

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |

## Error Handling
- **Override without note:** The override modal's submit button is disabled until the operator has entered at least 10 characters in the note field (client-side validation).
- **Conflicting override:** If an override already exists for the workload, the modal pre-populates the current override value and note, and the action becomes "Update override".
- **API error on override POST:** Error toast shown; the local override state is not updated until the API confirms success.
- **Empty verdict (analysis not yet complete):** If the eligibility verdict is not yet available (analysis still running), the detail panel shows a "Verdict pending analysis" placeholder.

## Future Enhancements
- Rule documentation deep-links: each rule ID links to documentation explaining the rule and remediation steps.
- Bulk override mode: apply the same override to all workloads in an application group or namespace.
- Override expiry: allow overrides to auto-expire after a configurable number of days.
