# Metrics Collection: Network

## Purpose
Network metrics storage and querying module.

## Responsibilities
- Writes normalized Network datapoints to the database (rx_kbps, tx_kbps).
- Provides APIs for retrieving Network time-series data.

## Inputs
- Source: Ingestion worker.
- Format: Normalized metric objects.

## Outputs
- Destination: `network_metrics` table, API responses.
- Format: Database rows, JSON responses.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `network_metrics` (id, cluster_id, node_id, rx_kbps, tx_kbps, collected_at).

## APIs
- `GET /clusters/:id/metrics/network`

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Standard API errors.

## Future Enhancements
- Per-pod network metrics via eBPF.
