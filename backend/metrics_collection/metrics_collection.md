# metrics_collection

## Purpose
The `metrics_collection` module ingests, normalizes, and stores time-series resource utilization data collected by the BalanceKube agent DaemonSet from each cluster node's Kubelet Summary API. It exists as a separate module because metric data has fundamentally different storage characteristics (high write volume, time-series pruning, rolling aggregations) from inventory data, and because it provides the raw empirical signal that `resource_analysis` (Phase 2) consumes to compute utilization profiles and rightsizing recommendations.

## Responsibilities
- Accept batched metric payloads pushed by the agent DaemonSet every 60 seconds via REST API
- Validate and normalize all metric values to canonical units before persistence:
  - CPU → millicores (m)
  - Memory → MiB (mebibytes)
  - Network → Kbps (kilobits per second)
  - Filesystem → GiB (gibibytes)
- Store per-pod and per-node metrics with timestamps for time-series querying
- Record `null` metrics (not reject the push) when Kubelet data is unavailable for a specific node — does not block snapshot assembly
- Prune metric rows older than 90 days on a scheduled background worker
- Compute and cache rolling P50 and P95 percentile values over a 7-day sliding window for downstream consumption by `resource_analysis`
- Serve metric history to the frontend for workload utilization visualization
- Handle the sub-modules: `kubelet_metrics`, `metrics_server`, `cpu`, `memory`, `network`, `filesystem`, `normalization`

## Inputs

### From Agent (REST)
- **Source**: `POST /api/v1/agents/:id/metrics`
- **Frequency**: Every 60 seconds per node
- **Format**: `MetricsPayload` TypeScript type:
```typescript
{
  clusterId: string;
  agentId: string;
  collectedAt: string;           // ISO 8601
  batchId: string;               // UUID v4 for deduplication
  source: 'kubelet_summary' | 'metrics_server';
  nodes: NodeMetrics[];
  pods: PodMetrics[];
}

type NodeMetrics = {
  nodeName: string;
  nodeId: string;                // FK to nodes.id
  cpu: {
    usageNanoCores: number;      // from kubelet, converted to m
    usageCoreNanoSeconds: number;
  } | null;
  memory: {
    usageBytes: number;          // converted to MiB
    workingSetBytes: number;
    rssBytes: number;
  } | null;
  network: {
    rxBytes: number;             // converted to Kbps
    txBytes: number;
    rxErrors: number;
    txErrors: number;
  } | null;
  filesystem: {
    usedBytes: number;           // converted to GiB
    capacityBytes: number;
    availableBytes: number;
  } | null;
};

type PodMetrics = {
  podName: string;
  namespace: string;
  podId: string;                 // FK to pods.id
  nodeName: string;
  containers: {
    name: string;
    cpu: { usageNanoCores: number } | null;
    memory: { usageBytes: number; workingSetBytes: number } | null;
  }[];
};
```

### Kubelet Summary API (called by Agent)
The agent DaemonSet, running on each node, calls the local Kubelet Summary API:
```
GET https://localhost:10250/stats/summary
```
Authorization: ServiceAccount token with `nodes/stats` RBAC permission.

Fallback: If Kubelet is unreachable, the agent falls back to the Kubernetes Metrics Server (`metrics.k8s.io/v1beta1`) for pod-level CPU and memory only (network and filesystem not available via Metrics Server).

## Outputs

### Database Writes
Rows written to metric tables on each accepted push:
- `cpu_metrics` — one row per pod per push, one row per node per push
- `memory_metrics` — one row per pod per push, one row per node per push
- `network_metrics` — one row per node per push
- `filesystem_metrics` — one row per node per push; one row per PVC if volume usage present

### API Responses (to frontend)
- `GET /api/v1/clusters/:id/metrics/:workload_id` → time-series arrays for CPU, memory, network, storage over configurable window

