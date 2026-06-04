# workload_classification

## Purpose
The `workload_classification` module implements Phase 2 Engine 1A: tag generation and workload type classification. It transforms the structured metadata in an assembled snapshot (container images, Kubernetes resource kind, PVC bindings, HPA presence, namespace, resource requests) into a set of deterministic semantic tags and a single canonical `workload_type`. It exists as a separate module because classification is a stateless, rule-driven transformation that must be independently testable, versioned, and replaceable without affecting other Phase 2 engines.

## Responsibilities
- Subscribe to `cluster.collected` events and run classification on the assembled snapshot
- Generate semantic tags for each workload — tags are **not mutually exclusive** (e.g., a Redis StatefulSet receives `stateful`, `cache`, and `database` tags simultaneously)
- Each tag has a deterministic detection rule and a `tag_source` field indicating which sub-module detected it
- Assign a canonical `workload_type` from a priority-ordered type hierarchy
- Delete and reinsert `workload_tags` rows on every cycle — no stale tags ever accumulate
- Write `workload_classifications` with the resolved `workload_type` and `analysis_version`
- Respect operator overrides in `workload_config` — if `workload_type` is overridden, skip auto-classification for that workload's type (but still generate tags)
- Key all classification rows by `(cluster_id, workload_id, analysis_version)` for versioned access

## Inputs

### From NATS (Events)
- **Source**: `cluster.collected` event
- **Payload**: `{ clusterId, snapshotId, clusterHash, assemblyVersion }`
- **Action**: Fetch `assembled_snapshots.payload` for `(clusterId, snapshotId)`; iterate every workload in `kubernetes.deployments`, `kubernetes.statefulsets`, `kubernetes.daemonsets`; run tag generation and classification for each

### From Database (Cross-Domain Read)
- **Source**: `assembled_snapshots` — `payload.kubernetes.*` for this snapshot
- **Source**: `workload_config` — operator overrides for `workload_type` and `excluded` flag

## Outputs

### Database Writes
| Table | Write Pattern |
|---|---|
| `workload_tags` | **DELETE all rows for `(cluster_id, analysis_version)` then INSERT new set** — guarantees no stale tags |
| `workload_classifications` | Upsert on `(cluster_id, workload_id, analysis_version)` |

### No Events Published
This module does not publish NATS events directly. It feeds data consumed by `eligibility_engine` and `resource_analysis` via database reads.

## Events Produced
N/A — classification results are read directly from the database by subsequent Phase 2 modules.

## Events Consumed
| Event | Action |
|---|---|
| `cluster.collected` | Trigger full tag generation and classification for all workloads in the new assembled snapshot |

## Database Tables

### Tables Owned (Written)
| Table | Key Columns | Notes |
|---|---|---|
| `workload_tags` | `id UUID PK`, `cluster_id UUID FK`, `workload_id VARCHAR`, `workload_name VARCHAR`, `workload_namespace VARCHAR`, `tag VARCHAR`, `tag_source VARCHAR`, `confidence NUMERIC(3,2)`, `analysis_version VARCHAR`, `created_at TIMESTAMPTZ` | Deleted and reinserted every cycle. A workload may have multiple rows (one per tag). Indexed on `(cluster_id, workload_id, analysis_version)`. |
| `workload_classifications` | `id UUID PK`, `cluster_id UUID FK`, `workload_id VARCHAR`, `workload_name VARCHAR`, `workload_namespace VARCHAR`, `workload_kind VARCHAR`, `workload_type VARCHAR`, `type_source VARCHAR` (`auto`/`operator`), `tags TEXT[]`, `analysis_version VARCHAR`, `classified_at TIMESTAMPTZ` | Upsert on `(cluster_id, workload_id, analysis_version)`. `workload_type` from operator override if `workload_config.workload_type` is set; otherwise from auto-classification. |

