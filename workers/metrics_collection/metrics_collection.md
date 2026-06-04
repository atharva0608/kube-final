# Workers: Metrics Collection

## Purpose
Metrics ingestion and aggregation job, processing batched telemetry from agent DaemonSets.

## Responsibilities
- Receives batched metrics pushed by the agent (HTTP POST handled async).
- Normalizes metric units.
- Computes rolling P50/P95 profiles and stores them in `workload_profiles`.
- Prunes metrics older than 90 days via scheduled cleanup.

## Inputs
- Queue: `queue:metrics_collection`
- Source: Agent push (HTTP POST to backend, placed on queue).
- Format: `AgentMetricsPush` payload.

## Outputs
- Destination: Time-series metric tables, `workload_profiles`.
- Format: Database rows.

## Events Produced
- N/A

## Events Consumed
- N/A (Synchronous HTTP ingestion with async processing).

## Database Tables
- Writes: `cpu_metrics`, `memory_metrics`, `network_metrics`, `filesystem_metrics`, `workload_profiles`.

## APIs
- N/A

## Dependencies
- `backend/metrics_collection`

## Configuration
- `METRICS_RETENTION_DAYS`: Retention period (default: 90).

## Error Handling
- Retries 2x immediately on DB write failure.

## Future Enhancements
- N/A
