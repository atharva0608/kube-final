# taints

## Purpose
Captures taint and toleration data from cluster nodes and workload pod specs. This module underpins two distinct read/write patterns: Phase 1 reads taints to understand current node scheduling constraints; Phase 4 **writes** a specific taint (`balancekube.io/critical-only=true:NoSchedule`) to reserved on-demand nodes to prevent Spot-eligible workloads from landing on them after drain.

## Responsibilities
- Collect node taints from node objects and pod tolerations from pod specs during inventory collection.
- Store taint and toleration data as JSONB on `nodes` and `pods` tables respectively (no separate table).
- Enable Phase 4 execution to read existing pod tolerations and carry them forward when constructing NodeClaim selection criteria, ensuring migrated pods can still tolerate special node taints.
- Support Phase 4 writing the `balancekube.io/critical-only=true:NoSchedule` taint to reserved on-demand nodes after Spot migration completes — prevents regression of spot-eligible workloads back onto OD capacity.
- Enforce the immutability constraint: BalanceKube **never** modifies developer-authored tolerations on any workload spec; it only writes to **node** objects.

## Inputs
- **Source:** Agent Controller push — taint data extracted from node objects and pod specs during inventory collection. Embedded within Node and Pod objects sent via `agent.inventory.nodes.{cluster_id}` and `agent.inventory.pods.{cluster_id}` NATS subjects.
- **Format:**
  - Node taints (JSONB array):
    ```json
    [{ "key": "node.kubernetes.io/not-ready", "effect": "NoExecute", "value": "" }]
    ```
  - Pod tolerations (JSONB array):
    ```json
    [{ "key": "node.kubernetes.io/not-ready", "operator": "Exists", "effect": "NoExecute", "tolerationSeconds": 300 }]
    ```

## Outputs
- **Destination:** No separate table — stored as JSONB on `nodes.taints` and `pods.tolerations`.
- **Format:** JSONB arrays. Phase 4 reads these directly to build NodeClaim specs and to issue taint-write commands to the Agent Controller.

## Events Produced
N/A — taint data is captured as part of resource ingestion; no separate events emitted.

## Events Consumed
N/A — data arrives as part of broader resource ingestion.

## Database Tables

**Owns (writes to):**
None — taint and toleration data stored as JSONB on tables owned by other sub-modules:

| Table | Taint/Toleration Columns |
|---|---|
| `nodes` | `taints` (jsonb) — array of node taint objects |
| `pods` | `tolerations` (jsonb) — array of pod toleration objects |

**Reads (read-only, cross-domain):**
- `nodes.taints` — read by Phase 4 to understand which nodes are already tainted before execution.
- `pods.tolerations` — read by Phase 4 to carry pod tolerations forward to NodeClaim spec.

## APIs
N/A — taint data is included in `GET /clusters/:id/nodes` and `GET /clusters/:id/pods` response payloads as nested JSONB fields. No dedicated taint API endpoint.

## Dependencies
- `cluster_inventory` resource sub-modules (`nodes`, `pods`) — taint and toleration data is stored on those rows.
- `execution` (Phase 4, `spot_placement`) — Phase 4 **writes** `balancekube.io/critical-only=true:NoSchedule` to reserved on-demand nodes via the Agent Controller. This is the only write to Kubernetes objects that this module participates in, and it targets node objects only — never workload specs.
- `execution` (Phase 4, `capacity_provisioning`) — reads `pods.tolerations` to include them in NodeClaim `spec.taints` requirements, ensuring migrated pods can tolerate the target Spot node's existing taints.
- PostgreSQL — JSONB storage.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `BALANCEKUBE_CRITICAL_TAINT_KEY` | `balancekube.io/critical-only` | Taint key applied to reserved on-demand nodes post-migration. |
| `BALANCEKUBE_CRITICAL_TAINT_EFFECT` | `NoSchedule` | Taint effect applied to reserved on-demand nodes. `NoSchedule` prevents new pods from landing there unless they explicitly tolerate this key. |

## Error Handling
- **Taint write failure:** If Phase 4 cannot write the `balancekube.io/critical-only` taint to a reserved OD node (API server error), the failure is logged as `TAINT_WRITE_FAILED`. Phase 4 does not abort the overall execution — the taint write is retried 3 times. If all retries fail, the execution step is marked `WARN` and the operator is notified; the overall execution may still complete, but the operator is advised to manually inspect the node.
- **Missing tolerations:** Pods with no tolerations store `tolerations=null`. Phase 4 treats this as unconstrained and does not add tolerations to the NodeClaim spec.
- **Conflicting toleration + taint:** If a pod's tolerations would permit scheduling on a `balancekube.io/critical-only` tainted node, Phase 4 flags this as a configuration warning but does not block execution — the toleration is developer-authored and BalanceKube does not remove it.

## Future Enhancements
- Track the full lifecycle of `balancekube.io/*` taints across execution cycles — detect and clean up stale taints from previous incomplete executions.
- Surface taint coverage in the UI: show which OD nodes currently have the `critical-only` taint applied, and which do not (indicating possible regression risk).
- Support cluster-configurable custom taint keys for teams that use non-standard taint conventions for node isolation.
