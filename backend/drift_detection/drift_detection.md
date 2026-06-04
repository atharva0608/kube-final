# drift_detection

## Purpose
Continuously monitors whether the live cluster state remains consistent with the assembled snapshot that backs the current pending recommendation. When the cluster drifts, the engine classifies the type and severity of drift, determines whether the existing plan can be patched in-place (PATCHABLE) or requires a full Phase 2 re-analysis (NOT PATCHABLE), and emits structured events so that operators and downstream systems can react appropriately.

## Responsibilities
- Run drift checks on three triggers: (1) immediately after `cluster.analysed` is received, (2) on a 5-minute recurring schedule while the recommendation is in `pending_approval` state, (3) on-demand via the `POST /clusters/:id/drift/recheck` API.
- Use a **3-part plan identity** (`snapshot_id + analysis_version + cluster_hash`) to detect stale plans instantly — any `cluster_hash` mismatch triggers immediate invalidation without further comparison.
- Compare **Plane 1 (Node Layout):** instance types, AZs, capacity types, node pools, node counts, allocatable CPU and memory.
- Compare **Plane 2 (Workload Placement):** workload-to-node-type mapping, Spot vs On-Demand per workload, AZ distribution deltas, CPU/memory profile changes.
- Classify each drift event into one of six drift types: `WORKLOAD_LEVEL`, `NODE_COMPOSITION`, `PLACEMENT_MISMATCH`, `PRICING_SHIFT`, `REPLICA_SPIKE`, `APPLICATION_GROUP_CHANGE`. Track `OWNERSHIP_CONFLICT` separately in `deployment_conflicts` — it never contributes to the drift score.
- Apply the **PLACEMENT_MISMATCH guard**: only count a pod-on-wrong-lifecycle as a PLACEMENT_MISMATCH drift if (1) the pod has been Running on the wrong node type for > 15 minutes, (2) there is no active rolling update on the workload, and (3) no Spot interruption occurred on that node in the last 10 minutes.
- Decide PATCHABLE vs NOT PATCHABLE for each drift event and write a `plan_delta` for patchable changes, or trigger Phase 2 re-analysis for non-patchable ones.
- Update `recommendation_store` rows in-place for patchable deltas (updating `plan_delta_at` and step parameters); require re-acknowledgement for moderate patches, no new approval for minor patches.
- Publish `drift.detected`, `drift.patchable`, or `drift.invalidated` events.

## Inputs
- **Source:** `cluster.analysed` NATS event — triggers the initial drift check immediately after a recommendation is generated.
- **Source:** BullMQ recurring scheduler — triggers the 5-minute polling check while `recommendation_store.status = 'pending_approval'`.
- **Source:** `POST /clusters/:id/drift/recheck` API — operator-triggered on-demand recheck.
- **Source:** `assembled_snapshots` table — the planned snapshot (`recommendation.snapshot_id`) used as the baseline for comparison.
- **Source:** Live cluster inventory tables (`nodes`, `pods`, `deployments`, `statefulsets`, `pvcs`, `pdbs`) — current cluster state at time of check.
- **Source:** `spot_prices` table — current Spot pricing for `PRICING_SHIFT` classification.
- **Format:** All live state read as PostgreSQL rows; snapshot baseline read from `assembled_snapshots.payload` (JSONB).

## Outputs
- **Destination:** `drift_events` table — one row per detected drift event.
- **Destination:** `plan_deltas` table — one row per patchable drift resolution.
- **Destination:** NATS topics `drift.detected`, `drift.patchable`, `drift.invalidated`.
- **Format:**
  ```json
  {
    "event": "drift.detected",
    "cluster_id": "uuid",
    "recommendation_id": "uuid",
    "drift_type": "NODE_COMPOSITION",
    "severity": "MODERATE",
    "patchable": true,
    "affected_workloads": ["workload-uuid-1", "workload-uuid-2"],
    "detected_at": "2024-06-04T07:30:00Z"
  }
  ```

## Events Produced
| Event | Description |
|---|---|
| `drift.detected` | Emitted when any drift is detected. Payload: `cluster_id`, `recommendation_id`, `drift_type`, `severity`, `patchable`, `affected_workloads`, `detected_at`. |
| `drift.patchable` | Emitted when drift is classified as PATCHABLE and a `plan_delta` has been written. Triggers minor or moderate re-acknowledgement flow. |
| `drift.invalidated` | Emitted when drift is NOT PATCHABLE or `cluster_hash` mismatch detected. Transitions `recommendation_store.status` back toward Phase 2 re-analysis. |

## Events Consumed
| Event | Action |
|---|---|
| `cluster.analysed` | Subscribes to this event to trigger the initial drift check immediately after Phase 2 completes. Extracts `snapshot_id`, `analysis_version`, `cluster_hash` from the payload to establish the 3-part plan identity baseline. |

## Database Tables

**Tables this module owns (writes to):**
| Table | Description |
|---|---|
| `drift_events` | Records each detected drift occurrence. Columns: `id`, `cluster_id`, `recommendation_id`, `drift_type` (ENUM: `WORKLOAD_LEVEL`, `NODE_COMPOSITION`, `PLACEMENT_MISMATCH`, `PRICING_SHIFT`, `REPLICA_SPIKE`, `APPLICATION_GROUP_CHANGE`), `severity` (ENUM: `MINOR`, `MODERATE`, `CRITICAL`), `patchable` (boolean), `affected_workloads` (JSONB array of workload UUIDs), `detected_at`. |
| `plan_deltas` | In-place plan patches for PATCHABLE drift. Columns: `id`, `recommendation_id`, `delta_payload` (JSONB — updated step parameters), `created_at`. |

