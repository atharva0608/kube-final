# database.md — BalanceKube Database Reference

> **Scope:** This document is the authoritative reference for the PostgreSQL database schema, table ownership, data relationships, Redis usage patterns, retention policies, and cross-domain access rules for the BalanceKube platform.

---

## Technology

| Store | Technology | Purpose |
|---|---|---|
| Primary Database | PostgreSQL (RDS Multi-AZ) | All durable business data |
| Cache / Queue | Redis (ElastiCache) | STS creds cache, pricing cache, BullMQ queues, execution locks |
| Event Transport | NATS (Redis Streams fallback) | Domain event pub/sub between services |

---

## Multi-Tenancy and Row-Level Security

Every table that holds customer data includes an `org_id` or `cluster_id` foreign key. PostgreSQL Row-Level Security (RLS) is enabled on all org-scoped tables. Before executing any query, the application sets:

```sql
SET app.current_org_id = '<authenticated_org_id>';
```

PostgreSQL RLS policies automatically filter all queries to the current org. No cross-organisation data leakage is possible at the query layer even if application code forgets to add a `WHERE org_id = ?` clause.

---

## Complete Table Reference

### Platform / Identity Tables

#### `organizations`
```sql
CREATE TABLE organizations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  external_id     UUID NOT NULL UNIQUE,         -- AWS ExternalId for STS assume-role
  aws_role_arn_encrypted TEXT,                  -- AES-256-GCM encrypted
  aws_account_id  TEXT,
  region          TEXT,
  karpenter_control_mode TEXT DEFAULT 'observe', -- 'observe' | 'managed'
  created_at      TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `backend/organizations`  
**Notes:** `external_id` is a UUID generated once per org. Used as `ExternalId` condition in IAM trust policy (confused deputy attack prevention). `karpenter_control_mode` defaults to `observe` — must be explicitly changed to `managed` before Phase 4 can create NodeClaims. `id` is always UUID (never integer) to prevent enumeration.

#### `users`
```sql
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES organizations(id),
  email         TEXT NOT NULL UNIQUE,
  role          TEXT NOT NULL DEFAULT 'operator', -- 'admin' | 'operator' | 'viewer'
  password_hash TEXT NOT NULL,                   -- bcrypt, cost factor 12
  created_at    TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `backend/users`

#### `memberships`
```sql
CREATE TABLE memberships (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id   UUID NOT NULL REFERENCES users(id),
  org_id    UUID NOT NULL REFERENCES organizations(id),
  role      TEXT NOT NULL
);
```
**Owner:** `backend/users`

