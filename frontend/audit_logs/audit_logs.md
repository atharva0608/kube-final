# audit_logs

## Purpose
The audit logs module provides a paginated, filterable audit trail viewer for compliance reporting and incident investigation. Every action performed by any operator in the BalanceKube platform is recorded as an audit log entry. This module surfaces those entries in a human-readable UI and supports export for external compliance workflows.

## Responsibilities
- Display audit log entries in reverse-chronological order with pagination.
- Filter controls: by actor (user name or user ID), by action type (e.g., `recommendation.approved`, `override.created`, `cluster.registered`), by resource type (e.g., `cluster`, `workload`, `recommendation`), and by date range.
- Per-entry display: actor name, action label, resource type and resource ID, timestamp, source IP address.
- Expandable before/after JSON diff view per entry: shows the state of the resource before and after the action (collapsible, syntax-highlighted).
- Export all filtered results to CSV (calls the same filtered `GET /audit-logs` endpoint with `format=csv` parameter).
- Support for URL-based filter state (shareable filtered links for incident investigation).

## Inputs
- **Source:** `GET /audit-logs`
- **Query parameters:** `actor_id`, `action_type`, `resource_type`, `from_date`, `to_date`, `page`, `per_page`, `format` (json|csv)
- **Format (JSON):**
```json
{
  "total": "number",
  "page": "number",
  "per_page": "number",
  "entries": [
    {
      "audit_id": "string",
      "actor_id": "string",
      "actor_name": "string",
      "action": "string",
      "resource_type": "string",
      "resource_id": "string",
      "timestamp": "ISO8601 string",
      "ip_address": "string",
      "before": "object | null",
      "after": "object | null"
    }
  ]
}
```
- **Source:** URL query parameters (for shareable filter state)

## Outputs
- **Destination:** HTTP GET requests to `GET /audit-logs` (read-only)
- **Destination:** Browser file download trigger when CSV export is requested

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `audit_logs`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/audit-logs` | Fetch paginated, filtered audit log entries (supports `format=csv` for export) |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` components** — `DataTable` (paginated, with server-side pagination), `DateRangePicker`, `Select` (filter dropdowns), JSON diff viewer, `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for audit log response
- **React Router** — URL query parameter management for filter state

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |
| `VITE_AUDIT_LOG_PAGE_SIZE` | Default entries per page | `50` |

## Error Handling
- **Large date range:** If the selected date range produces more than 10,000 entries, the backend returns a 422 with a message to narrow the range; the UI shows this error inline on the date picker.
- **CSV export timeout:** For large exports, the backend may take several seconds; the UI shows a "Preparing download..." spinner and the button is disabled to prevent duplicate requests.
- **API error:** Error card with retry; filter state is preserved so the operator does not lose their filter configuration on retry.
- **Empty results:** Shows "No audit events found for the selected filters" with a prompt to broaden the date range or clear filters.

## Future Enhancements
- Real-time streaming of new audit entries (Server-Sent Events) for live incident monitoring.
- Saved filter presets (e.g., "All approvals this month", "My actions this week").
- Audit log alert: notify (via Slack/email) when a specific high-risk action type is performed (e.g., `override.created` on a CRITICAL workload).
