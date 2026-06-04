# Agent

## Purpose
Root agent documentation. The BalanceKube Agent is an in-cluster Go application deployed via a single Helm chart, serving as the bridge between the customer's Kubernetes cluster and the BalanceKube platform.

## Responsibilities
- Orchestrates the two main components: Agent Controller (Deployment, leader-elected) and Agent DaemonSet (one pod per node).
- Operates with strict zero-write RBAC permissions (get, list, watch only) to limit blast radius.
- Uses HTTPS with mTLS to communicate with the backend.
- Does NOT require AWS credentials, database access, or Redis access.

## Inputs
- Source: Kubernetes API Server, Backend execution plans.
- Format: K8s objects, JSON execution plans.

## Outputs
- Destination: Backend Platform API.
- Format: HTTP POST requests (Inventory, Metrics, Heartbeats).

## Events Produced
- N/A (Agent communicates via REST, backend converts to events).

## Events Consumed
- N/A

## Database Tables
- N/A (Agent has no database access).

## APIs
- N/A (Agent acts as a client to the backend API).

## Dependencies
- `controller-runtime` (Go).

## Configuration
- `BACKEND_URL`: URL of the BalanceKube platform.
- `REGISTRATION_TOKEN`: Short-lived token used on first boot.

## Error Handling
- Follows standard exponential backoff for network drops.

## Future Enhancements
- eBPF-based metrics collection in the DaemonSet.
