# Cluster Inventory: Nodes

## Purpose
Node inventory CRUD and queries. Stores per-node records from agent inventory pushes, providing a complete view of the cluster's compute capacity and topology.

## Responsibilities
- Persists node inventory data from the agent.
- Serves node data to the frontend and other backend domains.
- Detects transitions to `NotReady` that might trigger drift events.

## Inputs
- Source: Agent inventory push (via `POST /agents/:id/inventory`).
- Format: `NodeRecord` JSON schema.

## Outputs
- Destination: Frontend UI and Phase 2/3 engines (via assembled snapshots).
- Format: Node JSON API responses.

## Events Produced
- N/A (Triggers Phase 3 drift detection indirectly via state change).

## Events Consumed
- N/A

## Database Tables
- `nodes` (id, cluster_id, snapshot_id, name, instance_type, az, capacity_cpu_m, capacity_memory_mi, allocatable_cpu_m, allocatable_memory_mi, labels, taints, conditions, karpenter_nodepool, lifecycle, collected_at) - Owned.

## APIs
- `GET /clusters/:id/nodes` (List nodes, filterable by az, instance_type, lifecycle).

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Follows standard API error handling.

## Future Enhancements
- N/A
