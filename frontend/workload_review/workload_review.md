# workload_review

## Purpose
The workload review module provides the operator validation workflow UI where operators inspect, confirm, or override the auto-detected classification and configuration of each workload before Phase 2 analysis proceeds. It is the human-in-the-loop gate between automated classification (Phase 2a) and eligibility/recommendation generation (Phase 2b onward).

## Responsibilities
- List all workloads in `pending_review` state, grouped by namespace, within the selected review session.
- Per-workload detail panel displays:
  - Auto-detected classification tags and tag sources (kind_detection, pvc_detection, image_detection, etc.)
  - Resource profile summary (CPU and memory usage state)
  - Proposed eligibility verdict with a list of `decision_reasons`
  - `is_java` flag (triggers conservative analysis note)
  - Replica count and whether an HPA is attached
- Operator action controls per workload:
  - Confirm classification (accept auto-detected values as-is)
  - Override `workload_type` via dropdown (DAEMON / STATEFUL / BATCH / WEB / WORKER)
  - Set `workload_purpose` (free-text description)
  - Set `business_criticality` (CRITICAL / IMPORTANT / STANDARD)
  - Assign `application_group` (free-text grouping label)
  - Toggle `excluded=true` to permanently exclude from spot placement
- Bulk actions:
  - Confirm all workloads in a namespace
  - Set business criticality for all workloads in a namespace at once
- Submit individual configuration changes via `PATCH /workloads/:id/config`
- Trigger review completion via `POST /clusters/:id/reviews/:review_id/complete` when all workloads are confirmed
- Show review progress bar (confirmed count / total count)

## Inputs
- **Source:** `GET /clusters/:id/reviews`
- **Format:** `{ review_id, status, created_at, total_items, confirmed_items, items: Array<{ workload_id, name, namespace, workload_type, tags, resource_profile, eligibility_verdict, decision_reasons, is_java, replicas, has_hpa, review_status }> }`
- **Source:** `PATCH /workloads/:id/config` response — `{ workload_id, review_status: 'confirmed', config: { workload_type, workload_purpose, business_criticality, application_group, excluded } }`
- **Source:** `POST /clusters/:id/reviews/:review_id/complete` response — `{ review_id, status: 'completed' }`
- **Source:** Route parameters `cluster_id`, `review_id` from React Router

## Outputs
- **Destination:** `PATCH /workloads/:id/config` — submits operator overrides and marks `review_status=confirmed`
- **Destination:** `POST /clusters/:id/reviews/:review_id/complete` — triggers Phase 2 continuation
- **Format:** JSON request bodies with override fields

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend writes to: `workload_reviews`, `review_items`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id/reviews` | Fetch the current review session and all workload items |
| `PATCH` | `/workloads/:id/config` | Submit operator override for a single workload |
| `POST` | `/clusters/:id/reviews/:review_id/complete` | Mark review as complete and trigger Phase 2 continuation |

## Dependencies
- **`frontend/shared/api`** — API client with optimistic update support for PATCH calls
- **`frontend/shared` components** — `DataTable`, `Modal` (bulk action confirmation), `Toast`, `StatusBadge`, `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for config override payloads and review API responses

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |

## Error Handling
- **Optimistic updates:** When the operator clicks "Confirm", the UI immediately updates the workload's `review_status` to `confirmed` in local state. If the `PATCH` call fails, the local state is reverted and an error toast is shown.
- **Bulk action failure:** If a bulk "Confirm all" operation returns a partial failure (some workloads succeed, some fail), the UI shows which workloads failed to confirm and provides a retry button for the failed items only.
- **Review already completed:** If `POST .../complete` is called but the review is already in `completed` state, the API returns 409; the UI shows an informational message and redirects to the next phase.
- **Unsaved changes guard:** If the operator navigates away with uncommitted changes (workload config edited but PATCH not yet sent), a confirmation modal warns them of potential data loss.

## Future Enhancements
- Keyboard navigation for rapid bulk review (arrow keys to move between workloads, Enter to confirm).
- Search/filter within the review list by workload name or namespace.
- Review history: ability to view past review sessions and their decisions.
- Suggested `application_group` values based on namespace patterns or existing labels.
