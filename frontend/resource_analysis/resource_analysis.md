# resource_analysis

## Purpose
The resource analysis module renders a per-workload resource profile viewer, allowing operators to inspect how the Phase 2 resource analysis engine assessed each workload's CPU and memory utilisation. It exposes the computed resource states, rightsizing recommendations, and workload-specific signals (JVM detection, batch spike detection, OOM risk) that feed into the eligibility and recommendation engines.

## Responsibilities
- Display the CPU utilisation state per workload: `THROTTLED` / `OVER_PROVISIONED` / `RIGHT_SIZED` / `UNDER_PROVISIONED`, with the computed `cpu_util_ratio` (actual / requested).
- Display the memory utilisation state: `OVER_PROVISIONED` / `RIGHT_SIZED` / `UNDER_PROVISIONED`, with `mem_util_ratio`.
- Show OOM risk flag (`oom_risk: true/false`) with a red warning indicator.
- Show `data_maturity` level (`MATURE` / `SUFFICIENT` / `INSUFFICIENT`) with a tooltip explaining impact on analysis accuracy.
- For Java workloads: show the `is_java` flag with a note that JVM heap analysis applies conservative memory assumptions to avoid false OOM risk.
- For batch workloads: show batch spike detection results (whether CPU/memory spikes during batch runs were detected and excluded from baseline).
- Display the rightsizing recommendation: suggested `cpu_request` and `mem_request` values in millicores and MiB.
- Show `network_intensity` flag (high network I/O detected, relevant for instance type selection).
- Show storage IOPS estimate for PVC-attached workloads.
- Allow the operator to browse all workloads for a cluster via a searchable list.

## Inputs
- **Source:** `GET /clusters/:id/workloads/:id/analysis`
- **Format:**
```json
{
  "workload_id": "string",
  "data_maturity": "MATURE | SUFFICIENT | INSUFFICIENT",
  "cpu_state": "THROTTLED | OVER_PROVISIONED | RIGHT_SIZED | UNDER_PROVISIONED",
  "cpu_util_ratio": "number",
  "mem_state": "OVER_PROVISIONED | RIGHT_SIZED | UNDER_PROVISIONED",
  "mem_util_ratio": "number",
  "oom_risk": "boolean",
  "is_java": "boolean",
  "batch_spike_detected": "boolean",
  "network_intensity": "boolean",
  "storage_iops_estimate": "number | null",
  "rightsizing": {
    "suggested_cpu_request_millicores": "number",
    "suggested_mem_request_mib": "number"
  }
}
```
- **Source:** Route parameters `cluster_id`, `workload_id` from React Router

## Outputs
- **Destination:** Rendered resource profile panels in the operator browser
- **Destination:** HTTP GET requests to backend API (read-only)

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `workload_analysis`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id/workloads/:id/analysis` | Fetch resource analysis profile for a specific workload |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` components** — `StatusBadge` (CPU state, memory state, OOM risk), `DataTable` (workload list), `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for analysis API response

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |

## Error Handling
- **`INSUFFICIENT` maturity:** A yellow contextual banner explains that the analysis is based on limited data and that rightsizing suggestions may be inaccurate; the operator is encouraged to wait for more data before approving recommendations.
- **API error:** The analysis panel shows an error card with a retry button; the workload list sidebar remains functional.
- **Null storage IOPS:** If `storage_iops_estimate` is null (workload has no PVCs), the storage row is hidden rather than showing null.

## Future Enhancements
- Side-by-side comparison of current requests vs. suggested requests with projected savings from rightsizing alone.
- Trend view: how has the `cpu_util_ratio` and `mem_util_ratio` changed over the last 7 days?
- Integration with cluster inventory to show which nodes the workload's pods are currently running on.
