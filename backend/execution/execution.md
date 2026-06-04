# execution

## Purpose
Orchestrates safe, reversible Spot node provisioning and workload migration for clusters where an operator has explicitly approved a recommendation. Phase 4 never modifies application workload specs — it operates exclusively on node infrastructure (labels, taints, cordons) and relies on Kubernetes pod controllers to reschedule pods onto the new Spot nodes through natural rolling behaviour.

## Responsibilities
- Consume `recommendation.approved` events and verify pre-conditions before any cluster changes begin.
- Acquire a per-cluster **execution lock** (`execution_locks` table) to prevent concurrent execution runs.
- Validate the **3-part plan identity** (`snapshot_id`, `analysis_version`, `cluster_hash`); abort and return to Phase 3 if any component mismatches.
- **E6.5 resource_version recheck:** Immediately before generating the execution plan (after the 3-part plan identity check passes), Phase 4 reads the `workload_resource_versions` JSONB from `recommendation_store` (captured at approval time from the assembled snapshot — never via a live K8s API call) and compares each workload's stored `resourceVersion` against the `resourceVersion` in the most recent assembled snapshot for the cluster. If any workload's `resourceVersion` has changed, it indicates a post-approval deployment or rollout occurred. Phase 4 aborts execution for that workload's group with `failure_reason='post_approval_deployment_detected'` and surfaces it to the operator. Other groups not affected by the changed workload proceed normally.
- Resolve **intent** for each workload using a strict priority order: `workload_config.placement_intent` → application group (operator-manual) → application group (template pattern) → developer `nodeAffinity` (read-only) → `topologySpreadConstraints` (read-only) → PVC zone binding → `node_selector`/`tolerations` (read-only).
- Determine global execution order: LOW/MEDIUM criticality groups first; never drain two nodes in the same AZ simultaneously; groups with no shared drain candidates run concurrently.
- Build and **HMAC-sign** the execution plan before dispatching to the agent; agent verifies the signature before acting.
- Execute each step type: `VERIFY_NODE_CAPACITY`, `CREATE_KARPENTER_NODECLAIM`, `APPLY_NODE_LABELS`, `APPLY_NODE_TAINT`, `DRAIN_SOURCE_NODE`, `DRAIN_STATEFUL_REPLICA`, `UNCORDON_NODE`, `VERIFICATION`.
- Support three execution modes: `OBSERVE` (dry-run, no cluster changes), `PLAN_ONLY` (build plan, notify, await manual trigger), `PLAN_AND_EXECUTE` (full automated execution after approval).
- **ITN_EMERGENCY mode:** Triggered by `cluster.itn_received` event (not `recommendation.approved`). No recommendation approval is required — the ITN is treated as implicit pre-authorization. Scope is limited to the single terminating node only. Pre-drain steps: lightweight node-only rollback snapshot capture (captures only the terminating node's labels, taints, and pod list — not the full cluster state — to minimise pre-drain latency), lock acquisition. Steps: `APPLY_NODE_TAINT` (NoSchedule on terminating node) → `CREATE_KARPENTER_NODECLAIM` (only if `karpenter_control_mode=managed` AND no spare capacity) → `DRAIN_SOURCE_NODE` → `VERIFICATION` (pods rescheduled). If `karpenter_control_mode=observe`, no capacity is provisioned — pods reschedule onto existing headroom only. Writes to `execution_history` with `trigger=itn_emergency`. **Best-effort timing:** Pre-drain overhead is typically 8–11 seconds on a healthy system (BullMQ pickup: 1-5s, lock: <1s, snapshot: 2-5s). On heavily loaded systems, this may reach 20-30 seconds. If the 2-minute AWS termination window expires before all pods are evicted, evacuation is aborted and remaining pods are annotated with `balancekube.io/itn-incomplete=true` for operator visibility. This annotation is for audit only — AWS terminates the node regardless.
- Invoke the rollback module on any step failure or health validation failure.
- Write all outcomes to `execution_history` and publish `execution.started` / `execution.completed` events.

## Hard Rules — Phase 4 Never
| Rule | Description |
|---|---|
| No spec writes | Never writes to any `Deployment`, `StatefulSet`, or `DaemonSet` spec. |
| No affinity mutation | Never adds, modifies, or removes developer-written affinity rules or tolerations. |
| No unmanaged NodeClaims | Never creates a Karpenter `NodeClaim` when `clusters.karpenter_control_mode != 'managed'`. |
| No PDB bypass | Never evicts pods in violation of a PodDisruptionBudget. |
| No force-delete | Never force-deletes pods; uses the Eviction API only. |
| No orphaned cordons | Never leaves a node cordoned on step failure — `UNCORDON_NODE` always runs on drain failure. |
| No auto-remediation | Never auto-remediates a failed verification — surfaces the failure to the operator instead. |

## Inputs
- **Source:** `recommendation.approved` NATS event — primary trigger.
- **Source:** `recommendation_store` table — fetches the approved recommendation with `snapshot_id`, `analysis_version`, `cluster_hash`.
- **Source:** `assembled_snapshots` table — full plan payload for the approved recommendation.
- **Source:** `eligibility_verdicts`, `savings_estimates` — workload list and placement intents.
- **Source:** `nodes`, `pods`, `pvcs`, `pdbs` — live cluster state for pre-execution validation.
- **Source:** `clusters` table — `karpenter_control_mode`, `cluster_template` for NodeClaim construction.
- **Format:** PostgreSQL rows; plan dispatched to agent as HMAC-signed JSON payload over mTLS.

## Outputs
- **Destination:** `execution_history` table — one row per execution run, updated at each phase transition.
- **Destination:** `execution_locks` table — acquired at start, released at end (success or failure).
- **Destination:** NATS topics `execution.started`, `execution.completed`.
- **Destination:** Agent — HMAC-signed execution plan JSON dispatched over mTLS.
- **Format:**
  ```json
  {
    "event": "execution.completed",
    "cluster_id": "uuid",
    "execution_id": "uuid",
    "recommendation_id": "uuid",
    "status": "success",
    "nodes_provisioned": 3,
    "nodes_drained": 2,
    "workloads_migrated": 12,
    "savings_realised_monthly": 1240.50,
    "completed_at": "2024-06-04T08:45:00Z"
  }
  ```

## Events Produced
| Event | Description |
|---|---|
| `execution.started` | Emitted immediately after lock acquisition and pre-condition checks pass. Payload: `cluster_id`, `execution_id`, `recommendation_id`, `mode`, `started_at`. |
| `execution.completed` | Emitted after all steps complete (success or failure). Payload: `cluster_id`, `execution_id`, `status`, `nodes_provisioned`, `nodes_drained`, `workloads_migrated`, `savings_realised_monthly`, `failure_reason?`. |

## Events Consumed
| Event | Action |
|---|---|
| `recommendation.approved` | Triggers the full execution pipeline. Validates the recommendation exists in `approved` status, acquires the execution lock, and begins plan validation. |

## Database Tables

**Tables this module owns (writes to):**
| Table | Description |
|---|---|
| `execution_history` | One row per execution run. Columns: `execution_id` (UUID), `cluster_id`, `recommendation_id`, `status` (ENUM: `running`, `success`, `failed`, `rolled_back`, `aborted`), `started_at`, `completed_at`, `nodes_provisioned`, `nodes_drained`, `workloads_migrated`, `savings_realised_monthly`, `failure_reason`, `rollback_reason`. |
| `execution_locks` | Per-cluster mutex. Columns: `cluster_id` (PK), `acquired_at`, `expires_at`, `execution_id`. Lock TTL: 2 hours; auto-expired by the database if execution crashes without releasing. |

**Tables this module reads (read-only):**
| Table | Source Domain |
|---|---|
| `recommendation_store` | Recommendations |
| `assembled_snapshots` | Snapshot Assembly |
| `eligibility_verdicts`, `savings_estimates` | Eligibility / Recommendations |
| `nodes`, `pods`, `pvcs`, `pdbs` | Cluster Inventory |
| `clusters` | Onboarding |

## APIs
| Method | Path | Description |
|---|---|---|
| `POST` | `/clusters/:id/executions` | Manually trigger an execution run (used in `PLAN_ONLY` mode after operator approval). Body: `{ recommendation_id, mode? }`. Requires `operator` or `admin` role. |
| `GET` | `/clusters/:id/executions` | List all execution history for a cluster, ordered by `started_at` descending. |
| `GET` | `/clusters/:id/executions/:exec_id` | Retrieve full details of a specific execution run, including per-step outcomes and failure reasons. |

## Execution Step Reference
| Step Type | Description |
|---|---|
| `VERIFY_NODE_CAPACITY` | Confirms sufficient node capacity exists for workload migration before any disruptive action. **NodeClaim exemption:** Because `cluster_hash` is now computed from the *set of distinct instance_type × AZ pairs* (not node counts), provisioning a new NodeClaim of an existing instance type in an existing AZ does not change the hash. `VERIFY_NODE_CAPACITY` can safely verify capacity after `CREATE_KARPENTER_NODECLAIM` without triggering a spurious hash mismatch. |
| `CREATE_KARPENTER_NODECLAIM` | Issues a Karpenter `NodeClaim` for the target Spot instance type. Only when `karpenter_control_mode = 'managed'`. Polls every 10s, timeout 120s. 20% CPU/memory buffer applied to node sizing. |
| `APPLY_NODE_LABELS` | Applies BalanceKube-managed labels to newly provisioned Spot nodes for scheduling guidance. |
| `APPLY_NODE_TAINT` | Taints source On-Demand nodes to prevent new pods from scheduling there. |
| `DRAIN_SOURCE_NODE` | Evicts pods via Kubernetes Eviction API. PDB violation (429) → wait 30s, retry. Pre-drain delay: 10s (15s if Istio sidecar detected). |
| `DRAIN_STATEFUL_REPLICA` | Evicts individual StatefulSet replicas one at a time; waits for each to be rescheduled and Ready before proceeding. |
| `UNCORDON_NODE` | Always runs on drain failure to restore node scheduling. |
| `VERIFICATION` | Runs health validation checks post-migration. Results surfaced to operator; never auto-remediated. |

## Health Validation Thresholds
| Workload Type | Pass Criteria |
|---|---|
| `SPOT` group | ≥ 75% of pods Running on Spot within 10 minutes of drain completion. |
| `ON_DEMAND` (HIGH/CRITICAL criticality) | Zero pods on Spot nodes. |
| `MIXED` | 40–90% of pods on Spot. |
| `StatefulSet` | All replicas Ready; none Pending > 5 minutes. |

> **Partial placement anomaly tracking:** After health validation passes, Phase 4 compares the actual placement outcome to the planned placement for each workload. Pods that landed on the wrong lifecycle (e.g., on OD when Spot was planned) are recorded as `placement_anomalies` in `execution_history.placement_anomaly_details` (JSONB array). The execution is marked `success` but the reported `savings_realised_monthly` is adjusted to reflect only pods that achieved their target lifecycle. Operators can view placement anomalies via `GET /clusters/:id/executions/:exec_id` and trigger a targeted re-execution for affected workloads.

## Intent Resolution Priority Order
1. `workload_config.placement_intent` (BalanceKube-managed, highest priority)
2. Application group placement (operator-manual override)
3. Application group placement (template pattern)
4. Developer `nodeAffinity` — **READ ONLY**; conflicts raise `INTENT_CONFLICT` block
5. `topologySpreadConstraints` — **READ ONLY**
6. PVC zone binding — forces `ON_DEMAND` for the PVC's AZ
7. `node_selector` / `tolerations` — **READ ONLY**

## Capacity Provisioning Details
- `NodeClaim` spec is built from the cluster's `cluster_template` configuration stored in the `clusters` table.
- Instance types filtered to those satisfying workload CPU + memory requests with a 20% buffer.
- Karpenter `NodeClaim` status polled every 10 seconds with a 120-second timeout.
- If provisioning times out, the step is marked failed and rollback is triggered immediately.
- Capacity provisioning is skipped entirely when `karpenter_control_mode != 'managed'` — the operator is expected to have pre-provisioned nodes.

## Node Drain Details
- Uses Kubernetes Eviction API exclusively (never `kubectl delete pod --force`).
- PDB violation returns HTTP 429; execution waits 30 seconds then retries. After 10 consecutive 429 responses, drain is aborted and rollback triggered.
- Parallel drain is permitted only when target nodes are in **different AZs** AND the number of concurrently drained nodes does not exceed `max_unavailable_percent`.
- Istio detection: if Istio sidecar (`istio-proxy`) is present on pods, pre-drain delay is extended to 15 seconds (from 10 seconds) to allow Envoy graceful shutdown.
- `UNCORDON_NODE` is always executed as a compensating step on drain failure, regardless of partial progress.

## Dependencies
- **rollback** module — invoked immediately on any step failure or health validation failure.
- **drift_detection** — plan identity validated against `assembled_snapshots`; execution aborted if `cluster_hash` mismatches.
- **agent_management** — agent must be in `active` state; execution plan is HMAC-signed and sent over mTLS.
- **NATS** — for consuming `recommendation.approved` and publishing execution events.
- **Redis** — distributed execution lock as a secondary guard (in addition to `execution_locks` table).
- **shared/db** — PostgreSQL client; all step state transitions are transactional.
- **shared/logger** — structured logging with `execution_id`, `cluster_id`, `step_type` context on every line.
- **shared/crypto** — HMAC-SHA256 signing of execution plans sent to agent.
- **Lock source of truth:** PostgreSQL `execution_locks` is the authoritative source of truth for execution lock state. Redis `SET NX EX cluster:{cluster_id}:exec_lock` is a performance optimisation — a fast pre-check before the PostgreSQL query. Lock validity is always confirmed against `execution_locks` before proceeding. The Redis lock is never the final arbiter. If Redis is evicted and the key disappears while the execution is running, the execution's next lock renewal detects the missing Redis key and re-sets it from the PostgreSQL `execution_locks` row. If the PostgreSQL row shows a different `execution_id` than the current process, the current process self-aborts with `failure_reason='lock_stolen'`.

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `EXECUTION_MODE` | `PLAN_AND_EXECUTE` | Default execution mode. Options: `OBSERVE`, `PLAN_ONLY`, `PLAN_AND_EXECUTE`. |
| `NODECLAIM_POLL_INTERVAL_SECONDS` | `10` | Polling interval for Karpenter `NodeClaim` status. |
| `NODECLAIM_TIMEOUT_SECONDS` | `120` | Maximum wait time for Karpenter `NodeClaim` to reach `Ready`. |
| `DRAIN_PRE_DELAY_SECONDS` | `10` | Pre-eviction delay before starting drain. |
| `DRAIN_ISTIO_PRE_DELAY_SECONDS` | `15` | Pre-eviction delay when Istio sidecar detected. |
| `DRAIN_PDB_RETRY_INTERVAL_SECONDS` | `30` | Wait time between retries when PDB violation (429) received. |
| `DRAIN_PDB_MAX_RETRIES` | `10` | Maximum PDB retry attempts before aborting drain. |
| `HEALTH_VALIDATION_WINDOW_MINUTES` | `10` | Window in which health thresholds must be met post-migration. |
| `EXECUTION_LOCK_TTL_HOURS` | `2` | TTL for `execution_locks` record; auto-expires if process crashes. |
| `EXECUTION_LOCK_RENEWAL_INTERVAL_SECONDS` | `600` | How often the active execution renews its lock TTL (seconds). |
| `MAX_CONCURRENT_DRAIN_AZ` | `1` | Maximum number of AZs from which nodes can be drained simultaneously. |
| `NODE_CAPACITY_BUFFER_PCT` | `20` | Buffer percentage applied to CPU/memory when sizing NodeClaims. |
| `HMAC_SECRET_KEY` | *(required)* | Secret key used for HMAC-SHA256 signing of execution plans. Must be set; no default. |

## Error Handling
- **Plan identity mismatch:** Execution aborted immediately; `execution_history` marked `aborted`; operator notified via `execution.completed` event with `status=aborted` and `failure_reason='plan_identity_mismatch'`.
- **Lock already held:** If `execution_locks` row exists and is not expired, the new execution request is rejected with HTTP 409. Stale locks (past `expires_at`) are force-released.
- **Lock heartbeat renewal:** The running execution renews its Redis lock TTL and updates `execution_locks.expires_at` every `EXECUTION_LOCK_RENEWAL_INTERVAL_SECONDS` (default: 600 — 10 minutes). On each renewal, it writes the current step to `execution_history.current_step` and verifies that its own `execution_id` still matches `execution_locks.execution_id`. If the PostgreSQL row shows a different `execution_id` (indicating a lock expiry-and-reacquire race), the original execution self-aborts immediately (`status=aborted, failure_reason='lock_lost'`). The process that acquired the lock then detects the partially-applied state via the pre-execution snapshot and triggers rollback.
- **NodeClaim timeout:** Rollback triggered; node is un-tainted; `execution_history` updated with `failure_reason='nodeclaim_timeout'`.
- **Drain failure after max retries:** `UNCORDON_NODE` runs immediately; rollback triggered for all previously completed steps.
- **Health validation failure:** Rollback triggered; verification results stored in `execution_history.failure_reason` as structured JSON; operator notified.
- **Agent unreachable:** Execution is paused (not failed) for up to 5 minutes while awaiting agent reconnect. After 5 minutes, execution is aborted and rollback triggered.
- **Crash recovery on BullMQ retry:** When the BullMQ execution job is retried after a crash, it performs a pre-flight audit before any new steps: reads `execution_history.current_step` to determine how far execution progressed, then queries live cluster state for any nodes annotated with `balancekube.io/execution-id: {this_execution_id}` that remain in `cordoned` state without a subsequent successful drain record. All such nodes are immediately uncordoned, their steps marked `FAILED_RECOVERED`, and execution resumes from the last safe checkpoint.
- **NATS publish failure:** `execution.completed` written to `event_store` for deferred delivery with at-least-once guarantee.

## Future Enhancements
- **Step-level retry configuration:** Allow operators to configure per-step retry policies rather than using global defaults.
- **Canary execution:** Migrate a single workload instance first, validate health, then proceed with the remaining workloads.
- **Execution simulation:** Extend `OBSERVE` mode to produce a detailed diff showing exactly which labels, taints, and scheduling changes would be applied.
- **Multi-cluster execution:** Batch execution across multiple clusters in a single recommendation set with global ordering constraints.
- **Execution webhook callbacks:** Allow external CI/CD systems to receive callbacks at each step completion for integration with change management systems.
