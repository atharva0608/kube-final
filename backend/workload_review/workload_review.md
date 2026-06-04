# workload_review

## Purpose
The `workload_review` module manages the review state gate that sits between Phase 1 data collection and Phase 3 planning (drift-based recommendation locking). It ensures that human operators have an opportunity to confirm or override workload classifications, business criticality, and exclusion flags before BalanceKube locks in a migration plan. It exists as a separate module because the review state machine is a distinct, policy-driven concern that intentionally decouples automated analysis from automated action.

## Responsibilities
- On each `cluster.collected` event, determine which workloads require operator review:
  - **First collection cycle**: all workloads enter `pending_review` state — analysis still runs immediately (not blocked), but Phase 3 planning is gated until review is complete
  - **Subsequent cycles**: only workloads with no `workload_config` row (i.e., never reviewed before) enter `pending_review`; previously confirmed workloads are exempt, meaning no `review_items` row is created for them in subsequent cycles (their absence implies auto-confirmed status based on the existing `workload_config`).
- Create a `workload_reviews` record per review cycle and `review_items` records for each workload requiring review
- Expose APIs for operators to view pending review items, update workload configuration, and complete a review cycle
- Accept operator decisions on each workload:
  - Confirm auto-detected classification
  - Override `workload_type` (e.g., promote from WORKER to STATEFUL)
  - Set `workload_purpose` from a fixed controlled vocabulary
  - Set `business_criticality` — **never auto-inferred**, always explicitly set by the operator
  - Assign `application_group` for multi-workload grouping
  - Set `excluded = true` to permanently opt a workload out of Spot migration
- `PATCH /api/v1/workloads/:id/config` implicitly sets `review_status = confirmed` without requiring a separate confirm call
- Publish `review.completed` when an operator explicitly completes a review cycle
- Notify operators via the `notifications` module when workloads enter `pending_review`

## Inputs

### From NATS (Events)
- **Source**: `cluster.collected` event
- **Payload**: `{ clusterId, snapshotId, clusterHash, collectedAt, assemblyVersion }`
- **Action**: Query `assembled_snapshots` for the new snapshot; extract workload list; compare against `workload_config` table; create `workload_reviews` + `review_items` for unreviewed workloads

### From Frontend (REST)
- **Source**: `GET /api/v1/clusters/:id/reviews` — list review cycles
- **Source**: `POST /api/v1/clusters/:id/reviews/:review_id/complete` — mark review complete
- **Source**: `PATCH /api/v1/workloads/:id/config` — update workload configuration
- **Format**: Workload config update body:
```typescript
{
  workloadType?: 'DAEMON' | 'STATEFUL' | 'BATCH' | 'WEB' | 'WORKER';
  workloadPurpose?: 'WEB' | 'API' | 'WORKER' | 'BATCH' | 'DATABASE' | 'CACHE'
                  | 'QUEUE' | 'STREAMING' | 'MONITORING' | 'SECURITY'
                  | 'SYSTEM' | 'ML' | 'GPU';
  businessCriticality?: 'CRITICAL' | 'IMPORTANT' | 'STANDARD';
  applicationGroup?: string;
  excluded?: boolean;
  reviewNotes?: string;
}
```

## Outputs

### Database Writes
- `workload_reviews` — one per cycle, tracking overall review state for a cluster snapshot
- `review_items` — one per workload requiring review, tracking per-item status
- `workload_config` — upserted when operator calls `PATCH /api/v1/workloads/:id/config`

### API Responses (to frontend)
- `GET /api/v1/clusters/:id/reviews` → paginated review cycle list with item counts
- `GET /api/v1/clusters/:id/reviews/:review_id` → review detail with all items and their statuses
- `POST /api/v1/clusters/:id/reviews/:review_id/complete` → `{ completed: true, reviewId, completedAt }`
- `PATCH /api/v1/workloads/:id/config` → updated `workload_config` row

### NATS Events Published
- `review.completed` — published when operator marks a review cycle complete

### Notifications
- `review.pending` — in-app notification created for all `ADMIN` and `MEMBER` users in the org when new workloads enter pending review

