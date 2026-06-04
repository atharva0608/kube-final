# Cluster Inventory: Pods

## Purpose
Pod inventory CRUD and queries. Stores workload state grouped by top-level controllers, providing the foundation for workload classification and resource analysis.

## Responsibilities
- Persists pod inventory data from the agent (only `Running` pods).
- Groups pods by top-level controller (Deployment, StatefulSet, DaemonSet) into `WorkloadSnapshot`s.
- Tracks active rolling updates (`updatedReplicas != replicas`).

## Inputs
- Source: Agent inventory push (via `POST /agents/:id/inventory`).
- Format: `PodRecord` JSON schema.

## Outputs
- Destination: Frontend UI and Phase 2/3 engines (via assembled snapshots).
- Format: Pod/Workload JSON API responses.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `pods` (id, cluster_id, snapshot_id, name, namespace, owner_kind, owner_name, node_id, phase, req_cpu_m, req_memory_mi, lim_cpu_m, lim_memory_mi, labels, annotations, affinity, topology_spread, node_selector, tolerations, active_rolling_update, collected_at) - Owned.

## APIs
- `GET /clusters/:id/pods` (List pods, filterable by namespace, owner, status).

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Follows standard API error handling.

## Future Enhancements
- N/A
