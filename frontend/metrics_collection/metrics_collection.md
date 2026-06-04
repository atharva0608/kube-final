# metrics_collection

## Purpose
The metrics collection module renders visualisation dashboards for the resource usage metrics that the BalanceKube agent collects from each cluster. It allows operators to verify that metrics data is fresh and sufficiently mature before trusting workload analysis and rightsizing recommendations.

## Responsibilities
- Display per-workload CPU and memory usage over time as P50 and P95 sparkline charts.
- Show node-level network throughput and filesystem utilisation.
- Display a metric freshness indicator: the timestamp of the most recent collection cycle and a staleness warning if data is older than the expected collection interval.
- Show the data maturity status for each workload: `MATURE` (sufficient history for reliable analysis), `SUFFICIENT` (enough for basic analysis), or `INSUFFICIENT` (too little data; recommendations will be conservative).
- Display OOMKill count and container restart count history per workload (bar chart or timeline).
- Allow the operator to select a workload from a list and view its metric detail panel.

## Inputs
- **Source:** `GET /clusters/:id/metrics/:workload_id`
- **Format:**
```json
{
  "workload_id": "string",
  "data_maturity": "MATURE | SUFFICIENT | INSUFFICIENT",
  "last_collected_at": "ISO8601 timestamp",
  "cpu": {
    "p50_millicores": "number[]",
    "p95_millicores": "number[]",
    "timestamps": "string[]"
  },
  "memory": {
    "p50_mib": "number[]",
    "p95_mib": "number[]",
    "timestamps": "string[]"
  },
  "network": {
    "rx_bytes_per_sec": "number[]",
    "tx_bytes_per_sec": "number[]",
    "timestamps": "string[]"
  },
  "filesystem": {
    "read_bytes_per_sec": "number[]",
    "write_bytes_per_sec": "number[]",
    "timestamps": "string[]"
  },
  "oomkill_count": "number",
  "restart_count": "number",
  "restart_history": [{ "timestamp": "string", "reason": "string" }]
}
```
- **Source:** Route parameters `cluster_id`, `workload_id` from React Router

## Outputs
- **Destination:** Rendered sparkline and bar charts in the operator browser
- **Destination:** HTTP GET requests to backend API (read-only)

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `cpu_metrics`, `memory_metrics`, `network_metrics`, `filesystem_metrics`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id/metrics/:workload_id` | Fetch full metric time series and maturity status for a workload |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` components** — Chart components (Recharts or equivalent for sparklines and bar charts), `StatusBadge` (data maturity), `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for metric API response parsing

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |
| `VITE_METRICS_STALENESS_THRESHOLD_MIN` | Minutes after which a freshness warning is shown | `60` |

## Error Handling
- **Stale data warning:** If `last_collected_at` is more than `VITE_METRICS_STALENESS_THRESHOLD_MIN` minutes ago, a yellow warning banner is shown above all charts.
- **`INSUFFICIENT` maturity:** A contextual tooltip explains that fewer than the minimum required data points exist, and that the analysis module will apply conservative assumptions.
- **API error:** Each workload's metric panel shows an inline error state with a retry button; the workload list sidebar remains functional.
- **No data:** If metrics arrays are empty (first collection cycle not yet complete), the charts show an empty-state message rather than empty axes.

## Future Enhancements
- Time range selector (last 1h, 6h, 24h, 7d) for metric charts.
- Percentile selector (P50, P95, P99) per chart.
- Overlay request vs actual usage on the same chart for immediate rightsizing insight.
- Anomaly detection highlighting (auto-highlight OOMKill spikes on the timeline).