### Redis Cache
- Rolling P50/P95 computed values written per workload:
  - Key: `metrics:p95:cpu:{workload_id}:{window_days}` → float (millicores)
  - Key: `metrics:p95:mem:{workload_id}:{window_days}` → float (MiB)
  - TTL: 3600 seconds (refreshed on each prune/aggregation cycle)

## Events Produced
N/A — this module does not publish NATS events. Metrics are consumed directly via database reads by `resource_analysis`.

## Events Consumed
N/A — this module is purely driven by agent REST pushes and background worker schedules. It does not subscribe to NATS events.

## Database Tables

### Tables Owned (Written)
| Table | Key Columns | Notes |
|---|---|---|
| `cpu_metrics` | `id`, `cluster_id`, `pod_id (FK→pods.id, nullable)`, `node_id (FK→nodes.id, nullable)`, `value_m FLOAT` (millicores), `collected_at TIMESTAMPTZ` | `pod_id` and `node_id` are both nullable — a row may represent pod-level or node-level. At least one must be non-null. NULL value_m = Kubelet data unavailable for that cycle |
| `memory_metrics` | `id`, `cluster_id`, `pod_id (nullable)`, `node_id (nullable)`, `value_mi FLOAT` (MiB), `working_set_mi FLOAT`, `rss_mi FLOAT`, `collected_at TIMESTAMPTZ` | `working_set_mi` is preferred for OOMKill analysis |
| `network_metrics` | `id`, `cluster_id`, `node_id (FK→nodes.id)`, `rx_kbps FLOAT`, `tx_kbps FLOAT`, `rx_errors INT`, `tx_errors INT`, `collected_at TIMESTAMPTZ` | Node-level only — per-pod network not available from Kubelet Summary API |
| `filesystem_metrics` | `id`, `cluster_id`, `node_id (FK→nodes.id, nullable)`, `pvc_id (FK→pvcs.id, nullable)`, `used_gi FLOAT`, `capacity_gi FLOAT`, `available_gi FLOAT`, `collected_at TIMESTAMPTZ` | Either node-level (ephemeral) or PVC-level (persistent) |

### Indexes
- `cpu_metrics(cluster_id, pod_id, collected_at DESC)` — primary query pattern for P95 window
- `memory_metrics(cluster_id, pod_id, collected_at DESC)`
- `network_metrics(cluster_id, node_id, collected_at DESC)`
- `filesystem_metrics(cluster_id, node_id, collected_at DESC)`
- Partial index on `cpu_metrics WHERE value_m IS NULL` — for null-metrics auditing

### Tables Read (Cross-Domain, Read-Only)
| Table | Module | Purpose |
|---|---|---|
| `pods` | `cluster_inventory` | Validate `pod_id` FK on ingestion |
| `nodes` | `cluster_inventory` | Validate `node_id` FK on ingestion |
| `pvcs` | `cluster_inventory` | Validate `pvc_id` FK on filesystem metric rows |
| `clusters` | `onboarding` | Validate cluster membership for agent authentication |

