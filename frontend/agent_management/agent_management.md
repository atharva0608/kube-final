# agent_management

## Purpose
The agent management module gives operators a live health dashboard and administrative controls for the BalanceKube agent running inside each cluster. It is a dedicated feature area because the agent is the platform's data collection foundation—if the agent is unhealthy, no pipeline phase can proceed—and operators need immediate visibility into agent status, heartbeat health, and token lifecycle without navigating away from a focused panel.

## Responsibilities
- Display agent metadata: version, last heartbeat timestamp, connection status (`registered` / `active` / `degraded` / `unreachable`), collection cycle count, and any last reported error.
- Show a heartbeat health indicator:
  - **Green:** Last heartbeat within the last 30 seconds
  - **Yellow:** Last heartbeat 30–90 seconds ago
  - **Red:** Last heartbeat > 90 seconds ago (triggers `agent.heartbeat_missed` event on the backend)
- Token management panel:
  - Show certificate expiry countdown (days/hours remaining).
  - "Rotate Token Now" button — calls `POST /agents/:id/rotate-token`.
  - "Generate New Registration Token" button — for scenarios where the agent needs full re-registration — calls `POST /agents/register`.
- Upgrade notification: if the platform's current agent version is newer than the installed agent version, show an "Upgrade available" banner with the upgrade `helm upgrade` command pre-populated.
- Permission drift alert: if the agent reports missing RBAC permissions (via heartbeat payload), show a red alert listing the missing permissions and the exact `kubectl apply` command to fix the ClusterRole.

## Inputs
- **Source:** `GET /clusters/:id/agent`
- **Format:**
```json
{
  "agent_id": "string",
  "cluster_id": "string",
  "version": "string",
  "status": "registered | active | degraded | unreachable",
  "last_heartbeat_at": "ISO8601 timestamp",
  "collection_cycle_count": "number",
  "last_error": "string | null",
  "certificate_expires_at": "ISO8601 timestamp",
  "missing_permissions": ["string"],
  "platform_agent_version": "string"
}
```
- **Source:** `POST /agents/register` response — `{ registration_token, helm_install_command }`
- **Source:** `POST /agents/:id/rotate-token` response — `{ new_token, expires_at }`
- **Source:** `GET /agents/:id/upgrade` response — `{ upgrade_available: boolean, latest_version, helm_upgrade_command }`
- **Source:** Route parameter `cluster_id` from React Router

## Outputs
- **Destination:** `POST /agents/register` — generate new registration token
- **Destination:** `POST /agents/:id/rotate-token` — rotate existing agent token
- **Destination:** `GET /agents/:id/upgrade` — check upgrade availability
- **Format:** JSON

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `agents`, `agent_tokens`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id/agent` | Fetch agent status, heartbeat, token expiry, and permission state |
| `POST` | `/agents/register` | Generate new registration token (for re-registration) |
| `POST` | `/agents/:id/rotate-token` | Rotate agent JWT/certificate token |
| `GET` | `/agents/:id/upgrade` | Check if a newer agent version is available |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` hooks** — `usePolling` (30 s interval for heartbeat status refresh)
- **`frontend/shared` components** — `StatusBadge` (heartbeat health, agent status), `Modal` (token rotation confirmation, new token display), `Toast`, `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for agent status API response

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |
| `VITE_AGENT_HEARTBEAT_GREEN_THRESHOLD_S` | Seconds threshold for green heartbeat indicator | `30` |
| `VITE_AGENT_HEARTBEAT_YELLOW_THRESHOLD_S` | Seconds threshold for yellow heartbeat indicator | `90` |
| `VITE_POLLING_INTERVAL_MS` | Heartbeat status refresh interval | `30000` |

## Error Handling
- **Token rotation confirmation:** Before calling `POST /agents/:id/rotate-token`, a confirmation modal explains that the agent must be restarted with the new token; the operator must explicitly confirm.
- **New token display:** After rotation, the new token is shown once in a modal with a "Copy to clipboard" button. The modal warns: "This token will not be shown again."
- **`unreachable` status:** Shows a troubleshooting guide: verify agent pods are running (`kubectl get pods -n balancekube`), check network egress policy, verify token has not expired.
- **Missing RBAC permissions:** The permission drift alert shows the specific missing resource types and the `kubectl apply` command for the corrected ClusterRole manifest, with a one-click copy button.

## Future Enhancements
- Auto-upgrade trigger: allow the platform to remotely upgrade the agent version (requires agent-side upgrade support).
- Historical heartbeat chart: show heartbeat success/miss rate over the last 24 hours.
- Multi-agent support per cluster (for future DaemonSet-based architectures).
