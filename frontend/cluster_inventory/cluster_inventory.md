# cluster_inventory

## Purpose
The cluster inventory module provides an interactive browser for all Kubernetes resources discovered within a registered cluster. It gives operators full visibility into the live cluster topology—nodes, pods, workload controllers, PVCs, and PDBs—so they can validate what the BalanceKube agent collected before proceeding to workload analysis and recommendations.

## Responsibilities
- Render a tabbed inventory browser with tabs for: Cluster list, Nodes, Pods, Deployments, StatefulSets, and DaemonSets.
- **Nodes tab:** Display each node with instance type, availability zone, lifecycle label (Spot / On-Demand), aggregate CPU and memory usage, node status (`Ready` / `NotReady`), and Karpenter NodePool membership if applicable.
- **Pods tab:** Display all pods with filtering by namespace, owning controller (Deployment, StatefulSet, DaemonSet, Job), and pod phase/status. Group pods by their controller for readability.
- **Deployments/StatefulSets/DaemonSets tab:** Show each controller with replica counts (desired / ready / available), associated pod count, and any attached PVC and PDB information.
- Show PVC details (storage class, access mode, bound status) inline within the workload view.
- Show PDB details (minAvailable / maxUnavailable policy, current disruptions allowed) inline within the workload view.
- Support sorting and filtering within each tab using the shared `DataTable` component.

## Inputs
- **Source:** `GET /clusters/:id/nodes` — full list of nodes in the cluster
- **Format:** `Array<{ node_id, name, instance_type, availability_zone, lifecycle, cpu_capacity, mem_capacity, cpu_allocatable, mem_allocatable, conditions, nodepool_name? }>`
- **Source:** `GET /clusters/:id/pods` — full list of pods
- **Format:** `Array<{ pod_id, name, namespace, status, owner_kind, owner_name, node_name, cpu_request, mem_request }>`
- **Source:** `GET /clusters/:id/deployments` — deployments with replica state
- **Format:** `Array<{ deployment_id, name, namespace, replicas_desired, replicas_ready, replicas_available, labels, pvcs, pdbs }>`
- **Source:** `GET /clusters/:id/statefulsets`, `GET /clusters/:id/daemonsets` — analogous to deployments
- **Source:** Route parameter `cluster_id` (from React Router)

## Outputs
- **Destination:** Rendered tabbed data tables in the operator browser
- **Destination:** HTTP GET requests to the backend API (read-only; this module performs no mutations)

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `nodes`, `pods`, `deployments`, `statefulsets`, `daemonsets`, `pvcs`, `pdbs`, `namespaces`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id/nodes` | Fetch all nodes for the cluster |
| `GET` | `/clusters/:id/pods` | Fetch all pods, filterable by namespace/status |
| `GET` | `/clusters/:id/deployments` | Fetch all Deployments with replica and PVC/PDB info |
| `GET` | `/clusters/:id/statefulsets` | Fetch all StatefulSets |
| `GET` | `/clusters/:id/daemonsets` | Fetch all DaemonSets |

## Dependencies
- **`frontend/shared/api`** — API client for HTTP calls
- **`frontend/shared` components** — `DataTable` (pagination, sorting, filtering), `StatusBadge` (node lifecycle, pod status), `Spinner`, `ErrorBoundary`
- **`frontend/shared` hooks** — `useCluster` for cluster context
- **`frontend/shared/validation`** — Zod schemas for API response parsing

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |

## Error Handling
- **Empty state:** If a tab returns an empty list (e.g., no DaemonSets in a cluster), the tab renders an informational empty-state illustration rather than a blank table.
- **API error:** If a tab's data fetch fails, that tab shows an error card with a retry button. Other tabs are unaffected.
- **Large clusters:** The `DataTable` component uses server-side pagination (passing `page` and `per_page` query parameters) when the cluster has more than 200 nodes or 500 pods to avoid browser memory pressure.
- **Stale data indicator:** A "Last refreshed" timestamp is shown at the top of each tab. A manual refresh button triggers a refetch.

## Future Enhancements
- Real-time updates via WebSocket push from the agent heartbeat cycle (replace manual refresh).
- Node topology map (visual AZ layout showing which nodes are in which AZ).
- Karpenter NodePool drill-down (click a NodePool name to see all nodes in that pool).
- Cross-tab correlation (click a Deployment to jump to its pods tab pre-filtered by that controller).