## Events Produced
| Event | Description |
|---|---|
| `review.pending` | Fired (as an in-app notification, not a NATS event) when workloads enter `pending_review` on a new collection cycle |
| `review.completed` | NATS event fired when operator explicitly completes a review cycle. Payload: `{ reviewId, clusterId, completedAt, itemCount, confirmedCount, overriddenCount, excludedCount }` |

## Events Consumed
| Event | Action |
|---|---|
| `cluster.collected` | Extract workload list from the assembled snapshot. Query `workload_config` for each workload by `(cluster_id, workload_id)`. For each workload with no config row: create a `review_items` row with `status = pending`. If any items created, create/update `workload_reviews` row for this cycle. Create operator notification. Analysis pipeline is NOT blocked — only Phase 3 planning is gated. |

## Database Tables

### Tables Owned (Written)
| Table | Key Columns | Notes |
|---|---|---|
| `workload_reviews` | `id UUID PK`, `cluster_id UUID FK`, `snapshot_id UUID FK`, `status VARCHAR` (`pending`/`completed`/`skipped`), `item_count INT`, `pending_count INT`, `completed_at TIMESTAMPTZ`, `created_at TIMESTAMPTZ` | One per collection cycle per cluster. `skipped` when no new workloads require review. |
| `review_items` | `id UUID PK`, `review_id UUID FK`, `cluster_id UUID FK`, `workload_id VARCHAR`, `workload_name VARCHAR`, `workload_namespace VARCHAR`, `workload_kind VARCHAR`, `auto_detected_type VARCHAR`, `status VARCHAR` (`pending`/`confirmed`/`overridden`), `reviewed_at TIMESTAMPTZ`, `reviewed_by UUID FK→users` | One per workload per review cycle. Only created for workloads requiring review in this cycle. Absence of a row implies auto-confirmed based on prior config. Status `overridden` when operator changes any field from auto-detected value. |
| `workload_config` | `id UUID PK`, `cluster_id UUID FK`, `workload_id VARCHAR`, `workload_type VARCHAR`, `workload_purpose VARCHAR`, `business_criticality VARCHAR`, `application_group VARCHAR`, `excluded BOOL DEFAULT false`, `review_status VARCHAR` (`pending`/`confirmed`), `review_notes TEXT`, `updated_at TIMESTAMPTZ`, `updated_by UUID FK→users` | Upsert on `(cluster_id, workload_id)`. This is the operator-defined configuration that overrides auto-detection. Once a row exists for a workload, it is exempt from future `pending_review` creation. |
| `application_group_definitions` | `id UUID PK`, `cluster_id UUID FK`, `name VARCHAR`, `description TEXT`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ` | Defines logical groups for workloads. Assigned via `workload_config.application_group`. |

### workload_purpose controlled vocabulary
| Value | Description |
|---|---|
| `WEB` | HTTP server, frontend, reverse proxy |
| `API` | Backend API, gRPC server |
| `WORKER` | Background job processor, queue consumer |
| `BATCH` | Periodic batch job, ETL, report generation |
| `DATABASE` | Relational or NoSQL database engine |
| `CACHE` | In-memory cache (Redis, Memcached) |
| `QUEUE` | Message broker (RabbitMQ, ActiveMQ, NATS) |
| `STREAMING` | Event streaming (Kafka, Redpanda, Pulsar) |
| `MONITORING` | Observability stack (Prometheus, Grafana, Loki) |
| `SECURITY` | Security tooling (Vault, cert-manager, Falco) |
| `SYSTEM` | Platform infrastructure (CNI, ingress, DNS) |
| `ML` | Machine learning training or inference |
| `GPU` | GPU-accelerated workload |

### business_criticality note
> ⚠️ `business_criticality` is **NEVER** auto-inferred from labels, annotations, or workload names. It is exclusively set by the operator through the review API. The auto-classification engine does not set this field. Only `ADMIN` and `MEMBER` role users may set `business_criticality = CRITICAL`.

### Tables Read (Cross-Domain, Read-Only)
| Table | Module | Purpose |
|---|---|---|
| `assembled_snapshots` | `snapshot_assembly` | Read workload list from the latest assembled snapshot on `cluster.collected` |
| `users` | `users` | Resolve `reviewed_by` foreign key; validate reviewer has org membership |

## APIs
| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/clusters/:id/reviews` | JWT | List all review cycles for a cluster, paginated. Includes `status`, `itemCount`, `pendingCount`, `completedAt`. |
| `GET` | `/api/v1/clusters/:id/reviews/:review_id` | JWT | Get full review cycle detail including all `review_items` with current status. |
| `POST` | `/api/v1/clusters/:id/reviews/:review_id/complete` | JWT (ADMIN/MEMBER) | Mark review cycle as completed. Publishes `review.completed` event. Fails with `400` if any items are still in `pending` status (operator must action all items or explicitly confirm them). |
| `PATCH` | `/api/v1/workloads/:id/config` | JWT (ADMIN/MEMBER) | Upsert workload configuration. Accepts partial updates (only provided fields are changed). Implicitly sets `review_status = confirmed` on the associated `review_items` row. Returns the complete updated `workload_config` object. |
| `GET` | `/api/v1/clusters/:id/workloads/:workload_id/config` | JWT | Read the current workload config for a specific workload. Returns 404 if not yet reviewed. |
| `POST` | `/api/v1/clusters/:id/application-groups` | JWT (ADMIN/MEMBER) | Create a new application group definition. |
| `GET` | `/api/v1/clusters/:id/application-groups` | JWT | List application group definitions for the cluster. |
| `PUT` | `/api/v1/clusters/:id/application-groups/:group_id` | JWT (ADMIN/MEMBER) | Update an application group definition. |
| `DELETE` | `/api/v1/clusters/:id/application-groups/:group_id` | JWT (ADMIN/MEMBER) | Delete an application group definition (fails if in use by any `workload_config`). |

