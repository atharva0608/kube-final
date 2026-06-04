# backend

## Purpose
The `backend` module is the central server-side application for the BalanceKube platform. It serves as the authoritative source of truth for all business logic, data persistence, and event coordination — translating raw cluster signals from agents and external AWS data sources into actionable cost-optimization recommendations and execution plans.

## Responsibilities
- Expose a versioned REST API (under `/api/v1`) consumed by the frontend dashboard, the Go agent, and any external integrations
- Enforce authentication (JWT RS256) and authorization (org-scoped, role-based) on every request
- Own all PostgreSQL write operations — no other service may write to the primary database directly
- Coordinate the full BalanceKube pipeline: Onboarding → Data Collection → Workload Intelligence → Drift Detection → Execution
- Produce and consume NATS events (with Redis Streams as fallback) to decouple processing stages
- Cache hot data (spot prices, STS credentials, risk scores) in Redis with explicit TTL policies
- Enforce multi-tenancy via `org_id` predicate on every database query, backed by PostgreSQL Row-Level Security (RLS)
- Schedule background BullMQ workers for polling tasks (pricing, spot risk, metrics pruning)
- Serve pre-signed S3 URLs for large artifacts (CloudFormation templates, execution bundles)
- Maintain audit trails and dead-letter job records for all user-initiated and system-initiated actions

## Inputs
- **Agent REST pushes**: inventory snapshots, metric batches, heartbeats, token rotation requests — authenticated via `cluster_token` (short-lived bearer token)
- **Frontend REST calls**: user actions (onboarding, review, approval, execution) — authenticated via JWT RS256
- **NATS events**: inter-module events consumed by subscriber workers (e.g., `cluster.collected`, `drift.detected`, `recommendation.approved`)
- **External AWS APIs**: AWS Pricing API, Spot Advisor JSON, STS, EKS — called by backend workers
- **Environment configuration**: `.env` / Kubernetes `ConfigMap` / `Secret` at startup

| Source | Format |
|---|---|
| Agent inventory POST | JSON (InventoryPayload TypeScript type) |
| Agent metrics POST | JSON (MetricsPayload TypeScript type) |
| Frontend API calls | JSON over HTTP/1.1, JWT in `Authorization: Bearer` header |
| NATS messages | JSON-encoded event envelope `{ event, payload, meta }` |
| AWS Pricing JSON | Bulk JSON from pricing.us-east-1.amazonaws.com |
| AWS Spot Advisor | JSONP from spot-price.s3.amazonaws.com/spot.js |

## Outputs
- **HTTP responses**: JSON bodies conforming to versioned TypeScript response types
- **NATS events produced**: `org.created`, `cluster.registered`, `cluster.collected`, `review.pending`, `review.completed`, `cluster.analysed`, `drift.detected`, `drift.patchable`, `drift.invalidated`, `recommendation.approved`, `execution.started`, `execution.completed`, `execution.rolled_back`, `agent.heartbeat_missed`, `agent.token_rotated`
- **PostgreSQL writes**: all tables across all domains (see Database Tables)
- **Redis writes**: cached prices, STS credentials, risk scores, BullMQ job queues
- **S3 objects**: CloudFormation template uploads, rollback snapshot bundles

## Events Produced
| Event | Description |
|---|---|
| `org.created` | Fired after a new organization row is committed |
| `cluster.registered` | Fired after a cluster is registered and its token issued |
| `cluster.collected` | Fired after snapshot_assembly completes an assembled snapshot |
| `review.pending` | Fired when workloads enter pending review state |
| `review.completed` | Fired when an operator marks a review cycle complete |
| `cluster.analysed` | Fired after workload_classification + resource_analysis + eligibility + recommendations complete |
| `drift.detected` | Fired when drift_detection identifies a topology change |
| `drift.patchable` | Fired when drift is within patchable bounds and does not invalidate current plan |
| `drift.invalidated` | Fired when drift fully invalidates the current recommendation plan |
| `recommendation.approved` | Fired when an operator approves a recommendation for execution |
| `execution.started` | Fired when the execution engine acquires a lock and begins a migration |
| `execution.completed` | Fired when execution succeeds |
| `execution.rolled_back` | Fired when execution fails and rollback completes |
| `agent.heartbeat_missed` | Fired when an agent has not reported within the expected interval |
| `agent.token_rotated` | Fired after a cluster token has been rotated |

