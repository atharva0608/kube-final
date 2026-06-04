# Metrics Collection: CPU

## Purpose
CPU metrics storage and querying module.

## Responsibilities
- Writes normalized CPU datapoints to the database.
- Provides APIs for retrieving CPU time-series data for a given pod or node.

## Inputs
- Source: Ingestion worker.
- Format: Normalized metric objects.

## Outputs
- Destination: `cpu_metrics` table, API responses.
- Format: Database rows, JSON responses.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `cpu_metrics` (id, cluster_id, pod_id, node_id, value_m, source, collected_at).

## APIs
- `GET /clusters/:id/metrics/cpu`

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Standard API errors.

## Future Enhancements
- Downsampling for historical queries.
