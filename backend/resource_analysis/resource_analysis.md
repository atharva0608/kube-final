# resource_analysis

## Purpose
The `resource_analysis` module implements Phase 2 Engine 1B: per-workload resource utilization profiling. It computes CPU, memory, network, and storage utilization states for each workload by aggregating time-series metric data against declared Kubernetes resource requests and limits. It exists as a separate module because resource profiling is a statistically intensive computation requiring its own data maturity rules, rolling percentile logic, and state machine — distinct from classification (which uses metadata) and eligibility (which uses analysis outputs as inputs).

## Responsibilities
- For each workload in an assembled snapshot, compute CPU and memory utilization ratios from P50 and P95 metrics over a 7-day rolling window
- Classify CPU utilization into one of four states: `THROTTLED`, `OVER_PROVISIONED`, `RIGHT_SIZED`, `UNDER_PROVISIONED`
- Classify memory utilization into one of three states: `OVER_PROVISIONED`, `RIGHT_SIZED`, `UNDER_PROVISIONED` (no THROTTLED — memory failures manifest as OOMKills instead)
- Detect network-intensive workloads (cross-node/cross-AZ traffic > 100 Mbps P95) and flag them as candidates for network-optimized instance types
- Analyze PVC-bound workloads for IOPS and throughput patterns; flag high-IOPS workloads for local NVMe or io1/io2 volume types
- Detect Java workloads via image name and environment variable scanning; apply a data maturity hold to Java workloads due to JVM warmup effects — the hold duration is `ELIGIBILITY_JAVA_MIN_AGE_DAYS` days (default: 7), read from the shared environment variable
- Detect batch spike patterns (`is_batch_spike = true`) when current replicas ≥ 3× P50 replica count over 7 days
- Enforce data maturity gates: minimum 7 days of metric history required for reliable analysis; Java workloads held at `SUFFICIENT` maturity until `ELIGIBILITY_JAVA_MIN_AGE_DAYS` full days of post-warmup data are available (default: 7)
- Write per-workload analysis results to `workload_analysis` as JSONB sub-documents for each resource dimension

## Inputs

### From Database (Cross-Domain Reads)
- **Source**: `assembled_snapshots.payload` — `kubernetes.*` section for workload resource requests/limits
- **Source**: `cpu_metrics` — P50/P95 computation over 7-day window, grouped by `workload_id` (aggregated from pod-level rows)
- **Source**: `memory_metrics` — P50/P95 computation, OOMKill event count
- **Source**: `network_metrics` — P95 Rx+Tx Kbps per node, associated with workloads via pod → node mapping
- **Source**: `filesystem_metrics` — PVC usage, IOPS estimates
- **Source**: `workload_classifications` — `is_java` derived from tags; `is_batch` from `batch` tag

### From NATS (Events)
- **Source**: `cluster.collected` event
- **Payload**: `{ clusterId, snapshotId, assemblyVersion }`
- **Action**: Trigger resource analysis for all workloads in the snapshot

### Data Maturity Check
Before computing P95 values, query the minimum `collected_at` timestamp for each workload's metric rows:
- If `(NOW() - min_collected_at) < 7 days` → `data_maturity = INSUFFICIENT`; analysis still written but all states set to `UNKNOWN`
- If `≥ 7 days` → `data_maturity = SUFFICIENT`
- For Java workloads: Java workloads require a minimum of `ELIGIBILITY_JAVA_MIN_AGE_DAYS` days of metrics history (default: 7) before `data_maturity` is considered SUFFICIENT. This threshold is read from the shared environment variable controlled by the eligibility engine — resource_analysis never hard-codes this value. This ensures both modules stay aligned: changing `ELIGIBILITY_JAVA_MIN_AGE_DAYS` in one place affects both the resource profiling maturity check and the eligibility verdict. Even once the maturity threshold is met, check if the earliest 24 hours of readings show JVM startup ramp (CPU > 2× baseline for first 2 hours); if so, exclude the first 24 hours from P95 computation.

## Outputs

### Database Write
| Table | Write Pattern |
|---|---|
| `workload_analysis` | Upsert on `(cluster_id, workload_id, analysis_version)` |