## Dependencies

### Internal Modules
| Module | Usage |
|---|---|
| `common/auth` | JWT middleware; role check for ADMIN/MEMBER on config write |
| `common/validation` | Zod validation of `workload_config` update body |
| `common/logger` | Structured logging with `clusterId`, `reviewId`, `workloadId` |
| `database` | PostgreSQL pool; upsert helpers |
| `events` | NATS subscriber for `cluster.collected`; publisher for `review.completed` |
| `notifications` | Create in-app notification for org members when review is pending |

### External Services
None — this module interacts only with PostgreSQL and NATS.

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `REVIEW_AUTO_COMPLETE_AFTER_HOURS` | `0` (disabled) | If > 0, automatically complete a pending review this many hours after creation (for orgs that want fully automated pipelines) |
| `REVIEW_NOTIFY_ROLES` | `ADMIN,MEMBER` | Comma-separated roles that receive pending review notifications |
| `REVIEW_ITEMS_PAGE_SIZE` | `50` | Default page size for review items list |
| `REVIEW_PHASE3_GATE_ENABLED` | `true` | If false, Phase 3 planning proceeds even when review is pending (escape hatch) |

## Error Handling

| Scenario | Behavior |
|---|---|
| `cluster.collected` handler fails to parse assembled snapshot | Log `REVIEW_SNAPSHOT_PARSE_ERROR`; skip review creation for this cycle; Phase 2 pipeline continues unaffected |
| `PATCH /workloads/:id/config` with invalid `workloadPurpose` value | `400 Bad Request` with enum validation error |
| `POST /reviews/:id/complete` when items still pending | `400 Bad Request` with `REVIEW_ITEMS_PENDING`; lists the workload IDs still requiring action |
| DB upsert of `workload_config` fails | `500`; no partial write; retry is safe (upsert is idempotent) |
| Notification delivery fails | Logged; not fatal; review state is still updated |
| Review cycle already completed | `409 Conflict` with `REVIEW_ALREADY_COMPLETED` |

## Future Enhancements
- **Bulk review actions**: Allow operators to confirm or exclude multiple workloads in a single API call (e.g., "confirm all monitoring workloads")
- **Review templates**: Allow orgs to define classification rules (e.g., "all workloads in namespace `monitoring` auto-confirm as MONITORING") that pre-populate workload config without manual review
- **Review expiry**: Auto-skip stale review cycles (older than N days) and mark them as `expired` to unblock planning
- **Slack / webhook notifications**: Push review pending notifications to Slack or custom webhooks in addition to in-app notifications
- **Review audit trail**: Record a full diff of every field change made during review for compliance and rollback purposes
