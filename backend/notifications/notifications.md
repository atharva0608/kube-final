# notifications

## Purpose
Delivers platform-generated alerts to operators via email, Slack, and custom webhooks when significant events occur across the BalanceKube lifecycle. Decouples event producers from delivery mechanics — no other module needs to know which channels are configured for a given organization; they simply write a notification intent and this module handles multi-channel fanout, retries, and failure tracking.

## Responsibilities
- Receive notification dispatch requests from the `workers/notifications` BullMQ job, which subscribes to relevant NATS events and enqueues delivery tasks.
- Fan out each notification to all configured channels for the target organization: email (SES or SMTP), Slack incoming webhook, and custom webhook URL.
- Persist every notification attempt in the `notifications` table with `status` tracking (`pending`, `sent`, `failed`, `dead_lettered`).
- Retry failed deliveries up to 5 times with exponential backoff (starting at 30s, doubling each attempt).
- Dead-letter notifications that fail all 5 retries into `dead_letter_jobs` for operator inspection.
- Expose read APIs for operators to list notifications and mark them as read.
- Support per-organization channel configuration: email recipients, Slack webhook URL, custom webhook URL (all stored per-org, custom webhook URLs stored encrypted).

## Notification Types
| Type | Trigger Event | Description |
|---|---|---|
| `review.pending` | Internal trigger post-`cluster.collected` | Workload review required before analysis can proceed. |
| `drift.detected` | `drift.detected` NATS event | Cluster state has drifted from the pending recommendation plan. |
| `execution.started` | `execution.started` NATS event | Phase 4 execution has begun on a cluster. |
| `execution.completed` | `execution.completed` NATS event | Phase 4 execution completed (success or failure). |
| `execution.rolled_back` | `execution.completed` with `status=rolled_back` | Execution was rolled back; includes failure reason. |
| `agent.heartbeat_missed` | `agent.heartbeat_missed` NATS event | An in-cluster agent has gone silent. |
| `recommendation.ready` | `cluster.analysed` NATS event | A new recommendation is available for operator approval. |

## Inputs
- **Source:** `workers/notifications` BullMQ job — dequeues dispatch requests produced by NATS event subscriptions.
- **Source:** NATS events (consumed via the worker): `drift.detected`, `execution.started`, `execution.completed`, `cluster.analysed`, `agent.heartbeat_missed`.
- **Source:** Internal trigger for `review.pending` from the snapshot assembly / workload review pipeline.
- **Source:** `PATCH /notifications/:id/read` — operator acknowledgement of a notification.
- **Format:** Notification payloads are structured JSON; per-org channel configuration is stored in a `org_notification_settings` sub-table (or as a JSONB column on `organizations`).

## Outputs
- **Destination:** `notifications` table — one row per notification attempt, updated with delivery status.
- **Destination:** AWS SES or SMTP server — email delivery.
- **Destination:** Slack incoming webhook URL — HTTP POST with Slack message payload.
- **Destination:** Custom webhook URL — HTTP POST with standardised JSON payload.
- **Destination:** `dead_letter_jobs` table — for notifications that exhaust all retries.
- **Format (custom webhook payload):**
  ```json
  {
    "event_type": "execution.completed",
    "org_id": "uuid",
    "cluster_id": "uuid",
    "timestamp": "2024-06-04T09:00:00Z",
    "payload": {
      "execution_id": "uuid",
      "status": "success",
      "savings_realised_monthly": 1240.50
    }
  }
  ```

## Events Produced
- **N/A** — The notifications module does not publish NATS events. It is a consumer and delivery layer only.

## Events Consumed
| Event | Action |
|---|---|
| `drift.detected` | Enqueue `drift.detected` notification for the cluster's organization. |
| `execution.started` | Enqueue `execution.started` notification. |
| `execution.completed` | Enqueue `execution.completed` notification; if `status=rolled_back`, also enqueue `execution.rolled_back`. |
| `cluster.analysed` | Enqueue `recommendation.ready` notification indicating a new recommendation awaits approval. |
| `agent.heartbeat_missed` | Enqueue `agent.heartbeat_missed` notification as a high-priority alert. |

*(Event consumption is handled by the `workers/notifications` BullMQ worker, which subscribes to NATS and enqueues delivery jobs to this module.)*

## Database Tables

**Tables this module owns (writes to):**
| Table | Description |
|---|---|
| `notifications` | One row per notification delivery attempt. Columns: `id` (UUID), `org_id` (FK), `type` (ENUM: see notification types above), `recipient` (email address, Slack channel, or webhook URL — masked in logs), `payload` (JSONB — full notification content), `sent_at` (nullable), `status` (ENUM: `pending`, `sent`, `failed`, `dead_lettered`), `attempt_count` (int), `last_error` (text). |

**Tables this module reads (read-only):**
| Table | Source Domain |
|---|---|
| `organizations` | Organizations — reads per-org channel configuration (Slack URL, email, webhook URL). |
| `clusters` | Onboarding — resolves cluster name and region for notification content. |

## APIs
| Method | Path | Description |
|---|---|---|
| `GET` | `/notifications` | List all notifications for the authenticated user's organization. Supports query params: `?type=`, `?status=`, `?limit=`, `?cursor=` (cursor-based pagination). Returns paginated list of notification records ordered by `sent_at` descending. |
| `PATCH` | `/notifications/:id/read` | Mark a notification as read (sets a `read_at` timestamp on the notification record). Used by the UI to dismiss notification banners. |