**Tables this module reads (read-only):**
| Table | Source Domain |
|---|---|
| `assembled_snapshots` | Snapshot Assembly |
| `recommendation_store` | Recommendations |
| `nodes`, `pods`, `deployments`, `statefulsets`, `pvcs`, `pdbs` | Cluster Inventory |
| `spot_prices` | Pricing |
| `deployment_conflicts` | Shared / Execution |

## APIs
| Method | Path | Description |
|---|---|---|
| `GET` | `/clusters/:id/drift` | Returns all `drift_events` for the active recommendation, ordered by `detected_at` descending. Includes severity, patchability, and affected workload list. |
| `POST` | `/clusters/:id/drift/recheck` | Triggers an on-demand drift check for the cluster's current `pending_approval` recommendation. Returns `{ drift_detected: boolean, drift_type?, patchable? }`. Requires `operator` or `admin` role. |

## Dependencies
- **recommendations** module — reads `recommendation_store` to resolve the current `snapshot_id` and baseline `cluster_hash`.
- **snapshot_assembly** — reads `assembled_snapshots` payload as the plan baseline for comparison.
- **Cluster Inventory** — reads live node/pod/workload state for both comparison planes.
- **pricing** module — reads `spot_prices` for PRICING_SHIFT drift classification.
- **NATS** — for consuming `cluster.analysed` and publishing drift events; falls back to Redis Streams.
- **BullMQ** — recurring 5-minute scheduled job (`drift-polling-job`) that only runs when `recommendation_store.status = 'pending_approval'`.
- **shared/db** — PostgreSQL client; drift check and `plan_delta` write are transactional.
- **shared/logger** — structured logging with `cluster_id`, `recommendation_id`, `drift_type` context.

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `DRIFT_POLL_INTERVAL_SECONDS` | `300` | Interval (seconds) for recurring drift checks while recommendation is `pending_approval`. |
| `DRIFT_PLACEMENT_MISMATCH_GRACE_MINUTES` | `15` | Minimum time a pod must be Running on the wrong node lifecycle before it counts as PLACEMENT_MISMATCH. |
| `DRIFT_INTERRUPTION_GUARD_MINUTES` | `10` | Lookback window (minutes) for recent Spot interruptions that suppress PLACEMENT_MISMATCH counting. |
| `DRIFT_PRICING_SHIFT_THRESHOLD_PCT` | `20` | Percentage increase in Spot price above OD price that triggers a PRICING_SHIFT drift event. |
| `DRIFT_REPLICA_SPIKE_THRESHOLD_PCT` | `30` | Percentage increase in replica count (outside HPA bounds) that triggers a REPLICA_SPIKE drift. |
| `NATS_DRIFT_DETECTED_TOPIC` | `drift.detected` | NATS topic for drift detection events. |
| `NATS_DRIFT_PATCHABLE_TOPIC` | `drift.patchable` | NATS topic for patchable drift events. |
| `NATS_DRIFT_INVALIDATED_TOPIC` | `drift.invalidated` | NATS topic for plan invalidation events. |

## Patchable vs Not-Patchable Classification

| Drift Scenario | Classification | Action |
|---|---|---|
| Replica count changed within HPA bounds | PATCHABLE | Write `plan_delta`, no new approval needed (minor patch). |
| Spot price shifted but still below OD | PATCHABLE | Write `plan_delta`, update step parameters, no new approval needed. |
| New node added without changing plan capacity significantly | PATCHABLE | Write `plan_delta`, minor patch. |
| New workload deployed requiring review | NOT PATCHABLE | Emit `drift.invalidated`, trigger Phase 2 re-analysis. |
| Storage profile change (PVC added/removed) | NOT PATCHABLE | Emit `drift.invalidated`. |
| PDB now blocks all eviction | NOT PATCHABLE | Emit `drift.invalidated`. |
| Application group topology changed | NOT PATCHABLE | Emit `drift.invalidated`, re-analysis required. |
| `cluster_hash` mismatch | NOT PATCHABLE (immediate) | Emit `drift.invalidated` immediately, no further comparison. |

## Error Handling
- **`cluster_hash` mismatch:** Immediately emits `drift.invalidated` without performing any plane comparisons. This is the highest-priority guard.
- **Live inventory unavailable:** If the cluster agent has not sent a collection cycle within the last 10 minutes, drift check is aborted and a `drift_events` row is written with `drift_type=NODE_COMPOSITION`, `severity=CRITICAL`, `patchable=false` to alert operators that the cluster state is unverifiable.
- **NATS publish failure:** Events are retried up to 5 times with 2s exponential backoff before being written to `event_store` for deferred delivery.
- **Plan delta write failure:** If the `plan_deltas` write fails, the drift is escalated to NOT PATCHABLE to prevent the execution engine from operating on a stale plan.
- **Concurrent drift checks:** Guarded by a Redis distributed lock per `cluster_id`; simultaneous recheck API calls are deduplicated.

## Future Enhancements
- **Drift scoring:** Aggregate drift events into a composite drift score (0–100) to give operators a single health signal for the pending recommendation.
- **Auto-invalidation threshold:** Allow operators to configure a maximum number of PATCHABLE drift events before automatic escalation to NOT PATCHABLE and Phase 2 re-analysis.
- **Drift history UI:** Timeline view of all drift events for a recommendation, showing which events led to which plan patches.
- **Webhooks on invalidation:** Allow operators to configure a webhook callback when `drift.invalidated` is emitted so their on-call systems are notified.
- **OWNERSHIP_CONFLICT promotion:** Surface `deployment_conflicts` data in the drift API response even though they are excluded from the drift score.
