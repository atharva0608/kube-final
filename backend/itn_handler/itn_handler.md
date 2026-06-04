# Backend: ITN Handler

## Purpose
Processes AWS Spot Interruption Notices (ITN) and EC2 Rebalance Recommendations reported by the Agent DaemonSet.

## Responsibilities
- Receives immediate ITN alerts via `POST /api/v1/agents/:id/itn`.
- Achieves a strict <2 second *backend processing* SLA (record to DB + enqueue BullMQ job) to maximise the 2-minute AWS termination window.
- Maintains a pre-established connection pool to avoid cold-start delays.
- Immediately enqueues a high-priority BullMQ job `itn-evacuation-{cluster_id}-{node_name}` with `priority: 1` (highest available).
- Triggers Phase 4 in `ITN_EMERGENCY` mode via the BullMQ job.
- Writes records to `itn_events` for audit and debugging.

## ITN Emergency Execution Path

On receiving a valid ITN:
1. Backend writes to `itn_events` and immediately returns HTTP 200 to the agent (within the 2s processing SLA).
2. A high-priority BullMQ job is enqueued (`priority: 1`).
3. The execution worker picks up the job and triggers Phase 4 in `ITN_EMERGENCY` mode:
   - No recommendation approval is required — the ITN is implicit pre-authorization.
   - Scope is limited to the single terminating node only.
   - Lightweight rollback snapshot captured (terminating node labels/taints/pods only — not full cluster).
   - Steps: `APPLY_NODE_TAINT` → `CREATE_KARPENTER_NODECLAIM` (only if `karpenter_control_mode=managed` AND no spare capacity) → `DRAIN_SOURCE_NODE` → `VERIFICATION`.
   - Writes to `execution_history` with `trigger=itn_emergency`.
4. **Timing:** The 2-minute AWS window is best-effort. Pre-drain overhead is 8–30 seconds depending on system load. If the window expires before evacuation completes, the agent aborts and annotates remaining pods with `balancekube.io/itn-incomplete=true`.
5. **observe-mode behavior:** When `karpenter_control_mode=observe`, no capacity is provisioned. Pods reschedule onto existing cluster headroom. The operator notification sent on ITN receipt includes: 'ITN evacuation initiated. Node provisioning is disabled (observe mode) — pods will reschedule onto existing capacity only.' Operators who set observe mode accept that ITN handling depends entirely on pre-existing cluster headroom.

## Inputs
- Source: Agent DaemonSet.
- Format: JSON.

## Outputs
- Destination: Phase 4 Execution, `itn_events` table.
- Format: BullMQ trigger, Database insert.

## Events Produced
- `cluster.itn_received` — Published immediately after the `itn_events` row is written. Consumed by the execution worker to trigger ITN_EMERGENCY mode.

## Events Consumed
- N/A

## Database Tables
- `itn_events` (id, cluster_id, node_id, node_name, instance_id, notice_type, termination_time, detected_at). Retention: 30 days (pruned by the same cleanup job that handles spot_prices).

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