## Events Consumed
| Event | Handler Module | Action |
|---|---|---|
| `cluster.registered` | `cluster_inventory` | Initialize inventory tracking records for the new cluster |
| `cluster.collected` | `workload_review` | Trigger review state gate check |
| `cluster.collected` | `workload_classification` | Begin Phase 2 tag generation and classification |
| `review.completed` | `eligibility_engine` | Proceed with eligibility verdicts after operator sign-off |
| `cluster.analysed` | `recommendations` | Generate or refresh recommendation store |
| `drift.detected` | `drift_detection` | Trigger plan-delta computation and reanalysis |
| `recommendation.approved` | `execution` | Begin execution lock and migration sequence |
| `execution.completed` | `audit_logs` | Write immutable audit record |
| `execution.rolled_back` | `rollback` | Record rollback snapshot and notify operators |

## Database Tables

### Tables Owned (Written) by Backend

**Onboarding Domain**
| Table | Description |
|---|---|
| `organizations` | Tenant root — org name, plan, status |
| `users` | User accounts with hashed passwords |
| `memberships` | Org-user join table with role |
| `clusters` | Registered Kubernetes clusters per org |
| `cloudformation_stacks` | CF stack name, external_id, arn, status per org |
| `cluster_tokens` | Short-lived bearer tokens issued to agents |

**Cluster Inventory Domain**
| Table | Description |
|---|---|
| `nodes` | Node resource records keyed to snapshot |
| `pods` | Pod records with controller reference |
| `deployments` | Deployment specs |
| `statefulsets` | StatefulSet specs |
| `daemonsets` | DaemonSet specs |
| `pvcs` | PersistentVolumeClaims with zone metadata |
| `pdbs` | PodDisruptionBudget constraints |
| `namespaces` | Namespace records with labels |

**Metrics Domain**
| Table | Description |
|---|---|
| `cpu_metrics` | Per-pod/node CPU in millicores |
| `memory_metrics` | Per-pod/node memory in MiB |
| `network_metrics` | Per-node Rx/Tx in Kbps |
| `filesystem_metrics` | Per-node/PVC filesystem usage in GiB |

**Pricing Domain**
| Table | Description |
|---|---|
| `on_demand_prices` | On-demand $/hr per instance type per region |
| `spot_prices` | Spot $/hr per instance type per region per AZ |
| `instance_catalog` | vCPU, memory GiB, network performance per instance type |

**Spot Risk Domain**
| Table | Description |
|---|---|
| `interruption_rates` | Raw frequency band from Spot Advisor |
| `risk_scores` | Normalized 0–10 score per instance type per region |
| `spot_risk_history` | 90-day rolling history of risk scores |

**Snapshot Domain**
| Table | Description |
|---|---|
| `assembled_snapshots` | Immutable JSONB snapshot blobs, 7-day retention |

**Workload Review Domain**
| Table | Description |
|---|---|
| `workload_reviews` | Review cycle records per cluster |
| `review_items` | Per-workload review items with status |
| `workload_config` | Operator-confirmed configuration overrides |

**Classification Domain**
| Table | Description |
|---|---|
| `workload_tags` | Per-cycle semantic tags (deleted+reinserted) |
| `workload_classifications` | Final workload type per analysis version |

**Resource Analysis Domain**
| Table | Description |
|---|---|
| `workload_analysis` | CPU/memory/network/storage JSONB analysis per workload |

**Eligibility Domain**
| Table | Description |
|---|---|
| `eligibility_verdicts` | ELIGIBLE / INELIGIBLE / NEEDS_REVIEW per workload |
| `operator_overrides` | Manual eligibility overrides with reason |
| `decision_reasons` | Structured reasons for verdicts |

**Recommendations Domain**
| Table | Description |
|---|---|
| `recommendation_store` | Per-workload spot recommendations |
| `savings_estimates` | Projected monthly savings per cluster |

**Drift Detection Domain**
| Table | Description |
|---|---|
| `drift_events` | Records of topology changes detected |
| `plan_deltas` | Delta between current plan and new snapshot |

**Execution Domain**
| Table | Description |
|---|---|
| `execution_history` | Execution run records with status, timestamps |
| `execution_locks` | Distributed lock records per cluster |

**Rollback Domain**
| Table | Description |
|---|---|
| `rollback_snapshots` | Pre-migration rollback state bundles |

