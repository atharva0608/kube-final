# Agent: Health Reporting

## Purpose
Monitors the agent's internal health and reports diagnostics to the backend.

## Responsibilities
- Tracks internal queue depths, API Server latency, and memory usage.
- Embeds diagnostic summaries into the regular heartbeat payload.
- Provides an internal `/healthz` endpoint for Kubernetes liveness/readiness probes.

## Inputs
- Source: Internal agent metrics.
- Format: Go memory stats, latency timers.

## Outputs
- Destination: Heartbeat payload, `/healthz` response.
- Format: JSON, HTTP 200 OK.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Exposes `GET /healthz` (Internal K8s probe).

## Dependencies
- N/A

## Configuration
- Probe timeouts.

## Error Handling
- Fails `/healthz` if disconnected from the API server for > 3 minutes, forcing a pod restart.

## Future Enhancements
- Prometheus `/metrics` endpoint for local cluster scraping.
