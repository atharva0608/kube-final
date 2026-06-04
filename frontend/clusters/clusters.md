# clusters

## Purpose
The clusters module provides the cluster settings and metadata management view. It is the operator's primary interface for viewing the registered cluster configuration, understanding the current connection and onboarding status, and modifying cluster-level operational settings such as the Karpenter control mode.

## Responsibilities
- Display cluster metadata: cluster name, AWS region, Kubernetes version, cluster ARN, `cluster_hash`, `connection_status`, `onboarding_status`, and current `karpenter_control_mode`.
- Show cluster template details: group definitions, execution defaults (drain timeout, batch size, health check interval), and `never_touch_namespaces` list.
- Provide a settings panel to change `karpenter_control_mode`:
  - **observe → managed** transition requires a confirmation modal warning the operator that BalanceKube will begin actively managing Karpenter NodePool provisioning.
  - **managed → observe** transition requires a similar confirmation modal.
- Show cluster connection status badge (`connected` / `disconnected` / `degraded`) with a link to the agent management module if disconnected.
- Show onboarding status badge (`pending` / `active` / `error`) with context-appropriate next-step links.

## Inputs
- **Source:** `GET /clusters/:id`
- **Format:**
```json
{
  "cluster_id": "string",
  "name": "string",
  "region": "string",
  "kubernetes_version": "string",
  "arn": "string",
  "cluster_hash": "string",
  "connection_status": "connected | disconnected | degraded",
  "onboarding_status": "pending | active | error",
  "karpenter_control_mode": "observe | managed",
  "cluster_template": {
    "groups": [{ "group_id": "string", "name": "string", "namespaces": ["string"] }],
    "execution_defaults": {
      "drain_timeout_seconds": "number",
      "batch_size": "number",
      "health_check_interval_seconds": "number"
    },
    "never_touch_namespaces": ["string"]
  }
}
```
- **Source:** `PATCH /clusters/:id` request body — `{ karpenter_control_mode: 'observe' | 'managed' }` (and other patchable fields)
- **Source:** Route parameter `cluster_id` from React Router

## Outputs
- **Destination:** `PATCH /clusters/:id` — update cluster settings
- **Format:** JSON partial update body

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads/writes to: `clusters`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id` | Fetch cluster metadata and template configuration |
| `PATCH` | `/clusters/:id` | Update cluster settings (e.g., karpenter_control_mode) |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` components** — `StatusBadge` (connection status, onboarding status, karpenter mode), `Modal` (control mode change confirmation), `Toast`, `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for cluster API response and PATCH request body

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |

## Error Handling
- **Control mode change conflict:** If the cluster is currently executing a recommendation when the operator attempts to change `karpenter_control_mode`, the backend returns 409; the UI shows "Cannot change control mode during active execution."
- **PATCH error:** On failure, the settings form reverts to the last confirmed value and shows an error toast.
- **Cluster not found:** If the `cluster_id` route parameter is invalid, the backend returns 404; the UI redirects to the cluster list with a "Cluster not found" notification.

## Future Enhancements
- Cluster template editor: allow operators to modify group definitions and `never_touch_namespaces` directly from the UI.
- Multi-cluster view: list all registered clusters for the organisation with a status summary row.
- Cluster deletion workflow (danger zone): deregister a cluster with explicit confirmation and impact summary.