## APIs
| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/agents/:id/metrics` | Agent token | Accept batched metric push from agent DaemonSet. Validates agent token. Deduplicates by `batchId`. Normalizes all values. Bulk inserts. Returns `{ accepted: true, rowsWritten: N }`. |
| `GET` | `/api/v1/clusters/:id/metrics/:workload_id` | JWT | Return metric time series for a specific workload (aggregated from pod-level). Query params: `?window=7d` (default), `?resolution=1h` (downsampling resolution), `?metrics=cpu,memory,network,filesystem`. Returns P50/P95 pre-computed where available. |

## Dependencies

### Internal Modules
| Module | Usage |
|---|---|
| `common/auth` | Agent token validation middleware |
| `common/validation` | Zod schema validation of `MetricsPayload` |
| `common/logger` | Structured logging with `clusterId`, `batchId`, `source` context |
| `database` | PostgreSQL pool; optimized bulk insert with `COPY` or multi-row `INSERT` |

### External Services
None — this module writes only to PostgreSQL and Redis. The agent handles all Kubelet/Metrics Server calls externally.

### Sub-Modules
| Sub-Module | Responsibility |
|---|---|
| `kubelet_metrics` | Parse and map Kubelet Summary API response format to internal types |
| `metrics_server` | Parse Kubernetes Metrics Server response as fallback source |
| `cpu` | CPU nanoCores → millicores conversion; per-pod aggregation across containers |
| `memory` | Bytes → MiB conversion; select `workingSetBytes` as primary value |
| `network` | Bytes/interval → Kbps calculation; delta computation between consecutive readings |
| `filesystem` | Bytes → GiB conversion; separate node vs PVC classification |
| `normalization` | Unit conversion utilities; value clamping (negative values → 0); null propagation rules |

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `METRICS_PUSH_INTERVAL_S` | `60` | Expected agent push interval (used for staleness detection) |
| `METRICS_RETENTION_DAYS` | `90` | Days before metric rows are pruned by the scheduled worker |
| `METRICS_P95_WINDOW_DAYS` | `7` | Rolling window (days) for P50/P95 computation |
| `METRICS_PRUNE_BATCH_SIZE` | `10000` | Number of rows deleted per prune batch to avoid table lock contention |
| `METRICS_PRUNE_CRON` | `0 3 * * *` | Cron expression for the daily prune worker (3 AM UTC) |
| `METRICS_DEDUP_WINDOW_S` | `120` | Window within which duplicate `batchId` pushes are rejected |
| `METRICS_NULL_THRESHOLD_PERCENT` | `20` | If more than this percent of nodes report null metrics, emit a `METRICS_DEGRADED` warning log |
| `METRICS_MAX_BATCH_SIZE` | `100000` | Maximum metric rows accepted in a single push payload |

## Error Handling

| Scenario | Behavior |
|---|---|
| Invalid or expired agent token | `401 Unauthorized`; log `METRICS_AUTH_FAILED` |
| `MetricsPayload` schema validation failure | `400 Bad Request` with Zod error detail; entire batch rejected — no partial write |
| Duplicate `batchId` within dedup window | `200 OK` with `{ accepted: false, reason: 'DUPLICATE_BATCH' }` — idempotent |
| Null Kubelet data for a node | Accepted: writes NULL `value_m` row. Does not block snapshot assembly. Logged at DEBUG level per node. |
| DB bulk insert failure | Retry 3× with exponential backoff. On failure after 3 retries, return `500` to agent; agent will retry next cycle (data for this window is lost) |
| Prune worker failure | Logged as `METRICS_PRUNE_FAILED`; dead-letter job created; next scheduled run will prune the combined window |
| P95 computation overflow (extreme values) | Values clamped to `MAX_SAFE_METRIC_VALUE` constant; logged as `METRICS_VALUE_CLAMPED` |
| Pod/node FK validation failure | Row skipped with warning log `METRICS_FK_MISS`; remainder of batch continues — avoids rejecting an entire batch due to a single deleted pod |

## Future Enhancements
- **Prometheus remote_write endpoint**: Accept metrics pushed directly from cluster-internal Prometheus via `remote_write`, enabling richer application-level metrics (e.g., request latency, error rate) to inform eligibility decisions
- **KEDA scaler metrics**: Ingest KEDA external scaler metrics to detect event-driven workloads that scale to zero
- **Custom metrics support**: Allow operators to specify custom Prometheus query expressions whose results are stored alongside standard metrics for workload profiling
- **Metric anomaly detection**: Flag statistical outliers (e.g., sudden 10× CPU spike) to distinguish batch spikes from sustained load for classification
- **Per-container granularity**: Store container-level metrics separately (currently aggregated at pod level for most queries) to support init container and sidecar analysis
- **Compression**: Use PostgreSQL `timescaledb` hypertables or columnar compression for metrics tables to reduce storage cost at scale
