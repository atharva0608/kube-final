# Cluster Inventory: Namespaces

## Purpose
Namespace inventory CRUD and queries. Part of the `cluster_inventory` module.

## Responsibilities
- Persists Namespace metadata.
- Enables filtering workloads by Namespace and reading Namespace-level annotations.

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
- `namespaces` (id, cluster_id, snapshot_id, name, labels, annotations, phase, collected_at).

## APIs
- `GET /clusters/:id/namespaces`

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Standard API errors.

## Future Enhancements
- N/A
