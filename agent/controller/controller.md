# Agent: Controller

## Purpose
The primary `controller-runtime` manager that owns all Kubernetes reconciliation loops and coordinates backend communication.

## Responsibilities
- Implements leader election via Kubernetes Lease to ensure only one active Controller pod.
- Maintains in-memory `NodeMap` and `WorkloadMap`.
- Performs paginated LIST operations on startup, then switches to WATCH streams.
- Rebuilds state gracefully on `410 Gone` errors (logged as `WATCH_REBASE`).

## Inputs
- Source: Kubernetes API Server.
- Format: K8s API responses.

## Outputs
- Destination: In-memory state, downstream modules.
- Format: Internal Go structs.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Exposes internal `/healthz` for liveness/readiness probes.

## Dependencies
- Kubernetes client-go.

## Configuration
- Standard K8s RBAC limits.

## Error Handling
- On network drop or EOF: sleeps 2s, reconnects from last known `resourceVersion`.

## Future Enhancements
- N/A
