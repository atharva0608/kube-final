# Metrics Collection: Filesystem

## Purpose
Filesystem metrics storage and querying module.

## Responsibilities
- Writes normalized Filesystem datapoints (used vs capacity) to the database.
- Links filesystem metrics to PVCs where possible.

## Inputs
- Source: Ingestion worker.
- Format: Normalized metric objects.

## Outputs
- Destination: `filesystem_metrics` table, API responses.
- Format: Database rows, JSON responses.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `filesystem_metrics` (id, cluster_id, node_id, pvc_id, used_gi, capacity_gi, collected_at).

## APIs
- `GET /clusters/:id/metrics/filesystem`

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Standard API errors.

## Future Enhancements
- N/A