### Tables Read (Cross-Domain, Read-Only)
| Table | Module | Purpose |
|---|---|---|
| `assembled_snapshots` | `snapshot_assembly` | Read workload metadata for classification input |
| `workload_config` | `workload_review` | Check for operator-set `workload_type` and `excluded` flag |

## Tag Catalog

### Tags — Detection Rules
| Tag | Detection Rule | tag_source |
|---|---|---|
| `stateless` | Kubernetes kind = `Deployment` AND no PVC binding for any pod in this deployment | `stateful_detection` |
| `stateful` | Kubernetes kind = `StatefulSet` OR any pod in the workload has a bound PVC | `stateful_detection` |
| `batch` | Kubernetes kind = `CronJob` OR `Job`, OR `batch_detection.is_batch_spike = true` (replicas ≥ 3× P50 over 7 days) | `batch_detection` |
| `database` | Any container image name contains: `postgres`, `mysql`, `mariadb`, `mongo`, `cassandra`, `cockroachdb`, `yugabyte`, `tidb`, `clickhouse`, `scylladb` | `database_detection` |
| `cache` | Any container image name contains: `redis`, `memcached`, `dragonfly`, `keydb` | `cache_detection` |
| `queue` | Any container image name contains: `rabbitmq`, `activemq`, `nats`, `pulsar`, `artemis` | `queue_detection` |
| `streaming` | Any container image name contains: `kafka`, `redpanda`, `pulsar`, `flink`, `spark` | `queue_detection` |
| `ai_ml` | Any container image contains: `pytorch`, `tensorflow`, `ray`, `triton`, `huggingface`, `vllm`, `ollama`, `jax` | `java_detection` (same sub-module, renamed scope) |
| `gpu` | Any container `resources.requests` or `resources.limits` contains `nvidia.com/gpu` or `amd.com/gpu` key with value > 0 | `java_detection` |
| `monitoring` | Any container image contains: `prometheus`, `grafana`, `loki`, `alertmanager`, `thanos`, `victoria-metrics`, `jaeger`, `tempo`, `otel` | `monitoring_detection` |
| `system` | Pod namespace is any of: `kube-system`, `cert-manager`, `ingress-nginx`, `kube-proxy`, `calico-system`, `cilium`, `metallb-system`, `external-secrets`, `vault` | `monitoring_detection` |
| `java` | Container image contains: `java`, `jdk`, `jre`, `openjdk`, `corretto`, `temurin`, `eclipse-temurin`, `graalvm`, `azul`, `zulu`; OR any container env var key is: `JAVA_OPTS`, `JVM_OPTS`, `JAVA_TOOL_OPTIONS`, `JAVA_HOME` | `java_detection` |
| `critical` | `workload_config.business_criticality = 'CRITICAL'` — **operator-set only, never auto-inferred** | `operator_override` |
| `unknown` | No other tags matched — fallback | `unknown_detection` |

### Workload Type — Priority Hierarchy
Types are resolved in this strict priority order. The first match wins:

| Priority | workload_type | Condition |
|---|---|---|
| 1 | `DAEMON` | Kubernetes kind = `DaemonSet` |
| 2 | `STATEFUL` | Has `stateful` tag (StatefulSet or PVC-bound) |
| 3 | `BATCH` | Has `batch` tag (CronJob/Job or spike pattern) |
| 4 | `WEB` | Kubernetes kind = `Deployment` AND HPA resource exists for this workload |
| 5 | `WORKER` | Kubernetes kind = `Deployment` AND no HPA |

If operator has set `workload_config.workload_type`, that value overrides all auto-classification. `type_source` is set to `operator`.

## Sub-Modules

