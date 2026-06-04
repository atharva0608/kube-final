# Backend: ITN Handler

## Purpose
Processes AWS Spot Interruption Notices (ITN) and EC2 Rebalance Recommendations reported by the Agent DaemonSet.

## Responsibilities
- Receives immediate ITN alerts via `POST /api/v1/agents/:id/itn`.
- Achieves a strict <2 second processing SLA to maximize the 2-minute AWS termination window.
- Avoids cold-start delays by maintaining a pre-established connection pool.
- Triggers Phase 4 Execution emergency evacuation logic immediately.
- Writes records to `itn_events` for audit and debugging.

## Inputs
- Source: Agent DaemonSet.
- Format: JSON.

## Outputs
- Destination: Phase 4 Execution, `itn_events` table.
- Format: BullMQ trigger, Database insert.

## Events Produced
- `cluster.itn_received`

## Events Consumed
- N/A

## Database Tables
- `itn_events` (id, cluster_id, node_id, node_name, instance_id, notice_type, termination_time, detected_at).

## APIs
- `POST /api/v1/agents/:id/itn`

## Dependencies
- Phase 4 Execution

## Configuration
- N/A

## Error Handling
- Retries internally if database insert fails, but immediately triggers execution to avoid delaying the evacuation.

## Future Enhancements
- Aggregating rebalance recommendations to preemptively move workloads before ITNs are issued.