**Platform Domain**
| Table | Description |
|---|---|
| `audit_logs` | Immutable append-only audit records |
| `event_store` | NATS event log for replay/debugging |
| `dead_letter_jobs` | BullMQ jobs that exhausted retries |
| `notifications` | In-app notifications per org |
| `agents` | Agent registration records |
| `agent_tokens` | Active agent bearer tokens with expiry |

## APIs

The backend exposes all APIs under `/api/v1`. Authentication is required on all routes except `/api/v1/health` and `/api/v1/auth/login`.

### Authentication
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Issue JWT for user credentials |
| `POST` | `/api/v1/auth/refresh` | Refresh access token using refresh token |
| `POST` | `/api/v1/auth/logout` | Invalidate refresh token |

### Onboarding
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/orgs` | Create organization + admin user |
| `GET` | `/api/v1/orgs/:id` | Get organization details |
| `POST` | `/api/v1/orgs/:id/cloudformation` | Generate and upload CF template, return pre-signed S3 URL |
| `POST` | `/api/v1/orgs/:id/validate-role` | Validate IAM role via sts:AssumeRole |
| `GET` | `/api/v1/orgs/:id/clusters/discover` | Discover EKS clusters from validated AWS account |
| `POST` | `/api/v1/clusters` | Register a cluster |
| `POST` | `/api/v1/clusters/:id/select-cluster` | Confirm cluster selection and issue agent install instructions |
| `GET` | `/api/v1/clusters/:id/status` | Get cluster onboarding + operational status |

### Cluster Inventory
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/agents/:id/inventory` | Agent pushes full inventory snapshot |
| `GET` | `/api/v1/clusters/:id/nodes` | List nodes for a cluster |
| `GET` | `/api/v1/clusters/:id/pods` | List pods for a cluster |
| `GET` | `/api/v1/clusters/:id/deployments` | List deployments |
| `GET` | `/api/v1/clusters/:id/statefulsets` | List statefulsets |
| `GET` | `/api/v1/clusters/:id/daemonsets` | List daemonsets |
| `GET` | `/api/v1/clusters/:id/pvcs` | List PVCs |
| `GET` | `/api/v1/clusters/:id/pdbs` | List PDBs |

### Metrics
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/agents/:id/metrics` | Agent pushes metric batch |
| `GET` | `/api/v1/clusters/:id/metrics/:workload_id` | Get metric history for a workload |

### Workload Review
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/clusters/:id/reviews` | List review cycles for a cluster |
| `POST` | `/api/v1/clusters/:id/reviews/:review_id/complete` | Mark review cycle complete |
| `PATCH` | `/api/v1/workloads/:id/config` | Update workload config (implicitly confirms review) |

