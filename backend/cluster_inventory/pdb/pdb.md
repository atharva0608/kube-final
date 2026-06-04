# Cluster Inventory: PDBs

## Purpose
PodDisruptionBudget inventory CRUD and queries. Part of the `cluster_inventory` module.

## Responsibilities
- Persists PDB inventory data from the agent.
- Tracks `disruptions_allowed` to determine if a workload can be safely drained.

## Inputs
- Source: Agent inventory push.
- Format: JSON.

## Outputs
- Destination: Backend and Frontend.
- Format: API responses.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `pdbs` (id, cluster_id, snapshot_id, name, namespace, selector, min_available, max_unavailable, current_healthy, desired_healthy, disruptions_allowed, collected_at).

## APIs
- `GET /clusters/:id/pdbs`

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Standard API errors.

## Future Enhancements
- N/A
