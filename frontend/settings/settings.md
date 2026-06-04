# settings

## Purpose
The settings module provides organisation-level and user-level configuration management. It is the administrative hub for user profile management, API key lifecycle, notification channel configuration, and organisation-scoped settings. It is a separate feature area because it is accessed infrequently compared to operational dashboards and groups all administrative operations in one place.

## Responsibilities
- **Profile tab:** Display and edit the current user's name, email address, and password (password change requires current password confirmation).
- **API Keys tab:** Create new API keys with a name and optional expiry date; list all active keys with name, created date, and last-used date; delete (revoke) existing keys. New key value is shown once on creation and cannot be retrieved again.
- **Notifications tab:** Configure notification delivery channels per notification event type:
  - Channels: Email, Slack (webhook URL), custom Webhook (HTTP POST)
  - Event types: `execution.completed`, `execution.rolled_back`, `agent.heartbeat_missed`, `drift.invalidated`, `recommendation.generated`
  - Per-channel test button: sends a test notification via `POST /orgs/:id/notifications/test`
- **Organisation tab:** Display org name and AWS Account ID; allow editing org name; show current AWS region(s). Danger zone: delete organisation (requires typing the org name to confirm; calls `DELETE /orgs/:id`).

## Inputs
- **Source:** `GET /users/me` — current user profile
- **Format:** `{ user_id, name, email, created_at, org_id, role }`
- **Source:** `GET /api-keys` — list of API keys for the current user
- **Format:** `Array<{ key_id, name, created_at, last_used_at, expires_at | null }>`
- **Source:** `GET /orgs/:id` — organisation details and notification configuration
- **Format:** `{ org_id, name, aws_account_id, region, notification_config: { channels: [...] } }`
- **Source:** User form inputs for all PATCH/POST operations

## Outputs
- **Destination:** `PATCH /users/me` — update profile (name, email, password)
- **Destination:** `POST /api-keys` — create new API key (returns `{ key_id, key_value, name, expires_at }`)
- **Destination:** `DELETE /api-keys/:id` — revoke API key
- **Destination:** `GET /orgs/:id` — fetch org details
- **Destination:** `PATCH /orgs/:id` — update org settings (name, notification config)
- **Format:** JSON

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads/writes to: `users`, `memberships`, `organizations`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/users/me` | Fetch current user profile |
| `PATCH` | `/users/me` | Update user name, email, or password |
| `POST` | `/api-keys` | Create new API key |
| `GET` | `/api-keys` | List all API keys for the current user |
| `DELETE` | `/api-keys/:id` | Revoke an API key |
| `GET` | `/orgs/:id` | Fetch organisation settings and notification config |
| `PATCH` | `/orgs/:id` | Update organisation settings and notification config |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` components** — `Modal` (API key creation + one-time display, org delete confirmation), `Toast`, `Spinner`, `ErrorBoundary`, `DataTable` (API key list)
- **`frontend/shared/validation`** — Zod schemas for profile form validation (email format, password strength), API key creation request, and org PATCH request body

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |

## Error Handling
- **API key one-time display:** After `POST /api-keys` returns the `key_value`, it is shown in a modal with a "Copy to clipboard" button and a warning: "This key will not be shown again. Store it securely now." The modal cannot be dismissed until the operator explicitly clicks "I have saved this key."
- **Password change validation:** Client-side Zod validation checks that the new password meets minimum strength requirements before calling `PATCH /users/me`.
- **Org delete guard:** The danger zone org delete flow requires the operator to type the exact organisation name in a confirmation input before the delete button becomes enabled.
- **Notification test failure:** If the test notification `POST` fails (e.g., invalid Slack webhook URL), an inline error is shown next to the test button with the specific HTTP error from the downstream channel.
- **Email change requires re-verification:** If `PATCH /users/me` includes an email change, the UI shows a banner: "A verification email has been sent to the new address. The change will take effect after verification."

## Future Enhancements
- SAML/SSO configuration tab for enterprise customers.
- Team member management: invite users, manage roles (Admin / Member / Read-Only).
- Activity summary on the profile page (last login, last action, API key last used timestamps).
- Webhook delivery log: show last N webhook delivery attempts with status codes for the notification webhook channel.
