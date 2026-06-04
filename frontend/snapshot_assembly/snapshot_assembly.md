# snapshot_assembly

## Purpose
The snapshot assembly module provides a debugging and audit UI for inspecting the assembled snapshots that the BalanceKube backend generates before running Phase 2 workload analysis. It exists as a dedicated feature area so that operators and support engineers can verify that the correct Kubernetes inventory, metrics, and pricing data was captured in a given snapshot—the primary tool for diagnosing unexpected Phase 2 outputs.

## Responsibilities
- List all assembled snapshots for a cluster, showing: snapshot ID, creation timestamp, `cluster_hash`, `assembly_version`, and `schema_version`.
- Show a 7-day retention indicator (snapshots older than 7 days are automatically deleted).
- Allow the operator to select a snapshot and inspect its full contents via an expandable detail panel.
- Detail panel sections: Kubernetes inventory summary (node count, pod count, workload counts), metrics summary (workloads with MATURE/SUFFICIENT/INSUFFICIENT data), pricing data summary (region, on-demand count, spot price count, pricing `fetched_at` timestamp), snapshot assembly timestamp and latency.
- Support JSON viewer for raw snapshot contents (with collapsible sections, search/highlight).

## Inputs
- **Source:** `GET /clusters/:id/snapshots`
- **Format:** `Array<{ snapshot_id, cluster_id, created_at, cluster_hash, assembly_version, schema_version, kubernetes_inventory_summary, metrics_summary, pricing_summary }>`
- **Source:** `GET /clusters/:id/snapshots/:snapshot_id`
- **Format:** Full snapshot detail object including kubernetes_inventory, metrics_data, pricing_data (as described in the backend snapshot assembly module)
- **Source:** Route parameters `cluster_id`, `snapshot_id` from React Router

## Outputs
- **Destination:** Rendered snapshot list and detail panels in the operator browser
- **Destination:** HTTP GET requests to backend API (read-only)

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `assembled_snapshots`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id/snapshots` | List all snapshots for the cluster (last 7 days) |
| `GET` | `/clusters/:id/snapshots/:snapshot_id` | Fetch full snapshot detail for inspection |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` components** — `DataTable` (snapshot list), `Spinner`, `ErrorBoundary`, JSON viewer (collapsible tree view for raw snapshot data)
- **`frontend/shared/validation`** — Zod schemas for snapshot list and detail responses

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |
| `VITE_SNAPSHOT_RETENTION_DAYS` | Days shown in UI retention indicator | `7` |

## Error Handling
- **Large snapshot payloads:** The detail view requests the snapshot from the backend, which transparently resolves S3-stored payloads (via `payload_ref`) before returning the response. The frontend shows a loading spinner during this resolution.
- **Expired snapshot:** If a snapshot ID is accessed after its 7-day retention has elapsed, the backend returns 404; the UI displays a "Snapshot no longer available" message.
- **API error on list:** Shows an error card with retry; the cluster navigation sidebar remains functional.

## Future Enhancements
- Snapshot diff viewer: side-by-side comparison of two snapshots to show what changed between collection cycles.
- Download snapshot as JSON file for offline analysis.
- Alert indicator on the snapshot list if any snapshot in the last 24 hours has an `assembly_version` mismatch with the current platform version.
