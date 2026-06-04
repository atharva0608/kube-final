# recommendations

## Purpose
Acts as the final step of Phase 2 Workload Intelligence by assembling per-workload savings estimates for all eligible workloads and producing a cluster-level `recommendation_store` record. Publishes the `cluster.analysed` event that signals Phase 3 and beyond that a recommendation is ready for operator review and approval.

## Responsibilities
- Read all `eligibility_verdicts` for a given `(cluster_id, analysis_version)` and filter to only `ELIGIBLE` and `ELIGIBLE_WITH_CONDITIONS` workloads before computing savings.
- Calculate **current monthly cost** using on-demand pricing as a baseline: `od_price_hourly × 24 × 30 × node_count`. On-demand is always the baseline even if the cluster already runs some Spot nodes, ensuring a consistent cost reference.
- Calculate **Spot cost** using the cheapest fitting instance type from `on_demand_prices` / `spot_prices` scoped to the workload's Availability Zone(s).
- Apply **rightsized recommendations** from `workload_analysis` if available; fall back to current resource requests when rightsizing data is absent.
- Perform a **pricing freshness check**: if `spot_prices.captured_at` is older than 60 minutes, flag `pricing_freshness = 'STALE_PRICING'` and surface a warning in the UI.
- Set `savings_estimate_available = false` and show 'pricing unavailable' (never zero) when no Spot price exists for the required instance type in the required AZ.
- Persist one `recommendation_store` row and N `savings_estimates` rows (one per eligible workload).
- Manage the **recommendation status lifecycle**: `generated → pending_approval → approved → execution_ready → executing → success / rolled_back`.
- Expose APIs for operators to view and approve recommendations.
- Publish `cluster.analysed` after all writes are committed.

## Inputs
- **Source:** `eligibility_verdicts` table — verdict per workload, filtered to `ELIGIBLE` / `ELIGIBLE_WITH_CONDITIONS`.
- **Source:** `workload_analysis` table — rightsized CPU/memory, current requests.
- **Source:** `on_demand_prices` / `spot_prices` / `instance_catalog` tables — pricing data per instance type × AZ × region.
- **Source:** `assembled_snapshots` table — `snapshot_id`, `analysis_version`, `cluster_hash` for the current analysis batch.
- **Source:** `review.completed` NATS event — signals that operator sign-off on workload review is done and analysis can proceed.
- **Format:** PostgreSQL rows; pricing tables joined on `(instance_type, az, region)`.

## Outputs
- **Destination:** `recommendation_store` table — one row per cluster per analysis run.
- **Destination:** `savings_estimates` table — one row per eligible workload within a recommendation.
- **Destination:** NATS topic `cluster.analysed` — published after all DB writes are committed.
- **Format:**
  ```json
  {
    "event": "cluster.analysed",
    "cluster_id": "uuid",
    "recommendation_id": "uuid",
    "snapshot_id": "uuid",
    "analysis_version": "2024-06-04T06:00:00Z",
    "cluster_hash": "sha256-abc123",
    "analysed_at": "2024-06-04T06:05:12Z",
    "total_savings_monthly": 1240.50
  }
  ```

## Events Produced
| Event | Description |
|---|---|
| `cluster.analysed` | Published once per analysis cycle after `recommendation_store` and all `savings_estimates` rows are committed. Payload includes `cluster_id`, `recommendation_id`, `snapshot_id`, `analysis_version`, `cluster_hash`, `analysed_at`, `total_savings_monthly`. |

## Events Consumed
| Event | Action |
|---|---|
| `review.completed` | Unblocks Phase 2 analysis after operator sign-off on workload review is received. Triggers the savings estimation pipeline for the corresponding `(cluster_id, analysis_version)`. |

## Database Tables

**Tables this module owns (writes to):**
| Table | Description |
|---|---|
| `recommendation_store` | One record per cluster per analysis cycle. Columns: `id` (UUID), `cluster_id`, `snapshot_id`, `analysis_version`, `cluster_hash`, `status` (ENUM: `generated`, `pending_approval`, `approved`, `execution_ready`, `executing`, `success`, `rolled_back`), `total_savings_monthly` (decimal), `created_at`, `approved_at`, `approved_by` (user UUID). |
| `savings_estimates` | One record per eligible workload per recommendation. Columns: `recommendation_id` (FK), `workload_id`, `current_instance_type`, `current_cost_monthly`, `recommended_instance_type`, `spot_cost_monthly`, `savings_monthly`, `savings_pct`, `spot_risk_score`, `pricing_freshness_at`, `savings_estimate_available` (boolean). |

**Tables this module reads (read-only):**
| Table | Source Domain |
|---|---|
| `eligibility_verdicts` | Eligibility Engine |
| `workload_analysis` | Resource Analysis |
| `on_demand_prices`, `spot_prices`, `instance_catalog` | Pricing |
| `assembled_snapshots` | Snapshot Assembly |