### Recommendations & Execution
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/clusters/:id/recommendations` | Get current recommendation store |
| `GET` | `/api/v1/clusters/:id/savings` | Get savings estimates |
| `POST` | `/api/v1/recommendations/:id/approve` | Approve recommendation for execution |
| `GET` | `/api/v1/clusters/:id/executions` | List execution history |
| `POST` | `/api/v1/executions/:id/rollback` | Manually trigger rollback |

### Platform
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Health check (unauthenticated) |
| `GET` | `/api/v1/audit-logs` | Query audit logs for the org |
| `GET` | `/api/v1/notifications` | List notifications for the current user |
| `PATCH` | `/api/v1/notifications/:id/read` | Mark notification read |

## Dependencies

### Internal Submodules
| Module | Role |
|---|---|
| `onboarding` | Customer registration and AWS IAM setup |
| `cluster_inventory` | Kubernetes resource storage and serving |
| `metrics_collection` | Time-series metric ingestion |
| `pricing_collection` | AWS pricing data workers |
| `spot_risk_collection` | Spot Advisor data ingestion |
| `snapshot_assembly` | Multi-source snapshot JOIN and immutable storage |
| `workload_review` | Review state gate management |
| `workload_classification` | Tag generation and workload type classification |
| `resource_analysis` | Per-workload metric profiling |
| `eligibility_engine` | Spot eligibility verdict computation |
| `recommendations` | Recommendation store and savings estimation |
| `drift_detection` | Topology change detection and plan delta |
| `execution` | Migration orchestration and health checks |
| `rollback` | Pre-migration state capture and rollback |
| `agent_management` | Agent registration, heartbeat, token rotation |
| `users` | User CRUD and password management |
| `organizations` | Organization CRUD and plan management |
| `notifications` | In-app notification delivery |
| `audit_logs` | Immutable audit record writes |
| `events` | NATS publisher/subscriber helpers |
| `database` | PostgreSQL connection pool, migration runner, query builder |
| `common` | Shared utilities: logging, errors, validation, auth middleware |

### External Services
| Service | Purpose |
|---|---|
| PostgreSQL | Primary relational data store |
| Redis | BullMQ job queues, response caching, STS credential cache |
| NATS | Event bus for inter-module communication |
| AWS STS | Role assumption for cross-account access |
| AWS EKS | Cluster discovery during onboarding |
| AWS EC2 | Spot price history, instance type descriptions |
| AWS S3 | Pre-signed URL delivery of CF templates and bundles |
| AWS Pricing API | Bulk on-demand price data |
| AWS Spot Advisor | Historical interruption rate data |

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `PORT` | `3000` | HTTP server listen port |
| `NODE_ENV` | `development` | `development` / `production` / `test` |
| `DATABASE_URL` | — | PostgreSQL connection string (required) |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `NATS_URL` | `nats://localhost:4222` | NATS server URL |
| `JWT_PRIVATE_KEY_PATH` | — | Path to RS256 private key PEM (required) |
| `JWT_PUBLIC_KEY_PATH` | — | Path to RS256 public key PEM (required) |
| `JWT_ACCESS_TTL` | `900` | Access token TTL in seconds (15 min) |
| `JWT_REFRESH_TTL` | `604800` | Refresh token TTL in seconds (7 days) |
| `AWS_REGION` | `us-east-1` | Default AWS region for platform-side calls |
| `S3_CF_BUCKET` | — | S3 bucket name for CloudFormation template uploads |
| `PRICING_POLL_INTERVAL_MS` | `86400000` | On-demand price poll interval (24 hr) |
| `SPOT_PRICE_POLL_INTERVAL_MS` | `900000` | Spot price poll interval (15 min) |
| `METRICS_RETENTION_DAYS` | `90` | Days before metric rows are pruned |
| `SNAPSHOT_RETENTION_DAYS` | `7` | Days before assembled_snapshots are pruned |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warn` / `error` |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `RLS_ENABLED` | `true` | Enable PostgreSQL row-level security enforcement |
| `NATS_FALLBACK_REDIS` | `false` | Use Redis Streams if NATS is unavailable |

## Error Handling
- **Validation errors**: All incoming request bodies are validated with Zod schemas. Validation failures return `400 Bad Request` with a structured error array; they are never retried.
- **Authentication errors**: Invalid or expired JWTs return `401 Unauthorized`. Missing org membership returns `403 Forbidden`.
- **Database errors**: Transient connection errors are retried up to 3 times with exponential backoff (base 100ms). Deadlocks are retried up to 5 times. Non-transient errors (constraint violations, type errors) propagate as `500 Internal Server Error` with a sanitized message.
- **NATS publish failures**: Events are written to the `event_store` table first (outbox pattern), then published. A background worker replays unpublished events on a 30-second interval.
- **BullMQ worker failures**: Jobs are retried with exponential backoff (max 5 attempts). Exhausted jobs are moved to `dead_letter_jobs` and an in-app notification is created for the org.
- **AWS API failures**: STS and EKS calls are retried 3 times. On persistent failure, the onboarding step returns a structured error code (e.g., `AWS_ROLE_ASSUMPTION_FAILED`) that the frontend displays inline.
- **Unhandled exceptions**: Caught by Express/Fastify error handler middleware, logged with full stack trace, and returned as `500` with a request correlation ID.

## Future Enhancements
- **GraphQL API layer**: Add a GraphQL gateway for flexible frontend queries, reducing over-fetching on the dashboard
- **WebSocket / SSE streaming**: Push real-time execution progress and heartbeat status to the frontend without polling
- **Multi-region deployment**: Shard `org_id` routing to regional backends for EU/APAC data residency compliance
- **OpenAPI spec generation**: Auto-generate OpenAPI 3.1 spec from route definitions and Zod schemas for SDK generation
- **Rate limiting**: Per-org and per-agent rate limiting on agent push endpoints to protect against runaway agents
- **Distributed tracing**: Integrate OpenTelemetry spans across NATS events and database calls for end-to-end pipeline tracing
- **Plugin architecture**: Allow custom eligibility rules and classification overrides to be registered as plugins per org