> **Note:** There is no public API for dispatching notifications. Delivery is triggered exclusively by internal events via the `workers/notifications` BullMQ job.

## Channel Configuration
Per-organization channel settings are stored in the `organizations` table (or a dedicated `org_notification_settings` table):

| Channel | Config Field | Storage |
|---|---|---|
| Email | `notification_email` (text array) | Plaintext |
| Slack | `slack_webhook_url` | Encrypted AES-256-GCM at rest |
| Custom webhook | `webhook_url` | Encrypted AES-256-GCM at rest |

If no channel is configured for an organization, the notification is persisted in `notifications` with `status=sent` (no-op) so the audit trail is complete even without delivery.

## Retry Strategy
| Attempt | Delay Before Retry |
|---|---|
| 1st retry | 30 seconds |
| 2nd retry | 60 seconds |
| 3rd retry | 120 seconds |
| 4th retry | 240 seconds |
| 5th retry | 480 seconds |
| Exhausted | Dead-letter to `dead_letter_jobs` |

Retry state is tracked via BullMQ's built-in retry mechanism with `attempt_count` mirrored to the `notifications` table for operator visibility.

## Dependencies
- **workers/notifications** — BullMQ worker that subscribes to NATS events and enqueues delivery jobs. Notifications module is the job processor; the worker is the enqueuer.
- **AWS SES or SMTP server** — for email delivery. Configured via environment variables.
- **Slack incoming webhooks** — per-org Slack webhook URL called via HTTP POST.
- **Custom webhook endpoints** — operator-supplied HTTP endpoints called with standardised payload.
- **organizations** module — reads per-org channel configuration.
- **shared/crypto** — AES-256-GCM decrypt for Slack and custom webhook URLs.
- **shared/db** — PostgreSQL client; `notifications` row updates are idempotent (upsert by `id`).
- **shared/logger** — structured logging with `org_id`, `notification_type`, `channel`; recipient addresses masked.

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `EMAIL_PROVIDER` | `ses` | Email delivery provider. Options: `ses`, `smtp`. |
| `AWS_SES_REGION` | `us-east-1` | AWS region for SES sending. |
| `SMTP_HOST` | — | SMTP server hostname (used when `EMAIL_PROVIDER=smtp`). |
| `SMTP_PORT` | `587` | SMTP server port. |
| `SMTP_USER` | — | SMTP authentication username. |
| `SMTP_PASS` | — | SMTP authentication password (loaded from secrets manager). |
| `NOTIFICATION_FROM_EMAIL` | `notifications@balancekube.io` | Sender email address for all outbound emails. |
| `NOTIFICATION_RETRY_MAX_ATTEMPTS` | `5` | Maximum delivery retry attempts before dead-lettering. |
| `NOTIFICATION_WEBHOOK_TIMEOUT_MS` | `5000` | HTTP timeout for custom webhook delivery calls. |
| `SLACK_WEBHOOK_SECRET_KEY_ID` | *(required)* | Secrets Manager key ID for AES-256-GCM decryption of stored Slack webhook URLs. |
| `WEBHOOK_URL_SECRET_KEY_ID` | *(required)* | Secrets Manager key ID for AES-256-GCM decryption of stored custom webhook URLs. |

## Error Handling
- **Email delivery failure (SES/SMTP):** BullMQ retries with exponential backoff (max 5 attempts). `notifications.status` set to `failed` after each attempt; `last_error` updated with provider error message. After 5 failures: `status=dead_lettered`, row written to `dead_letter_jobs`.
- **Slack webhook 4xx:** If Slack returns 404 (webhook deleted) or 403 (revoked), the notification is immediately dead-lettered without retrying. A `dead_letter_jobs` entry flags the misconfigured webhook URL for operator correction.
- **Custom webhook timeout:** Treated as a transient failure; retried per the exponential backoff schedule.
- **No channel configured:** Notification is persisted in `notifications` with `status=sent` and `recipient=none` immediately — no error, no retry. This ensures the audit trail is populated even for unconfigured orgs.
- **Payload serialisation failure:** If the notification payload cannot be serialised to JSON (unexpected type), the job is rejected (not retried) and written to `dead_letter_jobs` with `failure_reason='serialisation_error'`.
- **Dead-letter inspection:** Operators can query `dead_letter_jobs` filtered by `module=notifications` via the admin API to view and manually re-trigger failed notifications.

## Future Enhancements
- **In-app notification inbox:** Add a WebSocket-powered in-app notification center where operators receive real-time alerts without requiring email or Slack configuration.
- **Notification preferences per user:** Allow individual users within an org to subscribe/unsubscribe from specific notification types, rather than applying org-wide settings.
- **PagerDuty and OpsGenie integrations:** Add native integrations for on-call alerting platforms for high-severity events (`agent.heartbeat_missed`, `execution.rolled_back`).
- **Notification templates:** Allow organizations to customise notification message templates (subject, body) for their email and webhook channels.
- **Batching:** Batch multiple low-severity notifications within a 5-minute window into a single digest email, reducing noise for high-frequency drift detection alerts.
