# audit_logs

## Purpose
Provides an immutable, append-only audit trail for every mutation operation across the BalanceKube platform. Records who performed an action, on which resource, at what time, and exactly what changed — including before and after snapshots of the mutated resource. Used for compliance, security investigations, debugging, and change management.

## Responsibilities
- Accept audit log writes from every module that performs a mutation (recommendation approval, execution trigger, override creation, org settings change, user management, etc.).
- Store a structured record per mutation: `actor_id`, `action`, `resource_type`, `resource_id`, `before` (JSONB), `after` (JSONB), `ip_address`, `timestamp`.
- Guarantee **append-only** semantics — rows are never updated or deleted. PostgreSQL row-level triggers enforce this at the database layer.
- Scope all audit records to an `org_id` so that operators can only query their own organization's audit trail.
- Expose a paginated, filterable read API for operators and admins.
- Write audit records **synchronously** within the same request context as the mutation — not via a background job — to ensure the audit trail is complete even if the background processing layer fails.

## Responsibilities by Integration Point
Every module that mutates state is responsible for calling the shared audit library (`shared/audit`) at write time. The following actions must always be audited:

| Module | Audited Actions |
|---|---|
| `recommendations` | `recommendation.approved` |
| `eligibility_engine` | `override.created`, `override.updated`, `override.deleted` |
| `execution` | `execution.started`, `execution.aborted` |
| `organizations` | `org.created`, `org.updated`, `karpenter_mode.changed` |
| `users` | `user.created`, `user.role_changed`, `api_key.created`, `api_key.revoked` |
| `agent_management` | `agent.registered`, `agent.unregistered`, `agent.cert_rotated` |
| `drift_detection` | `drift.recheck_triggered` |
| `clusters` (onboarding) | `cluster.registered`, `cluster.deleted` |

## Inputs
- **Source:** `shared/audit` library — called synchronously by all mutating modules. Accepts a structured `AuditEntry` object.
- **Source:** `GET /audit-logs` — read API call from authenticated operators.
- **Format:**
  ```typescript
  interface AuditEntry {
    org_id: string;          // UUID
    actor_id: string;        // UUID of the authenticated user
    action: string;          // e.g. 'recommendation.approved'
    resource_type: string;   // e.g. 'recommendation', 'operator_override'
    resource_id: string;     // UUID of the affected resource
    before: object | null;   // Full resource snapshot before mutation (null for creates)
    after: object | null;    // Full resource snapshot after mutation (null for deletes)
    ip_address: string;      // Extracted from X-Forwarded-For or remote IP
  }
  ```

## Outputs
- **Destination:** `audit_logs` table — one row per audited mutation. Never mutated post-insert.
- **Destination:** API responses — paginated list of `audit_logs` rows.
- **Format (API response row):**
  ```json
  {
    "id": "uuid",
    "org_id": "uuid",
    "actor_id": "uuid",
    "actor_email": "user@example.com",
    "action": "recommendation.approved",
    "resource_type": "recommendation",
    "resource_id": "uuid",
    "before": { "status": "pending_approval" },
    "after": { "status": "approved", "approved_by": "uuid" },
    "ip_address": "203.0.113.42",
    "created_at": "2024-06-04T09:15:00Z"
  }
  ```

## Events Produced
- **N/A** — The audit log module does not emit NATS events. It is a synchronous write target only.

## Events Consumed
- **N/A** — The audit log module does not subscribe to NATS events. All writes are synchronous, in-band with the originating mutation.

## Database Tables

**Tables this module owns (writes to):**
| Table | Description |
|---|---|
| `audit_logs` | Append-only mutation audit trail. Columns: `id` (UUID, PK), `org_id` (FK → `organizations`), `actor_id` (UUID — user who performed the action), `action` (text — dotted action string like `recommendation.approved`), `resource_type` (text), `resource_id` (UUID), `before` (JSONB — full resource snapshot before change; null for creates), `after` (JSONB — full resource snapshot after change; null for deletes), `ip_address` (inet), `created_at` (timestamptz). **No UPDATE or DELETE ever issued on this table.** |

**Immutability enforcement:**
A PostgreSQL trigger is applied to `audit_logs` to `RAISE EXCEPTION` on any `UPDATE` or `DELETE` DML statement, regardless of the calling user or role. This provides defence-in-depth beyond application-layer constraints.

**Indexes:**
- `(org_id, created_at DESC)` — primary query pattern for paginated listing.
- `(org_id, actor_id)` — filter by actor.
- `(org_id, resource_type, resource_id)` — filter by specific resource.
- `(org_id, action)` — filter by action type.

**Tables this module reads (read-only):**
| Table | Source Domain |
|---|---|
| `users` | Users — joined to resolve `actor_email` from `actor_id` in API responses. |

## APIs
| Method | Path | Description |
|---|---|---|
| `GET` | `/audit-logs` | Paginated, filterable audit log listing for the authenticated user's organization. Query parameters: `?actor_id=`, `?action=`, `?resource_type=`, `?resource_id=`, `?from=` (ISO 8601 datetime), `?to=` (ISO 8601 datetime), `?limit=` (default 50, max 200), `?cursor=` (opaque cursor for pagination). Returns `{ items: AuditLog[], next_cursor?: string, total_count: number }`. Requires `operator` or `admin` role. |

