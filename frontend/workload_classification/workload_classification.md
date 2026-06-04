# workload_classification

## Purpose
The workload classification module provides a read-only viewer for the auto-detected tags and classification assigned to each workload by the Phase 2 classification engine. It gives operators full transparency into *why* each workload was classified the way it was—showing every tag, its source, and its confidence score—so they can identify misclassifications before the review step and understand what evidence the system used.

## Responsibilities
- List all workloads for a cluster with their final `workload_type` classification (DAEMON / STATEFUL / BATCH / WEB / WORKER).
- Indicate whether the `workload_type` came from an operator override (in a previous review) or from auto-detection.
- Per-workload tag list: show every tag applied, with:
  - `tag_name` (e.g., `has_pvc`, `is_stateful`, `is_batch_job`, `is_java`, `is_daemonset`)
  - `tag_source` (e.g., `kind_detection`, `pvc_detection`, `image_detection`, `resource_detection`, `namespace_detection`, `operator`)
  - `confidence` score (0.0–1.0) where applicable
- Allow the operator to filter the workload list by `workload_type` or search by name/namespace.
- Link each workload to its detail panel where tags are shown alongside the eligibility verdict.

## Inputs
- **Source:** `GET /clusters/:id/workloads`
- **Format:** `Array<{ workload_id, name, namespace, workload_type, type_source: 'auto' | 'operator_override', tag_count }>`
- **Source:** `GET /clusters/:id/workloads/:id/tags`
- **Format:**
```json
{
  "workload_id": "string",
  "workload_type": "DAEMON | STATEFUL | BATCH | WEB | WORKER",
  "type_source": "auto | operator_override",
  "tags": [
    {
      "tag_name": "string",
      "tag_source": "kind_detection | pvc_detection | image_detection | resource_detection | namespace_detection | operator",
      "confidence": "number | null",
      "evidence": "string | null"
    }
  ]
}
```
- **Source:** Route parameters `cluster_id`, `workload_id` from React Router

## Outputs
- **Destination:** Rendered classification list and per-workload tag detail panels in the operator browser
- **Destination:** HTTP GET requests to backend API (read-only)

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access. Backend reads from: `workload_tags`, `workload_classifications`.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/clusters/:id/workloads` | Fetch all workloads with classification summary |
| `GET` | `/clusters/:id/workloads/:id/tags` | Fetch full tag detail for a specific workload |

## Dependencies
- **`frontend/shared/api`** — API client
- **`frontend/shared` components** — `DataTable`, `StatusBadge` (workload type, tag source), `Spinner`, `ErrorBoundary`
- **`frontend/shared/validation`** — Zod schemas for workload list and tag detail responses
- **`frontend/workload_review`** — Deep link to the review workflow if operator override is needed

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |

## Error Handling
- **Workload list API error:** Error card with retry; per-workload tag fetch is independent (one workload's tag fetch failure does not block others).
- **Confidence score absent:** When `confidence` is `null` (e.g., for `kind_detection` which is deterministic), the confidence column shows "N/A" rather than 0.
- **Empty tag list:** If a workload has no tags (should not happen in normal operation), the detail panel shows a "No tags detected" message and links to the support documentation.

## Future Enhancements
- Tag explanation tooltips: expand each tag source with a plain-language explanation of the detection logic.
- Tag conflict highlighter: if two tags from different sources imply contradictory classifications, highlight the conflict.
- Bulk re-classification trigger after multiple operator overrides.
