# Cluster Inventory: StatefulSets

## Purpose
StatefulSet inventory CRUD and queries. Part of the `cluster_inventory` module.

## Responsibilities
- Persists StatefulSet inventory data from the agent.
- Analyzes `volume_claim_templates` to link PVCs to Pods implicitly.
- Tracks `ready_replicas` and `pod_management_policy`.

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
- `statefulsets` (id, cluster_id, snapshot_id, name, namespace, replicas, ready_replicas, updated_replicas, volume_claim_templates, pod_management_policy, active_rolling_update, collected_at).

## APIs
- `GET /clusters/:id/statefulsets`

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Standard API errors.

## Future Enhancements
- N/A
