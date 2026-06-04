# Agent: Metrics Collection

## Purpose
Collects time-series performance data from the cluster to feed into Phase 2 resource analysis.

## Responsibilities
- The Agent DaemonSet queries the Kubelet Summary API (or Metrics Server as fallback) every 60s.
- Formats CPU, memory, network, and filesystem metrics.
- Pushes batched metrics to the backend asynchronously.

## Inputs
- Source: Kubelet Summary API (`/stats/summary`).
- Format: JSON.

## Outputs
- Destination: Backend API.
- Format: HTTP POST (`POST /agents/:id/metrics`).

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Calls `POST /agents/:id/metrics` (Backend).

## Dependencies
- Kubelet API.

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `COLLECTION_INTERVAL_SECONDS` | `60` | How often metrics are collected from the Kubelet Summary API. |
| `METRICS_MAX_CONSECUTIVE_NULLS` | `3` | Maximum consecutive null collection cycles before a node is excluded from workload_profiles percentile computation. |

## Error Handling
- If Kubelet data is unavailable for a node, null metrics are recorded (does not crash the agent or block inventory snapshots).
- **Null metric cycle limit:** If a node returns null metrics for more than `METRICS_MAX_CONSECUTIVE_NULLS` (default: 3) consecutive collection cycles, that node's metrics are excluded from the `workload_profiles` percentile computation for the current window. A null cycle does NOT count as data toward the 7-day maturity window — only cycles with valid metric values contribute. This prevents a node that repeatedly bounces from silently polluting the maturity calculation.
- **valid_sample_count tracking:** The `workload_profiles` table tracks a `valid_sample_count` field (count of collection cycles with non-null metrics that contributed to the current percentile window). Phase 2 resource analysis reads `valid_sample_count` alongside `window_days` to verify that actual sample coverage is sufficient — a workload with 7 days in the window but only 3 valid samples is still treated as `data_maturity=INSUFFICIENT`.

## Future Enhancements
- cAdvisor direct scraping for higher resolution.
