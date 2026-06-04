# Workers: Snapshot Assembly

## Purpose
`assembled_snapshots` builder job. Fuses data from the agent, account collector, and pricing models into a single, immutable snapshot for Phase 2 analysis.

## Responsibilities
- Joins 3 data layers: node snapshots (from agent) + node enrichment (from AWS/account collector) + global pricing.
- Performs a LEFT JOIN—assembly never blocks on enrichment data.
- Computes `cluster_hash` from `sha256(node_types + node_counts + az_distribution)`.
- Writes the immutable `assembled_snapshot` record.
- Publishes the `cluster.collected` event to trigger Phase 2.

## Inputs
- Source: Internal trigger (agent event—backend receives snapshot POST, triggering this worker).
- Format: Internal queue message.

## Outputs
- Destination: `assembled_snapshots` table, NATS events.
- Format: Snapshot row, `cluster.collected` event.

## Events Produced
- `cluster.collected`: Triggers Phase 2 review/classification.

## Events Consumed
- N/A (Triggered directly via queue by `backend/snapshot_assembly` API handler).

## Database Tables
- Writes: `assembled_snapshots`.

## APIs
- N/A

## Dependencies
- `backend/snapshot_assembly`

## Configuration
- N/A

## Error Handling
- Retries 3x. 
- Idempotent: If a snapshot for `(cluster_id, collected_at_window)` already exists, the job is a no-op.

## Future Enhancements
- Streaming snapshot assembly for massive clusters.
