# rollback

## Purpose
Creates immutable point-in-time snapshots of cluster infrastructure state immediately before Phase 4 execution begins, and restores that state if execution fails or is aborted by an operator. Rollback undoes what BalanceKube wrote (node labels, taints, cordons) — it does not attempt to move running pods, which are already managed by their pod controllers on newly provisioned nodes.

## Responsibilities
- Capture a **pre-execution snapshot** immediately before any cluster changes are made by the execution engine. The snapshot is immutable for the lifetime of the execution run.
- Snapshot captures: current node pool composition (instance types, counts, AZ distribution), all active workload placements (pod-to-node mappings), all active PVC bindings (zone and node), all HPA configurations (min/max replicas, current replica counts).
- Retain the snapshot until execution is confirmed successful — on success, the snapshot is marked `retired`. On rollback, the snapshot is marked `restored`.
- Trigger rollback on: health validation failure, any execution step failure, or operator-triggered abort.
- Execute the restoration sequence in a fixed order: (1) restore node labels and taints to pre-execution state, (2) remove cordons from all nodes that were cordoned during execution, (3) verify that the cluster has returned to its pre-execution state.
- Validate recovery: confirm node labels match the pre-execution snapshot, confirm no nodes remain cordoned, confirm all pods that were Running before execution are still Running (or have recovered).
- Store snapshot payload as an immutable JSONB blob referenced by a storage handle.
- **Snapshot freshness guard:** Before capturing the pre-execution snapshot, the rollback module checks `assembled_snapshots.collected_at` for the cluster. If the most recent assembled snapshot is older than `ROLLBACK_MAX_SNAPSHOT_AGE_MINUTES` (default: 10), execution is aborted with `failure_reason='stale_cluster_snapshot'`. Operators should wait for a fresh collection cycle before re-triggering execution. This prevents the rollback snapshot from capturing stale inventory that does not reflect the current cluster state.

## Inputs
- **Source:** Internal call from `execution` module at the start of each execution run — pre-execution snapshot capture.
- **Source:** `execution.failed` internal event — triggers the restoration sequence.
- **Source:** Operator-triggered abort via the execution abort API (handled by the `execution` module, which calls rollback directly).
- **Source:** `nodes`, `pods`, `pvcs`, `statefulsets` tables — live cluster state captured at snapshot time.
- **Source:** HPA configurations — captured via Kubernetes API at snapshot time.
- **Format:** Cluster state captured as structured JSONB; stored in `rollback_snapshots.payload_ref` (reference to immutable JSONB blob in object storage or PostgreSQL JSONB column).

## Outputs
- **Destination:** `rollback_snapshots` table — one row per execution run, tracking snapshot lifecycle (`pending → active → retired / restored`).
- **Destination:** Kubernetes API — node label and taint restore operations, cordon removal.
- **Destination:** `execution_history` table (via the execution module) — updated with `rollback_reason` on restoration.
- **Format:** Restoration operations are applied directly via the Kubernetes API through the agent's mTLS channel. No NATS events are published by rollback itself.

## Events Produced
- **N/A** — Rollback does not publish its own events. The `execution` module publishes `execution.completed` (with `status=rolled_back`) after rollback completes, providing the external event signal.

## Events Consumed
| Event | Action |
|---|---|
| `execution.failed` (internal) | Triggers the restoration sequence: restore node labels/taints, remove cordons, run recovery validation. This is an internal module-to-module call, not a NATS event. |

## Database Tables

**Tables this module owns (writes to):**
| Table | Description |
|---|---|
| `rollback_snapshots` | One row per execution run. Columns: `id` (UUID), `execution_id` (FK → `execution_history`), `cluster_id`, `payload_ref` (JSONB or object-storage URI — immutable pre-execution state), `created_at`, `status` (ENUM: `pending`, `active`, `retired`, `restored`). |

**Tables this module reads (read-only):**
| Table | Source Domain |
|---|---|
| `nodes`, `pods`, `pvcs`, `statefulsets` | Cluster Inventory (read at snapshot time) |
| `execution_history` | Execution |

## APIs
- **N/A** — Rollback has no public REST API. It is invoked exclusively as an internal component of the `execution` module. Operator visibility into rollback outcomes is provided through `GET /clusters/:id/executions/:exec_id` (owned by the `execution` module), which includes `rollback_reason` in the response.

## Snapshot Payload Structure
The pre-execution snapshot captures the following state as an immutable JSONB blob:

```json
{
  "snapshot_version": "1",
  "captured_at": "2024-06-04T08:00:00Z",
  "node_pool_composition": [
    {
      "node_id": "uuid",
      "instance_type": "m5.large",
      "az": "us-east-1a",
      "capacity_type": "ON_DEMAND",
      "labels": { "balancekube.io/managed": "false" },
      "taints": [],
      "cordoned": false,
      "allocatable_cpu_millicores": 1900,
      "allocatable_memory_mib": 7168
    }
  ],
  "workload_placements": [
    { "workload_id": "uuid", "pod_name": "app-7d9f4-xxxxx", "node_id": "uuid", "lifecycle": "ON_DEMAND" }
  ],
  "pvc_bindings": [
    { "pvc_id": "uuid", "pvc_name": "data-0", "az": "us-east-1a", "node_id": "uuid" }
  ],
  "hpa_configurations": [
    { "workload_id": "uuid", "min_replicas": 2, "max_replicas": 10, "current_replicas": 3 }
  ]
}
```

## Restoration Sequence
Rollback always executes the following steps in order:

