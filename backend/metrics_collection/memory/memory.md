# Metrics Collection: Memory

## Purpose
Memory metrics storage and querying module.

## Responsibilities
- Writes normalized Memory datapoints to the database.
- Provides APIs for retrieving Memory time-series data for a given pod or node.

## Inputs
- Source: Ingestion worker.
- Format: Normalized metric objects.

## Outputs
- Destination: `memory_metrics` table, API responses.
- Format: Database rows, JSON responses.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `memory_metrics` (id, cluster_id, pod_id, node_id, value_mi, source, collected_at).

## APIs
- `GET /clusters/:id/metrics/memory`

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Standard API errors.

## Future Enhancements
- Downsampling for historical queries.
