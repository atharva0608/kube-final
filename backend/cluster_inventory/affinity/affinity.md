# affinity

## Purpose
Captures and stores affinity and anti-affinity rules — `nodeAffinity`, `podAffinity`, `podAntiAffinity` — as well as `topologySpreadConstraints` from all workload objects. Phase 2 records these as informational signals. Phase 4 reads them as hard constraints that are never modified. If developer-written affinity conflicts with BalanceKube's group placement intent, execution is blocked with an `INTENT_CONFLICT` error surfaced to the operator.

## Responsibilities
- Collect affinity and `topologySpreadConstraints` fields from pod specs of Deployments, StatefulSets, and standalone pods.
- Store affinity rules as JSONB on their respective resource rows — no separate affinity table exists.
- Phase 2: read affinity data as an informational signal for classification and tag generation.
- Phase 4: read developer-written affinity as **read-only** to check for conflicts with NodeClaim placement intent. If conflicts exist, surface `INTENT_CONFLICT` to operator and halt execution for the affected workload group.
- Enforce the immutability constraint: BalanceKube **never** writes to, modifies, or removes developer-authored affinity or `topologySpreadConstraints` on any workload spec.
- Store `topologySpreadConstraints` from pod specs (also read-only) and carry them forward to NodeClaim spec generation in Phase 4.

## Inputs
- **Source:** Agent Controller push — affinity rules extracted from pod specs during inventory collection. Embedded within Deployment, StatefulSet, and Pod objects sent via `agent.inventory.*` NATS subjects.
- **Format:** JSONB-compatible Kubernetes affinity objects:
  ```json
  {
    "nodeAffinity": {
      "requiredDuringSchedulingIgnoredDuringExecution": {
        "nodeSelectorTerms": [...]
      }
    },
    "podAntiAffinity": {
      "preferredDuringSchedulingIgnoredDuringExecution": [...]
    }
  }
  ```

## Outputs
- **Destination:** No separate table — affinity data stored as JSONB columns on `pods`, `deployments`, and `statefulsets` tables.
- **Format:** JSONB fields readable by Phase 4 capacity provisioning and Phase 2 classification.

## Events Produced
N/A — affinity data is captured as part of resource ingestion; no separate events emitted.

## Events Consumed
N/A — data arrives as part of broader resource ingestion.

## Database Tables

**Owns (writes to):**
None — affinity is stored as JSONB on the following tables (owned by their respective sub-modules):

| Table | Affinity Columns |
|---|---|
| `deployments` | `affinity` (jsonb), `topology_spread_constraints` (jsonb) |
| `statefulsets` | `affinity` (jsonb), `topology_spread_constraints` (jsonb) |
| `pods` | `affinity` (jsonb), `topology_spread_constraints` (jsonb) |

**Reads (read-only, cross-domain):**
- `deployments`, `statefulsets`, `pods` — Phase 4 reads affinity JSONB to perform conflict detection before NodeClaim provisioning.

## APIs
N/A — affinity data is not exposed via a dedicated API endpoint. It is included in the response payloads of `GET /clusters/:id/deployments`, `GET /clusters/:id/statefulsets`, and `GET /clusters/:id/pods` as nested fields.

## Dependencies
- `cluster_inventory` resource sub-modules (`deployments`, `statefulsets`, `pods`) — affinity is stored as part of those rows.
- `execution` (Phase 4, `capacity_provisioning`) — reads `nodeAffinity` and `topologySpreadConstraints` to build NodeClaim specs. Required affinity terms are passed through verbatim. If `nodeAffinity.required` terms conflict with target Spot pool labels → `INTENT_CONFLICT`.
- `workload_classification` (Phase 2) — reads `podAntiAffinity` to detect topology spread intent (e.g., spread across AZs) which informs group placement strategy.
- PostgreSQL — primary storage with JSONB containment queries.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `AFFINITY_CONFLICT_STRATEGY` | `block` | Action when `INTENT_CONFLICT` detected: `block` (halt execution for group, surface to operator) or `skip` (skip affected workload, proceed with group). `block` is strongly recommended. |

## Error Handling
- **Missing affinity:** Workloads with no affinity rules store `null` for all affinity JSONB fields. This is the common case and treated as unconstrained placement.
- **Malformed affinity:** If affinity JSONB fails Kubernetes schema validation (e.g., invalid operator values), the field is stored as-is with a `AFFINITY_SCHEMA_WARN` log. Phase 4 conflict detection skips malformed fields and logs `AFFINITY_PARSE_SKIP`.
- **INTENT_CONFLICT detected in Phase 4:** Execution is halted for the affected application group. `execution_history` records the failure with `failure_reason=INTENT_CONFLICT`. Operator must resolve by either adjusting developer affinity or operator-overriding the group placement strategy.

## Future Enhancements
- Build an affinity conflict pre-checker that runs during Phase 2 (before plan approval) to surface potential `INTENT_CONFLICT` issues at recommendation time rather than at execution time.
- Parse and store weighted `preferredDuringScheduling` terms separately from `requiredDuringScheduling` terms to allow Phase 4 to distinguish hard vs soft conflicts.
- Detect workloads that use `podAntiAffinity` with `topologyKey: kubernetes.io/hostname` (each replica on a different node) and automatically factor this into Phase 4's required capacity headroom calculations.
