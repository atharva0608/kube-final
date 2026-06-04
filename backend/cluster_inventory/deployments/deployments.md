# Cluster Inventory: Deployments

## Purpose
Deployment inventory CRUD and queries. Part of the `cluster_inventory` module, managing the Kubernetes Deployment resources collected by the agent.

## Responsibilities
- Persists Deployment inventory data from the agent.
- Serves Deployment data to the frontend and Phase 2 analysis.
- Tracks `replicas`, `available_replicas`, and `updated_replicas` to detect active rollouts.

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
- `deployments` (id, cluster_id, snapshot_id, name, namespace, replicas, available_replicas, updated_replicas, selector, labels, annotations, active_rolling_update, collected_at).

## APIs
- `GET /clusters/:id/deployments`

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Standard API errors.

## Future Enhancements
- N/A