## APIs
| Method | Path | Description |
|---|---|---|
| `GET` | `/clusters/:id/recommendations` | List all recommendations for a cluster, ordered by `created_at` descending. Returns status lifecycle, total savings, and workload count. |
| `GET` | `/clusters/:id/recommendations/:rec_id` | Retrieve a single recommendation with full `savings_estimates` breakdown per workload. Includes `pricing_freshness` warnings. |
| `POST` | `/clusters/:id/recommendations/:rec_id/approve` | Approve a recommendation, transitioning status from `pending_approval` → `approved`. Requires `operator` or `admin` role. Emits `recommendation.approved` internally to trigger Phase 4. |

## Dependencies
- **eligibility_engine** — must have written `eligibility_verdicts` for the current `analysis_version` before savings estimation starts.
- **resource_analysis** — provides rightsized instance recommendations consumed during Spot cost calculation.
- **pricing** module — `on_demand_prices`, `spot_prices`, and `instance_catalog` must be sufficiently fresh (< 60 min for spot, < 24 h for on-demand).
- **snapshot_assembly** — provides `snapshot_id`, `cluster_hash`, and `analysis_version` reference for the recommendation record.
- **NATS** — for publishing `cluster.analysed`; falls back to Redis Streams if NATS is unavailable.
- **shared/db** — PostgreSQL client; savings estimation and `cluster.analysed` publish wrapped in a single transaction with at-least-once delivery guarantee.
- **shared/logger** — structured logging with `recommendation_id`, `cluster_id`, `analysis_version` on all log lines.

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `PRICING_FRESHNESS_MAX_AGE_MINUTES` | `60` | Maximum age (minutes) of `spot_prices.captured_at` before `pricing_freshness = 'STALE_PRICING'` is flagged. |
| `SAVINGS_OD_HOURS_PER_MONTH` | `720` | Hours per month used in OD cost baseline: `24 × 30`. Adjustable for regions with different billing periods. |
| `SAVINGS_BUFFER_PERCENT` | `0` | Optional buffer percentage applied to Spot cost estimate for conservative display. Default 0 (no buffer). |
| `RECOMMENDATION_AUTO_APPROVE` | `false` | If `true`, recommendations are automatically transitioned to `approved` without operator action. **Only for dev/test environments.** |
| `NATS_CLUSTER_ANALYSED_TOPIC` | `cluster.analysed` | NATS topic on which `cluster.analysed` is published. |

## Error Handling
- **No eligible workloads:** If zero workloads pass eligibility, a `recommendation_store` row is still written with `total_savings_monthly = 0` and an empty `savings_estimates` set. `cluster.analysed` is still published so drift detection and UI are updated.
- **Spot price unavailable:** `savings_estimate_available = false` for the affected workload; the UI displays 'pricing unavailable' rather than $0 to avoid misleading the operator. The overall `recommendation_store` total excludes this workload's contribution.
- **Stale pricing:** `pricing_freshness = 'STALE_PRICING'` is set per-workload. A banner is shown in the UI. The recommendation is still generated; operators choose whether to wait for fresh prices or proceed.
- **Pricing table completely empty:** If `spot_prices` is entirely absent (e.g., first boot), the recommendation job is retried with exponential backoff (max 5 attempts, starting at 30s). After 5 failures it is dead-lettered in `dead_letter_jobs`.
- **`review.completed` event lost:** The recommendations worker is idempotent — re-processing the same `(cluster_id, analysis_version)` is safe. Duplicate `cluster.analysed` events are deduplicated downstream by `drift_detection` using `snapshot_id`.
- **Approval race condition:** The `approve` endpoint uses a PostgreSQL `SELECT FOR UPDATE` on `recommendation_store` to prevent double-approval if two operators submit simultaneously.

## Savings Labelling Policy
The savings figure is always labelled **"Potential Savings Estimate"** in all API responses and UI surfaces. It is never presented as a guarantee. This labelling is enforced at the API serialisation layer, not left to the frontend, to ensure consistency across all consumers.

## Future Enhancements
- **Multi-recommendation support:** Allow multiple recommendation versions for a cluster to be held simultaneously (e.g., conservative vs aggressive Spot mix), letting operators choose between strategies.
- **Currency conversion:** Currently all prices are USD; add per-org currency preference with live FX conversion from the pricing worker.
- **Reserved Instance / Savings Plan awareness:** Deduct RI/SP commitments from the OD baseline to compute true incremental savings.
- **Workload savings history:** Track realised savings post-execution and compare against the estimate to continuously improve the estimation model.
- **Approval workflow:** Add multi-person approval (require two operators to approve high-impact recommendations above a configurable savings threshold).