### workload_analysis Schema
```typescript
{
  id: string;
  cluster_id: string;
  workload_id: string;
  analysis_version: string;
  data_maturity: 'INSUFFICIENT' | 'SUFFICIENT';
  is_java: boolean;
  is_batch_spike: boolean;

  cpu_analysis: {
    request_m: number;           // CPU request in millicores
    limit_m: number | null;      // CPU limit in millicores (null if not set)
    p50_m: number | null;        // P50 actual usage in millicores
    p95_m: number | null;        // P95 actual usage in millicores
    cpu_util_ratio: number | null; // p95_m / request_m
    state: 'THROTTLED' | 'OVER_PROVISIONED' | 'RIGHT_SIZED' | 'UNDER_PROVISIONED' | 'UNKNOWN';
    throttle_rate_percent: number | null; // from CFS quota throttle events if available
    recommendation_m: number | null;     // suggested new request value
  };

  memory_analysis: {
    request_mi: number;          // Memory request in MiB
    limit_mi: number | null;     // Memory limit in MiB
    p50_mi: number | null;
    p95_mi: number | null;
    working_set_p95_mi: number | null;
    mem_util_ratio: number | null; // p95_mi / request_mi
    state: 'OVER_PROVISIONED' | 'RIGHT_SIZED' | 'UNDER_PROVISIONED' | 'UNKNOWN';
    oomkill_count_7d: number;
    recommendation_mi: number | null;
  };

  network_analysis: {
    rx_p95_kbps: number | null;
    tx_p95_kbps: number | null;
    combined_p95_mbps: number | null;
    is_network_intensive: boolean; // combined_p95_mbps > 100
    cross_az_traffic_detected: boolean;
    recommended_instance_class: string | null; // e.g. 'network-optimized'
  };

  storage_analysis: {
    pvc_count: number;
    total_capacity_gi: number | null;
    used_gi_p95: number | null;
    capacity_utilization_ratio: number | null;
    estimated_iops: number | null;
    estimated_throughput_mbps: number | null;
    is_high_iops: boolean;       // estimated_iops > 3000
    recommended_volume_type: string | null; // 'local-nvme' | 'io1' | 'io2' | 'gp3' | null
  };

  created_at: string;
}
```

### No Events Published
This module does not publish NATS events. Analysis results are consumed by `eligibility_engine` via direct database reads.

## Events Produced
N/A — resource analysis results are stored in `workload_analysis` and read by `eligibility_engine`.

## Events Consumed
| Event | Action |
|---|---|
| `cluster.collected` | Trigger resource analysis for all workloads in the new assembled snapshot |

## Database Tables

### Tables Owned (Written)
| Table | Key Columns | Notes |
|---|---|---|
| `workload_analysis` | `id UUID PK`, `cluster_id UUID FK`, `workload_id VARCHAR`, `analysis_version VARCHAR`, `data_maturity VARCHAR`, `is_java BOOL`, `is_batch_spike BOOL`, `cpu_analysis JSONB`, `memory_analysis JSONB`, `network_analysis JSONB`, `storage_analysis JSONB`, `created_at TIMESTAMPTZ` | Upsert on `(cluster_id, workload_id, analysis_version)`. JSONB sub-documents validated against internal TypeScript types before write. |

### CPU Utilization State Machine
| State | Condition | Eligibility Impact |
|---|---|---|
| `THROTTLED` | `cpu_util_ratio > 1.0` (P95 exceeds request) | **Hard eligibility block** — workload must not be placed on Spot until CPU is right-sized |
| `OVER_PROVISIONED` | `cpu_util_ratio < 0.25` | No block; candidate for instance downsizing |
| `RIGHT_SIZED` | `0.25 ≤ cpu_util_ratio ≤ 0.80` | Ideal for Spot |
| `UNDER_PROVISIONED` | `cpu_util_ratio > 0.80` | Soft warning; recommend increasing request |
| `UNKNOWN` | `data_maturity = INSUFFICIENT` | No eligibility decision until maturity reached |

### Memory Utilization State Machine
| State | Condition | Notes |
|---|---|---|
| `OVER_PROVISIONED` | `mem_util_ratio < 0.40` | Candidate for smaller memory instance |
| `RIGHT_SIZED` | `0.40 ≤ mem_util_ratio ≤ 0.85` | Suitable for Spot |
| `UNDER_PROVISIONED` | `mem_util_ratio > 0.85` | Risk of OOMKill; recommend increasing limit |
| `UNKNOWN` | `data_maturity = INSUFFICIENT` | Pending |

> Note: There is no `THROTTLED` state for memory. Memory pressure manifests as OOMKills (tracked in `oomkill_count_7d`). Three or more OOMKills in 7 days is a soft eligibility block.

### Tables Read (Cross-Domain, Read-Only)
| Table | Module | Purpose |
|---|---|---|
| `assembled_snapshots` | `snapshot_assembly` | Read resource requests/limits and pod-to-node topology |
| `cpu_metrics` | `metrics_collection` | Query P50/P95 over 7-day window |
| `memory_metrics` | `metrics_collection` | Query P50/P95 and OOMKill count |
| `network_metrics` | `metrics_collection` | Query P95 Rx/Tx per node |
| `filesystem_metrics` | `metrics_collection` | Query PVC usage and capacity |
| `workload_classifications` | `workload_classification` | Read `is_java` flag from `java` tag presence |
| `workload_config` | `workload_review` | Check `excluded` flag before running analysis |

## Sub-Modules