1. **Restore node labels** — Re-apply the pre-execution label set to each node that was modified. Uses a `PUT` (full replace) rather than a `PATCH` to guarantee no residual BalanceKube labels remain.
2. **Restore node taints** — Re-apply the pre-execution taint set to each node. Removes any taints added by the execution engine.
3. **Remove cordons** — Call `UNCORDON` for every node that was cordoned during execution. This ensures new pods can be scheduled normally.
4. **Recovery validation** — Verify:
   - Node labels match the pre-execution snapshot.
   - No nodes remain in `cordoned` state.
   - All pods that were in `Running` state before execution remain `Running` (or have naturally recovered via their pod controllers within a 5-minute grace window).

## What Rollback Does NOT Do
- **Does not move running pods.** Pod controllers (Deployments, StatefulSets) will have already created replacement pods on newly provisioned Spot nodes by the time rollback runs. Rolling back node labels prevents **future** pods from being scheduled there but does not terminate or migrate currently running pods. This is intentional — forcibly moving pods would cause additional disruption.
- **NodeClaim cleanup on rollback:** On rollback, BalanceKube annotates any NodeClaim it provisioned (identified via `balancekube.io/execution-id` annotation) with `balancekube.io/rollback-pending=true` and **cordons** the Spot node (prevents new pod scheduling). It then uses the **Kubernetes Eviction API** (not taints — to honour the hard rule against force-delete) to evict each running pod one at a time. PDB constraints are fully respected using the same retry logic as the normal drain process (`ROLLBACK_NODECLAIM_PDB_MAX_RETRIES`, default: 5 attempts at `DRAIN_PDB_RETRY_INTERVAL_SECONDS` spacing). If PDB blocks prevent eviction after max retries, `rollback_snapshots.status` is set to `restored_partial` with `failure_details.pdb_blocked_pods` listing the stuck pods, and a critical alert is raised for operator intervention. Once the node has drained successfully (zero running BalanceKube-managed pods, verified via pod watch), the `NodeClaim` deletion is triggered by the rollback module. This exception to 'rollback does not move running pods' applies exclusively to NodeClaims created by BalanceKube itself — pre-existing Spot nodes are never drained by rollback.
- **Does not modify HPA configurations.** HPA is read-only for BalanceKube; any HPA state captured in the snapshot is for validation purposes only.

## Dependencies
- **execution** module — the only caller; rollback is invoked as a direct function call (not via events) to maintain synchronous, ordered restoration.
- **agent** — restoration operations are sent to the agent over mTLS as signed commands. The agent applies label/taint changes and uncordon operations on the actual nodes.
- **shared/db** — PostgreSQL client; `rollback_snapshots` status transitions are transactional.
- **shared/logger** — structured logging with `execution_id`, `cluster_id`, `rollback_step` context.

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `ROLLBACK_RECOVERY_GRACE_MINUTES` | `5` | Grace window for pods to return to `Running` state after node uncordon before recovery validation fails. |
| `ROLLBACK_SNAPSHOT_RETENTION_DAYS` | `30` | Number of days `retired` rollback snapshots are retained before purge. Active and `restored` snapshots are never automatically purged. |
| `ROLLBACK_VALIDATION_POLL_INTERVAL_SECONDS` | `15` | Polling interval during recovery validation. |
| `ROLLBACK_MAX_VALIDATION_ATTEMPTS` | `20` | Maximum number of validation polls (20 × 15s = 5 minutes) before validation is declared failed and operator alerted. |
| `ROLLBACK_NODECLAIM_PDB_MAX_RETRIES` | `5` | Maximum PDB retry attempts during NodeClaim drain-back eviction. Lower than execution drain since rollback is already a degraded state. |
| `ROLLBACK_MAX_SNAPSHOT_AGE_MINUTES` | `10` | Maximum age (minutes) of the most recent assembled snapshot before execution is aborted with stale_cluster_snapshot. |

## Error Handling
- **Restoration step failure:** If restoring node labels or removing a cordon fails, the failure is logged with full context (`node_id`, `cluster_id`, `execution_id`) and the restoration continues with the remaining nodes. No partial restoration is aborted — all nodes are attempted. The final `rollback_snapshots.status` is set to `restored` (partial) with a `failure_details` JSONB field enumerating which nodes could not be restored.
- **Agent unreachable during rollback:** Restoration operations are retried for up to 10 minutes (30s intervals). If the agent remains unreachable, the `rollback_snapshots` row is set to `restored` (pending-agent) and a critical alert is raised for operator intervention.
- **Recovery validation failure:** If pods do not return to `Running` within the grace window, an alert is raised via `notifications` module. The `rollback_snapshots.status` remains `restored` rather than reverting — the cluster state has been best-effort restored; manual operator investigation is required.
- **Snapshot capture failure (pre-execution):** If the pre-execution snapshot cannot be written to `rollback_snapshots`, execution is **aborted immediately** and no cluster changes are made. This is the strictest safety gate — execution must never proceed without a valid rollback snapshot.

## Future Enhancements
- **Selective rollback:** Allow rollback of individual execution steps rather than the entire run, enabling partial recovery for multi-step executions where only later steps failed.
- **NodeClaim cleanup:** Automatically delete orphaned Karpenter `NodeClaims` created by BalanceKube when rollback is triggered, rather than leaving them for natural Karpenter cleanup.
- **Snapshot compression:** Compress large snapshot payloads (> 1MB) using gzip before storing in PostgreSQL JSONB to reduce storage costs for clusters with many nodes.
- **Rollback dry-run:** Expose a `POST /clusters/:id/executions/:exec_id/rollback/simulate` endpoint that shows what label/taint changes would be made without applying them, for operator verification before triggering a manual rollback.
