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
- Collection interval: 60s.

## Error Handling
- If Kubelet data is unavailable for a node, null metrics are recorded (does not crash the agent or block inventory snapshots).

## Future Enhancements
- cAdvisor direct scraping for higher resolution.
