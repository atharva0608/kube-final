# Cluster Inventory: DaemonSets

## Purpose
DaemonSet inventory CRUD and queries. Part of the `cluster_inventory` module.

## Responsibilities
- Persists DaemonSet inventory data from the agent.
- Serves DaemonSet data to the frontend and Phase 2 analysis.
- Tracks `number_available` vs `desired_number_scheduled`.
- Flags DaemonSets as ineligible for Spot instance replacement.

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
- `daemonsets` (id, cluster_id, snapshot_id, name, namespace, number_available, desired_number_scheduled, update_strategy, active_rolling_update, collected_at).

## APIs
- `GET /clusters/:id/daemonsets`

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Standard API errors.

## Future Enhancements
- N/A
