# snapshot_assembly

## Purpose
The `snapshot_assembly` module combines all Phase 1 data sources — Kubernetes inventory, enriched node metadata, real-time pricing, and spot risk scores — into a single immutable `assembled_snapshot` JSONB blob for each cluster collection cycle. It exists as a separate module because it is the critical contract boundary: all Phase 2, Phase 3, and Phase 4 engines read exclusively from `assembled_snapshots` and never query raw inventory, metrics, or pricing tables directly. This ensures that the pipeline operates on a consistent, point-in-time view of the world.

## Responsibilities
- Trigger immediately when the backend receives a successful inventory POST from the agent
- Perform a multi-source JOIN across:
  - **Layer 2** (Agent): node and pod inventory from `cluster_inventory` tables, scoped to the incoming `snapshot_id`
  - **Layer 3** (Account Collector): node enrichment data from platform-side AWS account polling (instance lifecycle, AZ topology, managed node group membership)
  - **Layer 1** (Platform Cache): current on-demand and spot pricing from Redis / `pricing_collection` tables; spot risk scores from Redis / `spot_risk_collection` tables
- Use LEFT JOINs for enrichment — assembly never blocks if Layer 3 enrichment is delayed or unavailable
- Compute a `cluster_hash` (SHA-256 of node instance types + counts + AZ distribution) that uniquely identifies the cluster topology
- Assign an immutable `snapshot_id` (UUID v4), `assembly_version`, and `schema_version` to every assembled snapshot
- Write the completed blob to `assembled_snapshots` as a JSONB payload
- Publish the `cluster.collected` event to trigger downstream Phase 2 processing
- Enforce the hard rule: no Phase 2/3/4 module queries `nodes`, `pods`, `deployments`, etc. directly — all reads go through `assembled_snapshots`
- Prune `assembled_snapshots` rows older than 7 days

## Inputs

### From BullMQ (Job Trigger)
- **Source**: BullMQ job `snapshot-assembly` enqueued by `cluster_inventory` after a successful inventory push
- **Format**: `{ clusterId: string, snapshotId: string, collectedAt: string }`

### Layer 2 — Kubernetes Inventory (Database Read)
- **Source**: Direct PostgreSQL reads from: `nodes`, `pods`, `deployments`, `statefulsets`, `daemonsets`, `pvcs`, `pdbs`, `namespaces` — all filtered by `snapshot_id`
- **Format**: Rows from each table, joined by `snapshot_id` and `cluster_id`

### Layer 3 — Node Enrichment (Platform-Side Account Collector)
- **Source**: PostgreSQL table `node_enrichments` (populated by account_collector worker that polls EC2 metadata for each registered cluster)
- **Key Fields**: `instance_lifecycle` (on-demand/spot/scheduled), `managed_node_group_name`, `asg_name`, `launch_template_id`, `capacity_type`, `az`, `subnet_id`, `root_volume_type`, `root_volume_size_gi`
- **JOIN**: LEFT JOIN on `(cluster_id, provider_node_id)` — if enrichment row is absent, that node's enrichment fields are null

### Layer 1 — Pricing (Redis → PostgreSQL Fallback)
- **Source**: Redis cache `price:{instance_type}:{az}` and `price:ondemand:{instance_type}:{region}`
- **Fallback**: If Redis miss, query `spot_prices` (most recent row per instance_type + az) and `on_demand_prices`

### Layer 1 — Spot Risk (Redis → PostgreSQL Fallback)
- **Source**: Redis cache `risk:{instance_type}:{region}`
- **Fallback**: If Redis miss, query `risk_scores` table

## Outputs

