# Agent: Cluster Inventory Collection

## Purpose
Collects a full point-in-time snapshot of Kubernetes resources from the cluster and POSTs it to the backend inventory endpoint.

## Responsibilities
- Collects nodes, pods, deployments, statefulsets, daemonsets, PVCs, PDBs, and namespaces via the Kubernetes API.
- Assembles an `InventoryPayload` and POSTs to `POST /api/v1/agents/:id/inventory`.
- Retries on network failure using the same `collection_cycle_id` for all retry attempts.

## collection_cycle_id Generation
- A single `collection_cycle_id` UUID is generated at the start of each collection trigger (i.e., when the timer fires or the backend sends a `PUSH_INVENTORY` instruction).
- This UUID is stored in agent memory for the duration of the collection attempt.
- On any network failure or timeout, the **same** `collection_cycle_id` is reused for all retry attempts. This allows the backend to detect idempotent re-delivery: if the original request succeeded but the response was lost, the backend returns 200 with the existing `snapshot_id` rather than 409.
- A **new** `collection_cycle_id` is only generated on the next independent collection trigger (next timer tick or next `PUSH_INVENTORY` instruction). Never generate a new `collection_cycle_id` on retry.

## Inputs
- Source: Kubernetes API (in-cluster).
- Format: Kubernetes API responses.

## Outputs
- Destination: Backend API `POST /api/v1/agents/:id/inventory`.
- Format: JSON InventoryPayload.

## Events Produced
- N/A

## Events Consumed
- N/A (triggered by internal timer or heartbeat `PUSH_INVENTORY` instruction).

## Database Tables
- N/A

## APIs
- Calls `POST /api/v1/agents/:id/inventory` (Backend).

## Dependencies
- Kubernetes in-cluster API.
- Agent heartbeat module (receives PUSH_INVENTORY instruction).

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `COLLECTION_INTERVAL_SECONDS` | `300` | How often a full inventory collection is triggered. Overridden by backend config returned at registration. |

## Error Handling
- Retries with exponential backoff on network failure. Same `collection_cycle_id` is reused on all retries.
- If the backend returns 409 with `SNAPSHOT_ALREADY_EXISTS` AND the `collection_cycle_id` matches, the agent treats this as a success (idempotent delivery).
- If the backend returns 413 `INVENTORY_LIMIT_EXCEEDED`, the agent respects the `Retry-After` header and does not retry until that time has elapsed.

## Future Enhancements
- Incremental/delta inventory pushes.