#### `api_keys`
```sql
CREATE TABLE api_keys (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id),
  key_hash     TEXT NOT NULL,     -- SHA-256 of plaintext key, never stored plaintext
  name         TEXT NOT NULL,
  last_used_at TIMESTAMPTZ,
  created_at   TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `backend/users`

---

### Cluster Registry Tables

#### `clusters`
```sql
CREATE TABLE clusters (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                 UUID NOT NULL REFERENCES organizations(id),
  name                   TEXT,
  region                 TEXT NOT NULL,
  k8s_version            TEXT,
  cluster_arn            TEXT UNIQUE,           -- Globally unique EKS ARN
  cluster_hash           TEXT,                  -- sha256(node_types+counts+az_distribution)
  status                 TEXT DEFAULT 'pending', -- 'pending' | 'active' | 'degraded' | 'unreachable' | 'inactive'
  onboarding_status      TEXT DEFAULT 'pending', -- 'pending' | 'in_progress' | 'complete'
  connection_status      TEXT DEFAULT 'pending', -- 'pending' | 'connected'
  role_arn_encrypted     TEXT,                  -- AES-256-GCM encrypted
  aws_account_id         TEXT,
  karpenter_control_mode TEXT DEFAULT 'observe',
  external_id            UUID NOT NULL,         -- Per-cluster UUID for ExternalId
  created_at             TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `backend/onboarding`

#### `agents`
```sql
CREATE TABLE agents (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id        UUID NOT NULL REFERENCES clusters(id),
  version           TEXT,
  last_heartbeat_at TIMESTAMPTZ,
  status            TEXT DEFAULT 'unregistered', -- 'unregistered' | 'registered' | 'active' | 'degraded' | 'unreachable'
  collection_cycle_count INTEGER DEFAULT 0,
  last_error        TEXT
);
```
**Owner:** `backend/agent_management`

#### `agent_tokens`
```sql
CREATE TABLE agent_tokens (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id    UUID NOT NULL REFERENCES agents(id),
  token_hash  TEXT NOT NULL,     -- SHA-256 of plaintext token
  expires_at  TIMESTAMPTZ,
  rotated_at  TIMESTAMPTZ,
  is_active   BOOLEAN DEFAULT true
);
```
**Owner:** `backend/agent_management`

---

### Phase 1 — Kubernetes Inventory Tables

All inventory tables are scoped to `(cluster_id, snapshot_id)` and are immutable per snapshot cycle.

#### `node_enrichments`
```sql
CREATE TABLE node_enrichments (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id            UUID NOT NULL REFERENCES clusters(id),
  node_name             TEXT NOT NULL,
  asg_name              TEXT,
  lifecycle_state       TEXT,
  reserved_instance     BOOLEAN DEFAULT false,
  collected_at          TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `backend/account_collector`
**Notes:** Populated via AWS API polling (Phase 4/5). Joined with `nodes` during snapshot assembly.

#### `nodes`
```sql
CREATE TABLE nodes (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id            UUID NOT NULL REFERENCES clusters(id),
  snapshot_id           UUID NOT NULL,
  name                  TEXT NOT NULL,
  instance_type         TEXT,
  az                    TEXT,                   -- topology.kubernetes.io/zone
  capacity_cpu_m        INTEGER,                -- millicores
  capacity_memory_mi    INTEGER,                -- MiB
  allocatable_cpu_m     INTEGER,
  allocatable_memory_mi INTEGER,
  labels                JSONB DEFAULT '{}',
  taints                JSONB DEFAULT '[]',
  conditions            JSONB DEFAULT '[]',     -- Ready, MemoryPressure, etc.
  lifecycle             TEXT,                   -- 'spot' | 'on-demand'
  karpenter_nodepool    TEXT,
  nodegroup             TEXT,
  collected_at          TIMESTAMPTZ NOT NULL
);
CREATE INDEX nodes_cluster_snapshot ON nodes(cluster_id, snapshot_id);
```
**Owner:** `backend/cluster_inventory/nodes`

#### `pods`
```sql
CREATE TABLE pods (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id        UUID NOT NULL REFERENCES clusters(id),
  snapshot_id       UUID NOT NULL,
  name              TEXT NOT NULL,
  namespace         TEXT NOT NULL,
  owner_kind        TEXT,                       -- 'Deployment' | 'StatefulSet' | 'DaemonSet'
  owner_name        TEXT,
  node_id           UUID REFERENCES nodes(id),
  phase             TEXT,                       -- 'Running' (only Running stored)
  req_cpu_m         INTEGER,                    -- summed across containers
  req_memory_mi     INTEGER,
  lim_cpu_m         INTEGER,
  lim_memory_mi     INTEGER,
  labels            JSONB DEFAULT '{}',
  annotations       JSONB DEFAULT '{}',
  affinity          JSONB,
  topology_spread   JSONB,
  node_selector     JSONB,
  tolerations       JSONB DEFAULT '[]',
  active_rolling_update BOOLEAN DEFAULT false,
  collected_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX pods_cluster_namespace ON pods(cluster_id, namespace);
```
**Owner:** `backend/cluster_inventory/pods`

#### `deployments`
```sql
CREATE TABLE deployments (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id            UUID NOT NULL REFERENCES clusters(id),
  snapshot_id           UUID NOT NULL,
  name                  TEXT NOT NULL,
  namespace             TEXT NOT NULL,
  replicas              INTEGER,
  available_replicas    INTEGER,
  updated_replicas      INTEGER,
  selector              JSONB,
  labels                JSONB DEFAULT '{}',
  annotations           JSONB DEFAULT '{}',
  active_rolling_update BOOLEAN DEFAULT false,
  collected_at          TIMESTAMPTZ NOT NULL
);
```
**Owner:** `backend/cluster_inventory/deployments`

#### `statefulsets`
```sql
CREATE TABLE statefulsets (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id              UUID NOT NULL REFERENCES clusters(id),
  snapshot_id             UUID NOT NULL,
  name                    TEXT NOT NULL,
  namespace               TEXT NOT NULL,
  replicas                INTEGER,
  ready_replicas          INTEGER,
  updated_replicas        INTEGER,
  volume_claim_templates  JSONB,               -- presence indicates persistent storage
  pod_management_policy   TEXT,               -- 'OrderedReady' | 'Parallel'
  active_rolling_update   BOOLEAN DEFAULT false,
  collected_at            TIMESTAMPTZ NOT NULL
);
```
**Owner:** `backend/cluster_inventory/statefulsets`

#### `daemonsets`
```sql
CREATE TABLE daemonsets (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id               UUID NOT NULL REFERENCES clusters(id),
  snapshot_id              UUID NOT NULL,
  name                     TEXT NOT NULL,
  namespace                TEXT NOT NULL,
  number_available         INTEGER,
  desired_number_scheduled INTEGER,
  update_strategy          TEXT,
  active_rolling_update    BOOLEAN DEFAULT false,
  collected_at             TIMESTAMPTZ NOT NULL
);
```
**Owner:** `backend/cluster_inventory/daemonsets`

#### `pvcs`
```sql
CREATE TABLE pvcs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id    UUID NOT NULL REFERENCES clusters(id),
  snapshot_id   UUID NOT NULL,
  name          TEXT NOT NULL,
  namespace     TEXT NOT NULL,
  storage_class TEXT,
  access_modes  JSONB DEFAULT '[]',
  capacity_gi   FLOAT,
  phase         TEXT,
  pod_id        UUID REFERENCES pods(id),
  az            TEXT,                          -- topology.kubernetes.io/zone if present
  zone_locked   BOOLEAN DEFAULT false,         -- EBS-backed = zone-locked
  collected_at  TIMESTAMPTZ NOT NULL
);
```
**Owner:** `backend/cluster_inventory/pvc`

#### `pdbs`
```sql
CREATE TABLE pdbs (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id         UUID NOT NULL REFERENCES clusters(id),
  snapshot_id        UUID NOT NULL,
  name               TEXT NOT NULL,
  namespace          TEXT NOT NULL,
  selector           JSONB,
  min_available      TEXT,                    -- can be integer or percentage string
  max_unavailable    TEXT,
  current_healthy    INTEGER,
  desired_healthy    INTEGER,
  disruptions_allowed INTEGER,               -- 0 = hard block in eligibility engine
  collected_at       TIMESTAMPTZ NOT NULL
);
```
**Owner:** `backend/cluster_inventory/pdb`

#### `namespaces`
```sql
CREATE TABLE namespaces (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id   UUID NOT NULL REFERENCES clusters(id),
  snapshot_id  UUID NOT NULL,
  name         TEXT NOT NULL,
  labels       JSONB DEFAULT '{}',
  annotations  JSONB DEFAULT '{}',
  phase        TEXT,
  collected_at TIMESTAMPTZ NOT NULL
);
```
**Owner:** `backend/cluster_inventory/namespaces`

---

### Phase 1 — Metrics Tables (Time-Series)

All metrics tables are partitioned by `collected_at` (monthly partitions). Metrics older than 90 days are automatically pruned via partition drops.

#### `cpu_metrics`
```sql
CREATE TABLE cpu_metrics (
  id           UUID DEFAULT gen_random_uuid(),
  cluster_id   UUID NOT NULL,
  pod_id       UUID,
  node_id      UUID,
  value_m      FLOAT NOT NULL,               -- millicores
  source       TEXT,                         -- 'kubelet' | 'metrics_server'
  collected_at TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (collected_at);
CREATE INDEX cpu_metrics_workload ON cpu_metrics(cluster_id, pod_id, collected_at DESC);
```
**Owner:** `backend/metrics_collection/cpu`

#### `memory_metrics`
```sql
CREATE TABLE memory_metrics (
  id           UUID DEFAULT gen_random_uuid(),
  cluster_id   UUID NOT NULL,
  pod_id       UUID,
  node_id      UUID,
  value_mi     FLOAT NOT NULL,               -- MiB
  source       TEXT,
  collected_at TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (collected_at);
```
**Owner:** `backend/metrics_collection/memory`

#### `network_metrics`
```sql
CREATE TABLE network_metrics (
  id           UUID DEFAULT gen_random_uuid(),
  cluster_id   UUID NOT NULL,
  node_id      UUID NOT NULL,
  rx_kbps      FLOAT,
  tx_kbps      FLOAT,
  collected_at TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (collected_at);
```
**Owner:** `backend/metrics_collection/network`

#### `filesystem_metrics`
```sql
CREATE TABLE filesystem_metrics (
  id           UUID DEFAULT gen_random_uuid(),
  cluster_id   UUID NOT NULL,
  node_id      UUID NOT NULL,
  pvc_id       UUID,
  used_gi      FLOAT,
  capacity_gi  FLOAT,
  collected_at TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (collected_at);
```
**Owner:** `backend/metrics_collection/filesystem`

#### `workload_profiles` (Precomputed Percentiles)
```sql
CREATE TABLE workload_profiles (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id        UUID NOT NULL,
  workload_id       TEXT NOT NULL,            -- '{namespace}/{owner_kind}/{owner_name}'
  p50_cpu_m         FLOAT,
  p95_cpu_m         FLOAT,
  p99_cpu_m         FLOAT,
  p50_memory_mi     FLOAT,
  p95_memory_mi     FLOAT,
  p50_replicas      FLOAT,
  p95_replicas      FLOAT,
  window_days       INTEGER DEFAULT 7,
  computed_at       TIMESTAMPTZ NOT NULL,
  UNIQUE(cluster_id, workload_id)
);
```
**Owner:** `backend/metrics_collection`  
**Notes:** Updated by the metrics ingestion worker after each collection cycle. Used by Phase 2 resource analysis to avoid re-computing percentiles on every analysis run.

---

### Phase 1 — Pricing Tables (Global, Not Per-Cluster)

#### `on_demand_prices`
```sql
CREATE TABLE on_demand_prices (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  instance_type   TEXT NOT NULL,
  region          TEXT NOT NULL,
  price_usd_hr    DECIMAL(10,6) NOT NULL,
  updated_at      TIMESTAMPTZ NOT NULL,
  UNIQUE(instance_type, region)
);
```
**Owner:** `backend/pricing_collection/on_demand`

#### `spot_prices`
```sql
CREATE TABLE spot_prices (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  instance_type   TEXT NOT NULL,
  region          TEXT NOT NULL,
  az              TEXT NOT NULL,
  price_usd_hr    DECIMAL(10,6) NOT NULL,
  collected_at    TIMESTAMPTZ NOT NULL
);
CREATE INDEX spot_prices_lookup ON spot_prices(instance_type, az, region, collected_at DESC);
```
**Owner:** `backend/pricing_collection/spot_price`

#### `instance_catalog`
```sql
CREATE TABLE instance_catalog (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  instance_type   TEXT NOT NULL UNIQUE,
  vcpu            INTEGER NOT NULL,
  memory_gi       FLOAT NOT NULL,
  network_perf    TEXT,                    -- 'low' | 'moderate' | 'high' | '10gbps' | '25gbps'
  instance_family TEXT,
  architecture    TEXT DEFAULT 'x86_64',
  updated_at      TIMESTAMPTZ NOT NULL
);
```
**Owner:** `backend/pricing_collection/instance_catalog`

---

### Phase 1 — Spot Risk Tables

#### `interruption_rates`
```sql
CREATE TABLE interruption_rates (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  instance_type   TEXT NOT NULL,
  region          TEXT NOT NULL,
  frequency_band  INTEGER NOT NULL,          -- 0-4 from Spot Advisor
  float_midpoint  FLOAT NOT NULL,            -- midpoint of band range
  updated_at      TIMESTAMPTZ NOT NULL,
  UNIQUE(instance_type, region)
);
```
**Owner:** `backend/spot_risk_collection/interruption_rates`

#### `risk_scores`
```sql
CREATE TABLE risk_scores (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  instance_type    TEXT NOT NULL,
  region           TEXT NOT NULL,
  risk_score       INTEGER NOT NULL,         -- 0-10 internal scale
  interruption_band INTEGER NOT NULL,
  risk_level       TEXT NOT NULL,            -- 'low' | 'medium' | 'high'
  updated_at       TIMESTAMPTZ NOT NULL,
  UNIQUE(instance_type, region)
);
```
**Owner:** `backend/spot_risk_collection/risk_normalization`

#### `spot_risk_history`
```sql
CREATE TABLE spot_risk_history (
  id              UUID DEFAULT gen_random_uuid(),
  instance_type   TEXT NOT NULL,
  region          TEXT NOT NULL,
  risk_score      INTEGER NOT NULL,
  frequency_band  INTEGER NOT NULL,
  recorded_at     TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (recorded_at);  -- Monthly partitions, 90-day retention
```
**Owner:** `backend/spot_risk_collection/historical_dataset`

---

### Phase 1 → Phase 2 — Snapshot Table

#### `assembled_snapshots`
```sql
CREATE TABLE assembled_snapshots (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id       UUID NOT NULL REFERENCES clusters(id),
  cluster_hash     TEXT NOT NULL,           -- sha256(node_types+counts+az_distribution)
  assembly_version INTEGER NOT NULL DEFAULT 1,
  schema_version   INTEGER NOT NULL DEFAULT 1,
  payload          JSONB,                   -- full snapshot if < threshold
  payload_ref      TEXT,                   -- S3 URI if payload too large for DB
  collected_at     TIMESTAMPTZ NOT NULL
);
CREATE INDEX assembled_snapshots_cluster ON assembled_snapshots(cluster_id, collected_at DESC);
```
**Owner:** `backend/snapshot_assembly`  
**Notes:** Immutable after assembly. Never mutated. Retained for 7 days (cleanup job drops old rows). All Phase 2, 3, 4 engines read from this table exclusively — never from raw inventory tables directly. `cluster_hash` change = topology change = all stale recommendations are automatically invalidated.

---

### Phase 2 — Workload Intelligence Tables

#### `workload_reviews`
```sql
CREATE TABLE workload_reviews (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id   UUID NOT NULL REFERENCES clusters(id),
  snapshot_id  UUID NOT NULL,
  review_type  TEXT NOT NULL,              -- 'initial' | 'partial'
  status       TEXT DEFAULT 'pending',     -- 'pending' | 'complete'
  created_at   TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  completed_by UUID REFERENCES users(id)
);
```
**Owner:** `backend/workload_review`

#### `review_items`
```sql
CREATE TABLE review_items (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id    UUID NOT NULL REFERENCES workload_reviews(id),
  workload_id  TEXT NOT NULL,
  namespace    TEXT,
  owner_kind   TEXT,
  owner_name   TEXT,
  detected_type TEXT,
  status       TEXT DEFAULT 'pending',     -- 'pending' | 'confirmed' | 'overridden'
  created_at   TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `backend/workload_review`

#### `workload_config`
```sql
CREATE TABLE workload_config (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id            UUID NOT NULL REFERENCES clusters(id),
  workload_id           TEXT NOT NULL,         -- '{namespace}/{kind}/{name}'
  review_status         TEXT DEFAULT 'pending_review', -- 'pending_review' | 'confirmed'
  workload_type_override TEXT,                -- overrides auto-detection
  workload_purpose      TEXT,                 -- WEB | API | WORKER | BATCH | DATABASE | CACHE | QUEUE | STREAMING | MONITORING | SECURITY | SYSTEM | ML | GPU
  business_criticality  TEXT,                 -- 'CRITICAL' | 'IMPORTANT' | 'STANDARD' — operator-set only
  application_group_id  UUID,
  placement_intent      TEXT,                 -- 'SPOT' | 'ON_DEMAND' | 'MIXED'
  excluded              BOOLEAN DEFAULT false,
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now(),
  UNIQUE(cluster_id, workload_id)
);
```
**Owner:** `backend/workload_review`

#### `workload_tags`
```sql
CREATE TABLE workload_tags (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id       UUID NOT NULL REFERENCES clusters(id),
  workload_id      TEXT NOT NULL,
  analysis_version INTEGER NOT NULL,
  tags             JSONB NOT NULL DEFAULT '[]',   -- list of tag strings
  tag_source       JSONB NOT NULL DEFAULT '{}',   -- map of tag -> source
  classification   TEXT,                          -- DAEMON | STATEFUL | BATCH | WEB | WORKER
  type_source      TEXT,                          -- 'auto' | 'operator_override'
  created_at       TIMESTAMPTZ DEFAULT now(),
  UNIQUE(cluster_id, workload_id, analysis_version)
);
```
**Owner:** `backend/workload_classification/tag_generation`  
**Notes:** Rows are deleted and reinserted on every analysis cycle — stale tags never accumulate.

#### `workload_classifications`
```sql
CREATE TABLE workload_classifications (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id       UUID NOT NULL REFERENCES clusters(id),
  workload_id      TEXT NOT NULL,
  analysis_version INTEGER NOT NULL,
  classification   TEXT NOT NULL,
  confidence       FLOAT,
  is_java          BOOLEAN DEFAULT false,
  is_batch_spike   BOOLEAN DEFAULT false,
  created_at       TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `backend/workload_classification`

#### `workload_analysis`
```sql
CREATE TABLE workload_analysis (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id       UUID NOT NULL REFERENCES clusters(id),
  workload_id      TEXT NOT NULL,
  analysis_version INTEGER NOT NULL,
  cpu_analysis     JSONB NOT NULL DEFAULT '{}',     -- {state, util_ratio, p95_m, request_m, burstiness}
  memory_analysis  JSONB NOT NULL DEFAULT '{}',     -- {state, util_ratio, p95_mi, request_mi, oom_risk}
  network_analysis JSONB NOT NULL DEFAULT '{}',     -- {p95_mbps, is_network_intensive}
  storage_analysis JSONB NOT NULL DEFAULT '{}',     -- {iops_estimate, throughput, capacity_util_pct}
  data_maturity    TEXT NOT NULL DEFAULT 'INSUFFICIENT', -- 'MATURE' | 'SUFFICIENT' | 'INSUFFICIENT'
  snapshot_id      UUID NOT NULL,
  created_at       TIMESTAMPTZ DEFAULT now(),
  UNIQUE(cluster_id, workload_id, analysis_version)
);
```
**Owner:** `backend/resource_analysis`

#### `eligibility_verdicts`
```sql
CREATE TABLE eligibility_verdicts (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id          UUID NOT NULL REFERENCES clusters(id),
  workload_id         TEXT NOT NULL,
  analysis_version    INTEGER NOT NULL,
  verdict             TEXT NOT NULL,           -- 'ELIGIBLE' | 'ELIGIBLE_WITH_CONDITIONS' | 'NOT_ELIGIBLE'
  decision_reasons    JSONB NOT NULL DEFAULT '[]',  -- ordered list of human-readable facts
  positive_signals    JSONB NOT NULL DEFAULT '[]',  -- signals shown even for blocked workloads
  conditions          JSONB NOT NULL DEFAULT '[]',  -- list of COND-* warnings
  block_reason        TEXT,
  eligibility_source  TEXT,                    -- 'auto' | 'operator_override'
  operator_override_id UUID REFERENCES operator_overrides(id),
  created_at          TIMESTAMPTZ DEFAULT now(),
  UNIQUE(cluster_id, workload_id, analysis_version)
);
```
**Owner:** `backend/eligibility_engine`

#### `operator_overrides`
```sql
CREATE TABLE operator_overrides (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id               UUID NOT NULL REFERENCES clusters(id),
  workload_id              TEXT NOT NULL,
  spot_eligible            BOOLEAN,            -- true=force eligible, false=force blocked
  target_instance_families TEXT[],
  max_risk_score           INTEGER,
  set_by                   UUID NOT NULL REFERENCES users(id),
  set_at                   TIMESTAMPTZ DEFAULT now(),
  note                     TEXT,
  UNIQUE(cluster_id, workload_id)
);
```
**Owner:** `backend/eligibility_engine/operator_overrides`

#### `application_group_definitions`
```sql
CREATE TABLE application_group_definitions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id        UUID NOT NULL REFERENCES clusters(id),
  name              TEXT NOT NULL,
  placement         TEXT NOT NULL,             -- 'SPOT' | 'ON_DEMAND' | 'MIXED'
  business_criticality TEXT,
  latency_sensitive BOOLEAN DEFAULT false,
  created_at        TIMESTAMPTZ DEFAULT now(),
  UNIQUE(cluster_id, name)
);
```
**Owner:** `backend/workload_review`

#### `recommendation_store`
```sql
CREATE TABLE recommendation_store (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id            UUID NOT NULL REFERENCES clusters(id),
  snapshot_id           UUID NOT NULL,
  analysis_version      INTEGER NOT NULL,
  cluster_hash          TEXT NOT NULL,
  status                TEXT DEFAULT 'generated', -- 'generated' | 'pending_approval' | 'approved' | 'executing' | 'success' | 'rolled_back' | 'invalidated' | 'stale'
  total_savings_monthly DECIMAL(12,4),
  created_at            TIMESTAMPTZ DEFAULT now(),
  approved_at           TIMESTAMPTZ,
  approved_by           UUID REFERENCES users(id),
  plan_delta_at         TIMESTAMPTZ,
  invalidated_at        TIMESTAMPTZ,
  invalidation_reason   TEXT
);
```
**Owner:** `backend/recommendations`

#### `savings_estimates`
```sql
CREATE TABLE savings_estimates (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recommendation_id         UUID NOT NULL REFERENCES recommendation_store(id),
  workload_id               TEXT NOT NULL,
  current_instance_type     TEXT,
  current_cost_monthly      DECIMAL(12,4),
  recommended_instance_type TEXT,
  spot_cost_monthly         DECIMAL(12,4),
  savings_monthly           DECIMAL(12,4),
  savings_pct               FLOAT,
  spot_risk_score           INTEGER,
  pricing_freshness         TEXT,              -- 'FRESH' | 'STALE_PRICING'
  pricing_freshness_at      TIMESTAMPTZ,
  savings_available         BOOLEAN DEFAULT true
);
```
**Owner:** `backend/recommendations`

---

### Phase 3 — Drift Detection Tables

#### `drift_events`
```sql
CREATE TABLE drift_events (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id        UUID NOT NULL REFERENCES clusters(id),
  recommendation_id UUID NOT NULL REFERENCES recommendation_store(id),
  drift_type        TEXT NOT NULL,            -- 'WORKLOAD_LEVEL' | 'NODE_COMPOSITION' | 'PLACEMENT_MISMATCH' | 'PRICING_SHIFT' | 'REPLICA_SPIKE' | 'APPLICATION_GROUP_CHANGE'
  severity          TEXT NOT NULL,            -- 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  patchable         BOOLEAN NOT NULL,
  affected_workloads JSONB DEFAULT '[]',
  reason            TEXT,
  detected_at       TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `backend/drift_detection/snapshot_comparator`

#### `plan_deltas`
```sql
CREATE TABLE plan_deltas (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recommendation_id UUID NOT NULL REFERENCES recommendation_store(id),
  delta_payload     JSONB NOT NULL,
  created_at        TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `backend/drift_detection/plan_delta`

---

### Phase 4 — Execution Tables

#### `execution_history`
```sql
CREATE TABLE execution_history (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id              UUID NOT NULL REFERENCES clusters(id),
  recommendation_id       UUID NOT NULL REFERENCES recommendation_store(id),
  status                  TEXT NOT NULL,       -- 'queued' | 'running' | 'success' | 'rolled_back' | 'aborted'
  execution_mode          TEXT NOT NULL,       -- 'OBSERVE' | 'PLAN_ONLY' | 'PLAN_AND_EXECUTE'
  started_at              TIMESTAMPTZ,
  completed_at            TIMESTAMPTZ,
  duration_seconds        INTEGER,
  nodes_provisioned       INTEGER DEFAULT 0,
  nodes_drained           INTEGER DEFAULT 0,
  workloads_migrated      INTEGER DEFAULT 0,
  savings_realised_monthly DECIMAL(12,4),
  failure_reason          TEXT,
  rollback_reason         TEXT,
  created_at              TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `backend/execution/execution_history`

#### `execution_results` (Per-Step Detail)
```sql
CREATE TABLE execution_results (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  execution_id  UUID NOT NULL REFERENCES execution_history(id),
  step_type     TEXT NOT NULL,               -- 'DRAIN_SOURCE_NODE' | 'CREATE_KARPENTER_NODECLAIM' | etc.
  step_order    INTEGER NOT NULL,
  status        TEXT NOT NULL,              -- 'pending' | 'running' | 'success' | 'failed' | 'skipped'
  state_before  JSONB,
  state_after   JSONB,
  error         TEXT,
  started_at    TIMESTAMPTZ,
  completed_at  TIMESTAMPTZ
);
```
**Owner:** `backend/execution/execution_history`

#### `execution_locks`
```sql
CREATE TABLE execution_locks (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id   UUID NOT NULL UNIQUE REFERENCES clusters(id),
  acquired_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at   TIMESTAMPTZ NOT NULL,
  execution_id UUID REFERENCES execution_history(id)
);
```
**Owner:** `backend/execution/lock_manager`  
**Notes:** This is the DB fallback. Primary lock is Redis `SET NX EX`. DB table used for auditing which execution holds the lock.

#### `rollback_snapshots`
```sql
CREATE TABLE rollback_snapshots (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  execution_id UUID NOT NULL REFERENCES execution_history(id),
  cluster_id   UUID NOT NULL REFERENCES clusters(id),
  payload      JSONB,                         -- node labels/taints/placement state
  payload_ref  TEXT,                         -- S3 URI if payload too large
  created_at   TIMESTAMPTZ DEFAULT now(),
  status       TEXT DEFAULT 'active'          -- 'active' | 'retired' | 'restored'
);
```
**Owner:** `backend/rollback`

---

### Platform Cross-Cutting Tables

#### `audit_logs`
```sql
CREATE TABLE audit_logs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES organizations(id),
  actor_id      UUID REFERENCES users(id),
  action        TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id   UUID,
  before        JSONB,
  after         JSONB,
  ip_address    TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);
-- Append-only: PostgreSQL trigger RAISES EXCEPTION on UPDATE or DELETE
CREATE INDEX audit_logs_org_actor ON audit_logs(org_id, actor_id, created_at DESC);
```
**Owner:** `backend/audit_logs`

#### `event_store`
```sql
CREATE TABLE event_store (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type     TEXT NOT NULL,
  payload        JSONB NOT NULL,
  schema_version INTEGER NOT NULL DEFAULT 1,
  published      BOOLEAN DEFAULT false,
  emitted_at     TIMESTAMPTZ DEFAULT now(),
  published_at   TIMESTAMPTZ,
  cluster_id     UUID
);
CREATE INDEX event_store_unpublished ON event_store(published, emitted_at) WHERE published = false;
```
**Owner:** `backend/events`  
**Notes:** Outbox pattern — events are written here BEFORE being published to NATS. A sweeper job retries unpublished events at-least-once.

#### `itn_events`
```sql
CREATE TABLE itn_events (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cluster_id       UUID NOT NULL REFERENCES clusters(id),
  node_id          UUID,
  node_name        TEXT NOT NULL,
  instance_id      TEXT NOT NULL,
  notice_type      TEXT NOT NULL,             -- 'ITN' | 'REBALANCE_RECOMMENDATION'
  termination_time TIMESTAMPTZ,
  detected_at      TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `backend/itn_handler`

#### `dead_letter_jobs`
```sql
CREATE TABLE dead_letter_jobs (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  worker       TEXT NOT NULL,
  job_payload  JSONB NOT NULL,
  error        TEXT NOT NULL,
  attempts     INTEGER NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT now()
);
```
**Owner:** `workers/common`

#### `notifications`
```sql
CREATE TABLE notifications (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      UUID NOT NULL REFERENCES organizations(id),
  type        TEXT NOT NULL,
  recipient   TEXT,
  payload     JSONB NOT NULL,
  sent_at     TIMESTAMPTZ,
  status      TEXT DEFAULT 'pending'          -- 'pending' | 'sent' | 'failed' | 'dead_lettered'
);
```
**Owner:** `backend/notifications`

---

## Redis Usage Patterns

| Key Pattern | Value | TTL | Purpose |
|---|---|---|---|
| `sts_creds:{cluster_id}` | STS temp credentials JSON | `expiry - 60s` | Cached assumed-role credentials |
| `price:{instance_type}:{az}` | Spot price decimal | `600s` | Fast spot price lookup for savings estimator |
| `od_price:{instance_type}:{region}` | On-demand price decimal | `86400s` | Fast OD price lookup |
| `spot_risk:{instance_type}:{region}` | Risk score integer | `86400s` | Cached Spot Advisor risk score |
| `execution_lock:{cluster_id}` | Execution ID | `1800s` | Distributed cluster execution lock (SET NX EX) |
| `bk_bullmq:*` | BullMQ job queue data | Managed by BullMQ | Worker job queues (per worker type) |

**Key rule:** Redis is NEVER used as durable storage. If Redis goes down:
- STS credentials: re-fetched from AWS STS
- Pricing data: read from PostgreSQL
- Spot risk: read from PostgreSQL
- Execution lock: falls back to `execution_locks` table

---

## Table Ownership Map

Every table has a single owning backend module. Only that module may write to the table.

| Table | Owner Domain | Owner Module |
|---|---|---|
| `organizations` | Onboarding | `backend/organizations` |
| `users` | Users | `backend/users` |
| `memberships` | Users | `backend/users` |
| `api_keys` | Users | `backend/users` |
| `clusters` | Onboarding | `backend/onboarding` |
| `agents` | Agent Management | `backend/agent_management` |
| `agent_tokens` | Agent Management | `backend/agent_management` |
| `node_enrichments` | Account Collector | `backend/account_collector` |
| `nodes` | Cluster Inventory | `backend/cluster_inventory/nodes` |
| `pods` | Cluster Inventory | `backend/cluster_inventory/pods` |
| `deployments` | Cluster Inventory | `backend/cluster_inventory/deployments` |
| `statefulsets` | Cluster Inventory | `backend/cluster_inventory/statefulsets` |
| `daemonsets` | Cluster Inventory | `backend/cluster_inventory/daemonsets` |
| `pvcs` | Cluster Inventory | `backend/cluster_inventory/pvc` |
| `pdbs` | Cluster Inventory | `backend/cluster_inventory/pdb` |
| `namespaces` | Cluster Inventory | `backend/cluster_inventory/namespaces` |
| `cpu_metrics` | Metrics Collection | `backend/metrics_collection/cpu` |
| `memory_metrics` | Metrics Collection | `backend/metrics_collection/memory` |
| `network_metrics` | Metrics Collection | `backend/metrics_collection/network` |
| `filesystem_metrics` | Metrics Collection | `backend/metrics_collection/filesystem` |
| `workload_profiles` | Metrics Collection | `backend/metrics_collection` |
| `on_demand_prices` | Pricing Collection | `backend/pricing_collection/on_demand` |
| `spot_prices` | Pricing Collection | `backend/pricing_collection/spot_price` |
| `instance_catalog` | Pricing Collection | `backend/pricing_collection/instance_catalog` |
| `interruption_rates` | Spot Risk | `backend/spot_risk_collection/interruption_rates` |
| `risk_scores` | Spot Risk | `backend/spot_risk_collection/risk_normalization` |
| `spot_risk_history` | Spot Risk | `backend/spot_risk_collection/historical_dataset` |
| `assembled_snapshots` | Snapshot Assembly | `backend/snapshot_assembly` |
| `workload_reviews` | Workload Review | `backend/workload_review` |
| `review_items` | Workload Review | `backend/workload_review` |
| `workload_config` | Workload Review | `backend/workload_review` |
| `workload_tags` | Classification | `backend/workload_classification/tag_generation` |
| `workload_classifications` | Classification | `backend/workload_classification` |
| `workload_analysis` | Resource Analysis | `backend/resource_analysis` |
| `eligibility_verdicts` | Eligibility Engine | `backend/eligibility_engine` |
| `operator_overrides` | Eligibility Engine | `backend/eligibility_engine/operator_overrides` |
| `application_group_definitions` | Workload Review | `backend/workload_review` |
| `recommendation_store` | Recommendations | `backend/recommendations` |
| `savings_estimates` | Recommendations | `backend/recommendations` |
| `drift_events` | Drift Detection | `backend/drift_detection/snapshot_comparator` |
| `plan_deltas` | Drift Detection | `backend/drift_detection/plan_delta` |
| `execution_history` | Execution | `backend/execution/execution_history` |
| `execution_results` | Execution | `backend/execution/execution_history` |
| `execution_locks` | Execution | `backend/execution/lock_manager` |
| `rollback_snapshots` | Rollback | `backend/rollback` |
| `audit_logs` | Audit | `backend/audit_logs` |
| `event_store` | Events | `backend/events` |
| `itn_events` | Execution | `backend/itn_handler` |
| `dead_letter_jobs` | Workers | `workers/common` |
| `notifications` | Notifications | `backend/notifications` |

### Cross-Domain Access Rules

1. A module that needs data from another domain's table **must call that domain's service layer function**, not issue a raw SQL query.
2. Migrations for a table **must be authored by the owning domain's team**.
3. Cross-domain `JOIN`s are permitted in **read-only analytical queries** (e.g. dashboard aggregations) but must be clearly marked with a `-- cross-domain read` comment.
4. **No direct writes** to a table you do not own. Ever.

---

## Retention Policies

| Data | Retention | Mechanism |
|---|---|---|
| `assembled_snapshots` | 7 days | Scheduled cleanup job drops rows older than 7 days |
| Metrics tables (cpu, memory, network, filesystem) | 90 days | Monthly partition drops |
| `spot_risk_history` | 90 days | Monthly partition drops |
| `spot_prices` | 30 days | Scheduled cleanup job |
| `rollback_snapshots` | Until execution success (then `retired`) | Status-based cleanup |
| `recommendation_store` | 90 days after `success` or `rolled_back` | Archival/compression |
| `audit_logs` | Indefinite (compliance) | No automated deletion |
| `event_store` | 30 days (after published) | Scheduled cleanup of published events |
| `dead_letter_jobs` | Indefinite (until resolved) | Manual resolution required |

---

## Key Data Relationships

```
Organization
  └── Clusters (many per org)
        ├── Agents (one per cluster)
        │     └── Agent Tokens (one active at a time)
        ├── assembled_snapshots (many, 7-day retention)
        │     └── nodes, pods, deployments, statefulsets, daemonsets, pvcs, pdbs, namespaces
        ├── cpu_metrics, memory_metrics, network_metrics, filesystem_metrics (90-day time-series)
        ├── workload_reviews → review_items, workload_config
        ├── workload_tags, workload_classifications (per analysis_version)
        ├── workload_analysis (per analysis_version)
        ├── eligibility_verdicts + operator_overrides (per analysis_version)
        ├── recommendation_store
        │     └── savings_estimates (per workload)
        ├── drift_events → plan_deltas (per recommendation)
        └── execution_history → execution_results → rollback_snapshots

Global (not per-cluster):
  on_demand_prices, spot_prices, instance_catalog
  interruption_rates, risk_scores, spot_risk_history
```

---

## Migration Strategy

- Migrations use `golang-migrate` (backend) or `node-pg-migrate` (Node.js workers).
- All migrations are **sequential, version-controlled, and forward-only** (no rollback migrations).
- Each migration file is owned by the domain team responsible for the table.
- Migration filenames: `{sequence}_{domain}_{description}.sql` (e.g. `0042_recommendations_add_invalidated_at.sql`).
- Run by: `scripts/migrate.sh` — idempotent (safe to re-run).
- Production: migrations run as part of the deployment pipeline before any service restart.

---

*This document is generated from the BalanceKube architecture definition. When a table schema changes, both this file and the owning module's `.md` file must be updated in the same PR.*