### Assembled Snapshot Schema
The `assembled_snapshots.payload` JSONB field contains:
```typescript
{
  snapshot_id: string;           // UUID v4 — immutable
  cluster_id: string;
  collected_at: string;          // ISO 8601 — from agent push
  assembled_at: string;          // ISO 8601 — when assembly completed
  schema_version: string;        // e.g. "2.1"
  assembly_version: string;      // e.g. "1.3.0" (BalanceKube release version)
  cluster_hash: string;          // SHA-256 of topology signature

  kubernetes: {
    nodes: AssembledNode[];
    pods: AssembledPod[];
    deployments: AssembledDeployment[];
    statefulsets: AssembledStatefulSet[];
    daemonsets: AssembledDaemonSet[];
    pvcs: AssembledPVC[];
    pdbs: AssembledPDB[];
    namespaces: AssembledNamespace[];
    labels: Record<string, string>;  // cluster-level labels
    affinity_rules: AffinityRule[];
    taints: Taint[];
  };

  enrichment: {
    nodes: {
      [providerNodeId: string]: {
        instance_lifecycle: 'on-demand' | 'spot' | 'scheduled' | null;
        managed_node_group_name: string | null;
        asg_name: string | null;
        launch_template_id: string | null;
        capacity_type: string | null;
        subnet_id: string | null;
        root_volume_type: string | null;
        root_volume_size_gi: number | null;
      };
    };
    enrichment_coverage_percent: number;  // % of nodes with full enrichment
  };

  pricing: {
    on_demand: {
      [instanceType: string]: {
        price_usd_hr: number;
        price_usd_month: number;
        region: string;
      };
    };
    spot: {
      [instanceType: string]: {
        [az: string]: {
          price_usd_hr: number;
          collected_at: string;
        };
      };
    };
    instance_catalog: {
      [instanceType: string]: {
        vcpu: number;
        memory_gi: number;
        network_perf: string;
        family: string;
      };
    };
    pricing_freshness: {
      on_demand_age_hours: number;
      spot_age_minutes: number;
    };
  };

  spot_risk: {
    risk_scores: {
      [instanceType: string]: {
        [region: string]: {
          risk_score: number;   // 0-10
          risk_level: string;   // 'low' | 'medium' | 'high'
          interruption_band: string;
          updated_at: string;
        };
      };
    };
    historical_dataset_ref: string;  // pointer to spot_risk_history query params
    risk_data_age_hours: number;
  };
}
```

### cluster_hash Computation
```
cluster_hash = SHA-256(
  sorted array of (instance_type × count per AZ)
)
```
A change in `cluster_hash` between two consecutive snapshots means a topology change occurred. This triggers `drift.detected` and invalidates all stale recommendations.

### Database Write
| Table | Write Pattern |
|---|---|
| `assembled_snapshots` | Insert one row per assembly: `(id UUID, cluster_id, snapshot_at TIMESTAMPTZ, cluster_hash VARCHAR, assembly_version VARCHAR, schema_version VARCHAR, payload JSONB)` |

### NATS Event Published
- **Event**: `cluster.collected`
- **Payload**:
```json
{
  "clusterId": "string",
  "snapshotId": "string",
  "clusterHash": "string",
  "collectedAt": "ISO 8601",
  "assembledAt": "ISO 8601",
  "assemblyVersion": "string",
  "enrichmentCoveragePercent": 97.5
}
```

## Events Produced
| Event | Description |
|---|---|
| `cluster.collected` | Published after the assembled snapshot is committed to PostgreSQL. Carries `snapshotId`, `clusterHash`, and `enrichmentCoveragePercent`. Triggers workload_review gate check and Phase 2 pipeline. |

## Events Consumed
N/A — snapshot assembly is triggered by a BullMQ job enqueued by `cluster_inventory`, not by a NATS event.

## Database Tables

### Tables Owned (Written)
| Table | Key Columns | Notes |
|---|---|---|
| `assembled_snapshots` | `id UUID PK`, `cluster_id UUID FK`, `snapshot_at TIMESTAMPTZ`, `cluster_hash VARCHAR(64)`, `assembly_version VARCHAR`, `schema_version VARCHAR`, `payload JSONB`, `created_at TIMESTAMPTZ` | 7-day retention enforced by pruning worker. JSONB is compressed at the PostgreSQL level (TOAST). Indexed on `(cluster_id, snapshot_at DESC)` for latest-snapshot lookups. |

### HARD RULE — Tables Read (Cross-Domain)
The following tables are read during assembly and then never again by any Phase 2/3/4 module:

| Table | Purpose in Assembly |
|---|---|
| `nodes` | Layer 2: node inventory for this snapshot |
| `pods` | Layer 2: pod inventory for this snapshot |
| `deployments` | Layer 2: deployment specs |
| `statefulsets` | Layer 2: statefulset specs |
| `daemonsets` | Layer 2: daemonset specs |
| `pvcs` | Layer 2: PVC zone metadata |
| `pdbs` | Layer 2: PDB disruption budgets |
| `namespaces` | Layer 2: namespace labels |
| `node_enrichments` | Layer 3: per-node EC2 metadata (LEFT JOIN) |
| `on_demand_prices` | Layer 1: pricing fallback (Redis miss) |
| `spot_prices` | Layer 1: pricing fallback (Redis miss) |
| `instance_catalog` | Layer 1: vCPU/memory catalog |
| `risk_scores` | Layer 1: risk score fallback (Redis miss) |