> **Note:** There is no write API. All writes are performed internally by the `shared/audit` library. There is no `PATCH`, `PUT`, or `DELETE` endpoint — mutating or deleting audit records is architecturally prohibited.

## Shared Audit Library (`shared/audit`)
All modules use the `shared/audit` library to write audit entries. The library:
1. Accepts an `AuditEntry` object.
2. Resolves `org_id` from the current request context (injected by the authentication middleware).
3. Extracts `ip_address` from the request headers (`X-Forwarded-For` → first IP; fallback to direct remote address).
4. Executes an `INSERT` into `audit_logs` within the **same database transaction** as the originating mutation. If the transaction rolls back, the audit entry is also rolled back — preventing phantom audit entries for failed operations.
5. Returns immediately (synchronous, no async fire-and-forget).

## Before/After Snapshot Policy
- **Creates:** `before = null`, `after = full serialised resource`.
- **Updates:** `before = full resource snapshot before update`, `after = full resource snapshot after update`.
- **Deletes:** `before = full resource snapshot before deletion`, `after = null`.
- **Sensitive fields:** Fields containing secrets (passwords, API key plaintexts, encrypted ARNs) are **always redacted** in `before`/`after` snapshots before JSON serialisation. The `shared/audit` library has an explicit allowlist of fields that are permitted to appear in `before`/`after`. All other fields are passed through; explicitly excluded fields are replaced with `"[REDACTED]"`.

## Dependencies
- **shared/auth** — extracts `actor_id` and `org_id` from the authenticated request context.
- **shared/db** — PostgreSQL client; audit writes are always within the calling module's transaction.
- **users** module — read-only join on `users.email` in the `GET /audit-logs` response to display `actor_email`.
- **shared/logger** — structured logging for audit write failures (critical severity; paged to on-call).

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `AUDIT_LOG_RETENTION_DAYS` | `365` | Number of days to retain audit log rows before archival. Rows are never deleted in-place; archival moves them to a cold storage table or S3. |
| `AUDIT_LOG_REDACTED_FIELDS` | `password_hash,key_hash,aws_role_arn_encrypted,slack_webhook_url,webhook_url` | Comma-separated list of field names always redacted from `before`/`after` JSONB snapshots. |
| `AUDIT_LOG_MAX_PAYLOAD_BYTES` | `65536` | Maximum size of `before` or `after` JSONB payload. Payloads exceeding this are truncated and flagged with `"_truncated": true`. |
| `AUDIT_LOG_PAGE_SIZE_DEFAULT` | `50` | Default page size for `GET /audit-logs`. |
| `AUDIT_LOG_PAGE_SIZE_MAX` | `200` | Maximum page size for `GET /audit-logs`. |

## Error Handling
- **Write failure within a transaction:** If the `INSERT INTO audit_logs` fails (e.g., database constraint violation, connection loss), the calling module's transaction is rolled back entirely. The mutation does not complete without an audit record. This is intentional — the audit trail is a hard requirement, not a best-effort side effect.
- **Write failure for critical actions:** For actions that are deemed critical (e.g., `karpenter_mode.changed`, `user.role_changed`), a write failure is treated as a `500 Internal Server Error` returned to the API caller. The originating request must be retried.
- **`before`/`after` serialisation error:** If the resource snapshot cannot be serialised to JSON (circular reference, unsupported type), the audit entry is written with `before = null` and/or `after = null` plus a `_serialisation_error: true` flag in the JSONB. The mutation is still committed.
- **Payload size exceeded:** Payloads larger than `AUDIT_LOG_MAX_PAYLOAD_BYTES` are truncated at the field level (deepest leaf nodes removed first) with `"_truncated": true` added. Structure is preserved; only overflow content is dropped.
- **Query performance:** The `GET /audit-logs` API uses cursor-based pagination to avoid expensive `OFFSET` scans on large audit log tables. The cursor encodes the `(created_at, id)` pair for deterministic, stable pagination.

## Compliance Notes
- The `audit_logs` table is the primary artefact for SOC 2 Type II audit evidence, demonstrating that all privileged actions are logged with actor identity, timestamps, and change details.
- The PostgreSQL immutability trigger provides a second layer of protection beyond the application layer, preventing accidental or malicious record deletion even by database administrators using the application's service account.
- `ip_address` is stored as a PostgreSQL `inet` type, supporting both IPv4 and IPv6 addresses. IP addresses are personal data under GDPR; the data retention policy (`AUDIT_LOG_RETENTION_DAYS`) must align with the organization's privacy policy.

## Future Enhancements
- **Audit log export:** Add a `GET /audit-logs/export` endpoint that streams a signed S3 CSV/JSONL export of the full audit log for compliance reporting and external SIEM ingestion.
- **SIEM integration:** Stream audit log entries in real time to external systems (Splunk, Datadog, AWS Security Hub) via the notifications worker.
- **Immutable cold storage archival:** Implement automatic archival of rows older than `AUDIT_LOG_RETENTION_DAYS` to S3 with object lock (WORM) for long-term compliance retention.
- **Audit log search:** Add full-text search across `before`/`after` JSONB payloads for incident investigation use cases (e.g., find all changes to a specific ARN value).
- **Actor enrichment:** Include `actor_name` (display name) and `actor_role` at-write-time in the audit record (currently resolved at read time by joining `users`), so the record remains accurate even after a user is deleted.