| Sub-Module | Responsibility |
|---|---|
| `cpu` | Query `cpu_metrics`; compute P50/P95; compute `cpu_util_ratio`; assign CPU state; compute recommendation |
| `memory` | Query `memory_metrics`; compute P50/P95 and `working_set_p95`; count OOMKills; assign memory state; compute recommendation |
| `network` | Query `network_metrics`; compute combined P95 Mbps; detect cross-AZ traffic; set `is_network_intensive`; recommend instance class |
| `storage` | Query `filesystem_metrics`; compute capacity utilization; estimate IOPS from access pattern deltas; set `is_high_iops`; recommend volume type |
| `java_detection` | Check `workload_classifications.tags` for `java` tag; scan container `env` for JVM env vars; set `is_java` flag; apply data maturity hold |
| `batch_detection` | Compute replica P50 from `assembled_snapshots` history; compare to current replica count; set `is_batch_spike` |

## APIs
N/A — this is a pure worker module triggered by NATS events. It exposes no REST endpoints. Analysis results are served to the frontend via the `recommendations` module's API which embeds analysis summaries.

## Dependencies

### Internal Modules
| Module | Usage |
|---|---|
| `common/logger` | Structured logging with `clusterId`, `workloadId`, `analysisVersion`, `dataMaturity` |
| `database` | PostgreSQL pool; percentile queries using `PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value_m)` |
| `events` | NATS subscriber for `cluster.collected` |

### External Services
None — this module reads from and writes to PostgreSQL only.

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `ANALYSIS_VERSION` | (from `package.json`) | Version string stamped on all analysis rows |
| `ANALYSIS_WINDOW_DAYS` | `7` | Rolling window for P50/P95 computation (days) |
| `ANALYSIS_MIN_MATURITY_DAYS` | `7` | Minimum days of metric history before analysis is considered reliable |
| `ANALYSIS_CPU_THROTTLE_RATIO` | `1.0` | P95/request ratio above which CPU state = THROTTLED |
| `ANALYSIS_CPU_OVER_PROVISIONED_RATIO` | `0.25` | P95/request ratio below which CPU state = OVER_PROVISIONED |
| `ANALYSIS_CPU_UNDER_PROVISIONED_RATIO` | `0.80` | P95/request ratio above which CPU state = UNDER_PROVISIONED |
| `ANALYSIS_MEM_OVER_PROVISIONED_RATIO` | `0.40` | Memory P95/request below this = OVER_PROVISIONED |
| `ANALYSIS_MEM_UNDER_PROVISIONED_RATIO` | `0.85` | Memory P95/request above this = UNDER_PROVISIONED |
| `ANALYSIS_NETWORK_INTENSIVE_MBPS` | `100` | P95 combined Mbps threshold for `is_network_intensive = true` |
| `ANALYSIS_HIGH_IOPS_THRESHOLD` | `3000` | Estimated IOPS above which `is_high_iops = true` |
| `ANALYSIS_BATCH_SPIKE_RATIO` | `3.0` | Current replicas / P50 replicas ratio for `is_batch_spike` |
| `ANALYSIS_OOMKILL_SOFT_BLOCK_COUNT` | `3` | OOMKills in 7 days that trigger a soft eligibility block |
| `ANALYSIS_JAVA_WARMUP_EXCLUDE_HOURS` | `24` | Hours of JVM warmup data excluded from P95 for Java workloads |

## Error Handling

| Scenario | Behavior |
|---|---|
| No metric data for a workload | `data_maturity = INSUFFICIENT`; all analysis states = `UNKNOWN`; row still written so downstream eligibility has a record |
| Metric query returns `NULL` P95 (< 2 data points) | Treated as INSUFFICIENT data; states set to `UNKNOWN` |
| CPU request = 0 (no request set) | `cpu_util_ratio = null`; state = `UNKNOWN`; logged as `ANALYSIS_NO_CPU_REQUEST`; soft eligibility warning |
| Memory request = 0 (no request set) | Same as above for memory |
| `workload_config.excluded = true` | Skip analysis entirely for this workload |
| DB write failure | Retry 3× with exponential backoff. On failure, log `ANALYSIS_WRITE_FAILED`; BullMQ job retried |
| Batch spike computation fails (no historical replica data) | `is_batch_spike = false` (safe default); logged at DEBUG |

## Future Enhancements
- **OOMKill event ingestion**: Directly ingest `OOMKilling` Kubernetes events from the agent to improve OOMKill count accuracy (currently estimated from metric gaps)
- **CFS throttle rate**: Ingest cgroup CFS throttle metrics from Kubelet to get precise CPU throttle percentage, not just the ratio-based proxy
- **VPA integration**: If a Vertical Pod Autoscaler is present, read VPA recommendations as a cross-check signal for right-sizing suggestions
- **Replica-count-aware P95**: For high-replica deployments, compute P95 at the percentile-of-pod-averages rather than the percentile-of-all-pod-samples to avoid outlier pods skewing the cluster
- **Seasonal baseline detection**: Detect weekly patterns (e.g., batch jobs that run every Sunday) to separate structural from transient load, improving accuracy of the 7-day P95 window
