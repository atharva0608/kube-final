# labels

## Purpose
Provides a unified label index across all Kubernetes resources collected from a cluster. Labels are the primary raw signal for Phase 2 tag generation — workload classification reads known semantic label keys to infer application names, components, and environments. This module also tracks BalanceKube's own annotations and CD system annotations to detect externally managed workloads.

## Responsibilities
- Index all resource labels and annotations collected during inventory ingestion (stored as JSONB on each resource's own table — no separate labels table exists).
- Provide a cross-resource search API so operators can query which resources have a given label key or value.
- Document which label keys carry semantic meaning in BalanceKube's classification model.
- Track CD system annotations (`argocd.argoproj.io/*`, `meta.helm.sh/*`, `flux.toolkit.fluxcd.io/*`) to identify GitOps-managed resources.
- Track BalanceKube's own annotations (`balancekube.io/*`) written during Phase 4 to mark managed nodes.
- Enforce the rule that `criticality` and `tier=critical` labels are **not** used to infer business criticality (too inconsistent across teams — only operator-set criticality at review time counts).

## Inputs
- **Source:** All resource ingestion sub-modules — labels are stored as `jsonb` columns on `deployments`, `statefulsets`, `daemonsets`, `pods`, `nodes`, `pvcs`, `namespaces` tables. No separate ingestion path for labels.
- **Format:** JSONB objects matching the Kubernetes `metadata.labels` and `metadata.annotations` maps.

## Outputs
- **Destination:** No separate table — labels are stored as JSONB fields on each resource table.
- **Format:** Cross-resource label search results returned as JSON from the search API. Phase 2 reads labels directly from resource tables via SQL `jsonb @>` containment queries.

## Events Produced
N/A — this module is a cross-cutting concern within `cluster_inventory`; no events emitted.

## Events Consumed
N/A — labels are populated as a side effect of resource ingestion; no separate subscription.

## Database Tables

**Owns (writes to):**
None — labels are stored as `jsonb` columns on the following tables (owned by their respective sub-modules):

| Table | Label Columns |
|---|---|
| `deployments` | `labels`, `annotations` |
| `statefulsets` | `labels`, `annotations` |
| `daemonsets` | `labels`, `annotations` |
| `pods` | `labels`, `annotations` |
| `nodes` | `labels`, `annotations`, `taints` |
| `pvcs` | `labels`, `annotations` |
| `namespaces` | `labels`, `annotations` |

**Reads (read-only, cross-domain):**
- All resource tables above — label search queries run across all tables.

### Semantically Significant Label Keys

| Label Key | Usage in BalanceKube |
|---|---|
| `app` | Primary workload name signal for tag generation |
| `app.kubernetes.io/name` | Preferred Kubernetes standard name label |
| `app.kubernetes.io/component` | Component classification (backend, frontend, worker) |
| `tier` | Environment tier signal (value `critical` is NOT used for criticality inference) |
| `environment` | Environment context (production, staging, dev) |
| `balancekube.io/lifecycle` | Written by Phase 4 to Spot nodes: `spot` or `on-demand` |
| `balancekube.io/spot-pool` | Written by Phase 4: `stable` or `volatile` |
| `balancekube.io/group` | Written by Phase 4: application group name |
| `argocd.argoproj.io/app-name` | Identifies ArgoCD-managed applications |
| `meta.helm.sh/release-name` | Identifies Helm-managed releases |
| `flux.toolkit.fluxcd.io/name` | Identifies Flux-managed objects |

## APIs

| Method | Path | Description |
|---|---|---|
| `GET` | `/clusters/:id/labels` | Search labels across all resource types. Query params: `key` (label key to search), `value` (optional label value), `resource_type` (filter to `deployments`, `pods`, `nodes`, etc.), `snapshot_id` (defaults to latest). Returns list of matching resources with their full label maps. |

## Dependencies
- All `cluster_inventory` sub-modules — each sub-module populates labels on its own table rows.
- `workload_classification` (Phase 2) — reads labels via `jsonb @>` queries to build the semantic tag set for each workload.
- PostgreSQL `jsonb` indexing — GIN indexes on `labels` and `annotations` columns on high-volume tables (`pods`, `nodes`) for efficient label search.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `LABEL_SEARCH_MAX_RESULTS` | `1000` | Maximum results returned by the label search API before pagination is required. |
| `LABEL_GIN_INDEX_TABLES` | `pods,nodes,deployments` | Tables on which GIN indexes are maintained for label JSONB queries. |

## Error Handling
- **Oversized label maps:** Labels exceeding 256 key-value pairs (Kubernetes limit) are stored as-is — PostgreSQL JSONB handles arbitrary map sizes without truncation.
- **Invalid UTF-8 in label values:** PostgreSQL rejects invalid UTF-8; agent strips non-UTF-8 bytes before transmission. If stripping is insufficient, the entire resource row is rejected and logged as `LABEL_ENCODING_ERROR`.
- **GIN index failures:** If a GIN index query times out (> 5 seconds), the label search API falls back to a sequential scan with a `slow_query` warning logged.

## Future Enhancements
- Materialise a `label_index` table (resource_type, resource_id, key, value) for O(1) label lookup without full JSONB scan, especially for large clusters with 10 000+ pods.
- Add a label consistency report: surface label keys that exist on only a subset of workloads in the same namespace (potential misconfiguration).
- Implement label-change tracking across snapshots to give operators a history of label mutations.