> ⚠️ **Architectural invariant**: After `cluster.collected` is published, all downstream modules (workload_classification, resource_analysis, eligibility_engine, recommendations, drift_detection, execution) query `assembled_snapshots` via `SELECT payload FROM assembled_snapshots WHERE cluster_id = $1 ORDER BY snapshot_at DESC LIMIT 1`. They do NOT join raw inventory tables.

## APIs
N/A — snapshot assembly is an internal worker process triggered by BullMQ. It exposes no REST endpoints.

## Dependencies

### Internal Modules
| Module | Usage |
|---|---|
| `common/logger` | Structured logging with `clusterId`, `snapshotId`, `assemblyVersion` context |
| `database` | PostgreSQL pool; transaction for atomic insert |
| `events` | NATS publisher for `cluster.collected` |

### External Services
| Service | Usage |
|---|---|
| Redis | Read spot prices (`price:{instance_type}:{az}`) and risk scores (`risk:{instance_type}:{region}`) |
| BullMQ | Job queue consumer for `snapshot-assembly` jobs |

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `ASSEMBLY_SCHEMA_VERSION` | `2.1` | Schema version stamped on each assembled snapshot |
| `ASSEMBLY_VERSION` | (from `package.json`) | BalanceKube release version stamped on each snapshot |
| `SNAPSHOT_RETENTION_DAYS` | `7` | Days before `assembled_snapshots` rows are pruned |
| `SNAPSHOT_PRUNE_CRON` | `0 5 * * *` | Cron for snapshot pruning worker (5 AM UTC daily) |
| `ASSEMBLY_ENRICHMENT_TIMEOUT_MS` | `2000` | Max wait for enrichment DB query before proceeding with null enrichment fields |
| `ASSEMBLY_PRICING_FALLBACK_MAX_AGE_HOURS` | `48` | If DB pricing data is older than this, stamp `pricing_freshness.stale = true` in payload |
| `CLUSTER_HASH_ALGO` | `sha256` | Hash algorithm for cluster topology fingerprint |

## Error Handling

| Scenario | Behavior |
|---|---|
| Enrichment data absent for a node | LEFT JOIN returns null enrichment fields for that node; assembly proceeds. `enrichment_coverage_percent` reflects the gap. Not a failure. |
| Redis miss for pricing or risk | Fall back to direct DB query. If DB also misses (e.g., brand new region), write null pricing/risk for that instance type. Assembly proceeds. |
| DB write of `assembled_snapshots` fails | Retry 3× with exponential backoff. On persistent failure, log `ASSEMBLY_WRITE_FAILED`; create dead-letter job; `cluster.collected` is NOT published for this cycle. Agent will push again on next collection cycle. |
| `cluster.collected` NATS publish fails | Outbox pattern: the event is persisted to `event_store` during the same transaction as the snapshot insert. A reconciliation worker replays un-published events within 30 seconds. |
| Snapshot pruning fails | Logged; skipped; next daily run will prune the combined window. Excess rows have no impact on correctness. |
| cluster_hash computation fails | Assembly aborts; returns `500` to the job queue; BullMQ retries. This is a programming error that must not be silently ignored. |

## Future Enhancements
- **Incremental snapshot diffs**: Instead of storing a full JSONB blob per cycle, store a base snapshot and compressed diffs for subsequent cycles to reduce storage volume
- **Schema migration support**: Add a snapshot schema migrator so that older snapshots (stored under a previous `schema_version`) can be projected forward to the current schema without reprocessing
- **Streaming assembly**: Pipeline the multi-source JOIN using streaming queries to reduce memory footprint for very large clusters (10,000+ pods)
- **Enrichment source extensibility**: Add a plugin interface so that additional enrichment sources (e.g., Datadog APM tags, custom annotations) can be contributed to the assembled payload
- **Cross-cluster comparison**: Support a multi-cluster assembled view that aggregates snapshots from all clusters in an org for global savings estimation