| Sub-Module | Tags Produced | Logic |
|---|---|---|
| `tag_generation` | Orchestrator — calls all sub-modules | Iterates workloads; merges tag arrays; deduplicates |
| `java_detection` | `java`, `ai_ml`, `gpu` | Image substring matching + env var key scan |
| `batch_detection` | `batch` | Kind check + replica spike ratio from `assembled_snapshots.metrics` |
| `stateful_detection` | `stateful`, `stateless` | Kind check + PVC binding check from `kubernetes.pvcs` |
| `database_detection` | `database` | Image substring matching against DB image list |
| `cache_detection` | `cache` | Image substring matching against cache image list |
| `queue_detection` | `queue`, `streaming` | Image substring matching against broker image list |
| `monitoring_detection` | `monitoring`, `system` | Image + namespace matching |
| `unknown_detection` | `unknown` | Fallback if no other tag matched |

## APIs
N/A — this is a pure worker module triggered by NATS events and BullMQ jobs. It exposes no REST endpoints. Classification results are consumed via direct database reads by `eligibility_engine`.

## Dependencies

### Internal Modules
| Module | Usage |
|---|---|
| `common/logger` | Structured logging with `clusterId`, `snapshotId`, `workloadId`, `analysisVersion` |
| `database` | PostgreSQL pool; DELETE + bulk INSERT for `workload_tags`; upsert for `workload_classifications` |
| `events` | NATS subscriber for `cluster.collected` |

### External Services
None — this module reads from PostgreSQL and writes to PostgreSQL.

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `CLASSIFICATION_ANALYSIS_VERSION` | (from `package.json`) | Version string stamped on all classification rows |
| `CLASSIFICATION_CONFIDENCE_THRESHOLD` | `0.5` | Minimum confidence score for a tag to be persisted |
| `CLASSIFICATION_BATCH_SPIKE_RATIO` | `3.0` | Replica ratio (current / P50) above which `batch` tag is applied |
| `CLASSIFICATION_DB_IMAGE_LIST` | (compiled list) | Comma-separated list of DB image name substrings (overridable for custom images) |
| `CLASSIFICATION_CACHE_IMAGE_LIST` | (compiled list) | Comma-separated list of cache image name substrings |
| `CLASSIFICATION_JAVA_IMAGE_LIST` | (compiled list) | Comma-separated list of JVM image name substrings |
| `CLASSIFICATION_SYSTEM_NAMESPACES` | `kube-system,cert-manager,...` | Comma-separated namespaces treated as `system` workloads |

## Error Handling

| Scenario | Behavior |
|---|---|
| Assembled snapshot payload is missing or malformed | Log `CLASSIFICATION_SNAPSHOT_MISSING`; skip classification for this cycle; workload_classifications rows retain their previous version |
| DELETE of `workload_tags` succeeds but INSERT fails | Full transaction rollback — old tags are restored. Logged as `CLASSIFICATION_TAG_INSERT_FAILED`. BullMQ retries job. |
| Unknown Kubernetes kind in snapshot | Workload receives `unknown` tag and `WORKER` type (safest default). Logged at DEBUG level. |
| Operator override present in `workload_config` | `workload_type` from config is used; tags are still generated; `type_source = 'operator'` is stamped on the classification row |
| `workload_config.excluded = true` | Workload is skipped entirely — no tags or classification row written for this cycle |
| Image scan times out (very large image list) | Capped at 5ms per workload via synchronous string operations; no async I/O in tag generation — timeout is not a practical concern |

## Future Enhancements
- **ML-based classification**: Train a classifier on labelled BalanceKube workload data to supplement or replace rule-based image matching, particularly for bespoke internal image names
- **Custom tag rules per org**: Allow operators to define additional tag rules (e.g., "all images from `myregistry.io/ml/` get the `ai_ml` tag") as org-level configuration
- **HPA source awareness**: Detect KEDA ScaledObjects as an equivalent to native HPA for `WEB` type classification
- **Helm release metadata**: Use Helm release labels (`app.kubernetes.io/managed-by=Helm`, `helm.sh/chart`) to improve workload purpose inference
- **Operator labelling feedback loop**: When operators override a classification, log the delta to a training dataset for future ML model improvement
