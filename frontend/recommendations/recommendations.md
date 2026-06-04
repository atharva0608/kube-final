# recommendations

## Purpose
The recommendations module is the primary operator decision point in the BalanceKube workflow. It presents a savings summary dashboard, a per-workload cost breakdown, and the approval workflow that initiates the execution engine. It is the central UI where the value proposition of the platform is made tangible—showing operators exactly how much they will save by migrating eligible workloads to Spot.

## Responsibilities
- Display the total cluster savings estimate prominently, labelled "Potential Savings Estimate" (monthly, in USD).
- Per-workload savings breakdown table: current on-demand cost (monthly), projected spot cost, savings amount, savings percentage, and spot risk score for the target instance type.
- Show pricing freshness warning banner if the underlying pricing data is older than the configured threshold.
- Eligibility summary strip: count of eligible workloads, count blocked, count with operator overrides.
- Render a savings chart (bar or donut) showing breakdown by namespace or application group.
- **Approval workflow:**
  - "Approve Recommendation" button opens a confirmation modal showing:
    - Total nodes to provision (Spot)
    - Total nodes to drain (On-Demand)
    - Workloads to be migrated (count and list)
    - Estimated execution duration
    - Monthly savings amount
  - Operator confirms → `POST /clusters/:id/recommendations/:rec_id/approve`
- Show recommendation status badge: `generated` / `pending_approval` / `approved` / `executing` / `success` / `rolled_back`.
- Refresh recommendation list to show status transitions in near-real-time (polling every 15 s when status is `executing`).

## Inputs
- **Source:** `GET /clusters/:id/recommendations`
- **Format:** `Array<{ rec_id, status, created_at, total_savings_usd_monthly, eligible_count, blocked_count, override_count }>`
- **Source:** `GET /clusters/:id/recommendations/:rec_id`
- **Format:**
```json
{
  "rec_id": "string",
  "status": "generated | pending_approval | approved | executing | success | rolled_back",
  "created_at": "string",
  "total_savings_usd_monthly": "number",
  "pricing_fetched_at": "string",
  "plan": {
    "nodes_to_provision": "number",
    "nodes_to_drain": "number",
    "workloads_to_migrate": "number",
    "estimated_duration_min": "number"
  },
  "workload_savings": [
    {
      "workload_id": "string",
      "name": "string",
      "namespace": "string",
      "current_cost_usd_monthly": "number",
      "projected_spot_cost_usd_monthly": "number",
      "savings_usd_monthly": "number",
      "savings_pct": "number",
      "spot_risk_score": "number"
    }
  ]
}
```
- **Source:** Route parameters `cluster_id`, `rec_id` from React Router

## Outputs
- **Destination:** `POST /clusters/:id/recommendations/:rec_id/approve` — approve recommendation and trigger execution
- **Format:** Empty body (approval is idempotent; no payload needed)

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `recommendation_store`, `savings_estimates`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id/recommendations` | List all recommendations for the cluster |
| `GET` | `/clusters/:id/recommendations/:rec_id` | Fetch full recommendation detail and savings breakdown |
| `POST` | `/clusters/:id/recommendations/:rec_id/approve` | Approve recommendation and trigger execution |

## Dependencies
- **`frontend/shared/api`** — API client (with polling via `usePolling` hook when status is `executing`)
- **`frontend/shared` components** — `DataTable`, `Modal` (approval confirmation), `StatusBadge` (recommendation status), Chart (savings bar/donut), `Toast`, `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for recommendation API responses
- **`frontend/shared` hooks** — `usePolling`, `useRecommendation`

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |
| `VITE_POLLING_INTERVAL_MS` | Polling interval when recommendation status is `executing` | `15000` |
| `VITE_PRICING_STALENESS_THRESHOLD_MIN` | Threshold for pricing freshness warning in the savings view | `60` |

## Error Handling
- **Stale pricing warning:** If `pricing_fetched_at` is older than `VITE_PRICING_STALENESS_THRESHOLD_MIN`, a yellow warning is shown in the savings breakdown header, noting that savings estimates may not reflect current spot prices.
- **Approval already in progress:** If the operator clicks "Approve" on a recommendation already in `executing` state (e.g., approved from another session), the API returns 409; the UI shows a "Execution already in progress" message and redirects to the execution view.
- **Double-click guard:** The approve button is disabled immediately on first click (pending state) to prevent duplicate approval calls.
- **Empty recommendation list:** Shows a "No recommendations yet" empty state with a link to the workload review module.

## Future Enhancements
- Per-workload approval: approve individual workloads rather than the entire recommendation.
- Savings history chart: show realised savings over past executions vs. projected savings.
- Spot risk tolerance slider: allow operators to exclude workloads above a configurable risk score threshold from the recommendation.
- Scheduled approval: set a time window for execution (e.g., "only execute between 2am and 5am").
