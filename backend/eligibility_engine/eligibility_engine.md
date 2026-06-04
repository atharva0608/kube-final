# eligibility_engine

## Purpose
Determines per-workload Spot placement eligibility by applying a structured set of hard-block and conditional rules against workload analysis, classification tags, operator overrides, and Spot risk scores. Produces a structured `eligibility_verdict` for every workload in a cluster snapshot, with human-readable `decision_reasons` that explain exactly why a workload was blocked, conditionally eligible, or fully eligible.

## Responsibilities
- Apply **hard-block rules** (HARD-001 through HARD-006, plus additional unconditional blocks) that categorically prevent a workload from being placed on Spot nodes.
- Apply **conditional rules** (COND-001 through COND-005) that produce warnings without blocking, surfaced as conditions in the verdict.
- Honour **operator overrides** stored in `operator_overrides`, giving them highest priority (HARD-006: manual `spot_eligible=false` always blocks).
- Compute **positive signals** for every workload — including blocked ones — to communicate what criteria would need to change for eligibility to be granted.
- Assemble ordered `decision_reasons` JSONB arrays with human-readable facts, rule codes, and severity levels.
- Write one `eligibility_verdict` row per workload per analysis version.
- Expose override management APIs so operators can pin, unpin, or restrict Spot eligibility for specific workloads.

## Inputs
- **Source:** `workload_analysis` table — CPU/memory profile, throttle state, rightsizing signals per workload.
- **Source:** `workload_tags` / `workload_classifications` tables — `workload_type` (e.g. `database`, `stateful`, `stateless`, `batch`), `is_batch_spike`, `data_maturity`.
- **Source:** `risk_scores` / `interruption_rates` tables — numeric `spot_risk_score` (0–10) per instance type × AZ.
- **Source:** `pods`, `deployments`, `statefulsets`, `daemonsets`, `pvcs`, `pdbs` tables — replica counts, PVC attachment, PDB configuration, HPA presence.
- **Source:** `operator_overrides` table — per-workload manual overrides set by operators via API.
- **Format:** All inputs are read as PostgreSQL rows; cross-joined in memory during analysis pass per `(cluster_id, workload_id, analysis_version)`.

## Outputs
- **Destination:** `eligibility_verdicts` table — one row per `(cluster_id, workload_id, analysis_version)`.
- **Destination:** `decision_reasons` — embedded as JSONB within `eligibility_verdicts.decision_reasons`; each element has `{ rule_code, severity, message, positive_signal }`.
- **Format:**
  ```json
  {
    "verdict": "ELIGIBLE_WITH_CONDITIONS",
    "decision_reasons": [
      { "rule_code": "COND-001", "severity": "WARNING", "message": "Spot risk score 6.2 — consider fallback instance types", "positive_signal": false },
      { "rule_code": "POSITIVE", "severity": "INFO", "message": "Workload is stateless with HPA configured", "positive_signal": true }
    ],
    "operator_override_id": null
  }
  ```

## Events Produced
- **N/A** — The eligibility engine writes to the database directly and does not emit events. The downstream `recommendations` module reads `eligibility_verdicts` and emits `cluster.analysed` once all Phase 2 engines complete.

## Events Consumed
- **N/A** — Invoked synchronously as part of the Phase 2 analysis pipeline, triggered after `workload_analysis` and `workload_classifications` are populated for a given `analysis_version`.

## Database Tables

**Tables this module owns (writes to):**
| Table | Description |
|---|---|
| `eligibility_verdicts` | One row per `(cluster_id, workload_id, analysis_version)`. Columns: `id`, `cluster_id`, `workload_id`, `analysis_version`, `verdict` (ENUM: `ELIGIBLE`, `ELIGIBLE_WITH_CONDITIONS`, `NOT_ELIGIBLE`), `decision_reasons` (JSONB), `operator_override_id` (FK → `operator_overrides`), `created_at`. |
| `operator_overrides` | Operator-authored per-workload Spot eligibility overrides. Columns: `id`, `cluster_id`, `workload_id`, `spot_eligible` (boolean), `target_instance_families` (text[]), `max_risk_score` (float), `set_by` (user UUID), `set_at`, `note` (free text). |

**Tables this module reads (read-only):**
| Table | Source Domain |
|---|---|
| `workload_analysis` | Resource Analysis |
| `workload_tags` | Classification |
| `workload_classifications` | Classification |
| `risk_scores` / `interruption_rates` | Spot Risk |
| `pods`, `deployments`, `statefulsets`, `daemonsets` | Cluster Inventory |
| `pvcs`, `pdbs` | Cluster Inventory |

## APIs
| Method | Path | Description |
|---|---|---|
| `POST` | `/clusters/:id/overrides` | Create or update an operator override for a specific workload. Body: `{ workload_id, spot_eligible, target_instance_families?, max_risk_score?, note? }`. |
| `GET` | `/clusters/:id/overrides` | List all active operator overrides for a cluster. Returns array of `operator_overrides` rows. |
| `DELETE` | `/clusters/:id/overrides/:override_id` | Remove a specific override. The next analysis cycle will re-evaluate the workload using automated rules only. |

## Dependencies
- **classification** module — must have populated `workload_tags` and `workload_classifications` before eligibility runs.
- **resource_analysis** module — must have populated `workload_analysis` (CPU/memory profiles, throttle state).
- **spot_risk** module — must have populated `risk_scores` and `interruption_rates`.
- **Cluster Inventory** — reads `pods`, `pvcs`, `pdbs`, `deployments`, `statefulsets`, `daemonsets` for structural workload facts.
- **shared/db** — PostgreSQL client; all reads and writes within a single serializable transaction per analysis batch.
- **shared/logger** — Structured logging with `cluster_id`, `workload_id`, `rule_code` on every rule evaluation.

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `ELIGIBILITY_HARD_RISK_THRESHOLD` | `8` | `spot_risk_score` threshold above which stateful workloads are hard-blocked (HARD-005). Valid range: 1–10. |
| `ELIGIBILITY_COND_RISK_THRESHOLD` | `6` | `spot_risk_score` threshold above which a COND-001 warning is emitted. Valid range: 1–10. |
| `ELIGIBILITY_MEMORY_PRESSURE_PCT` | `80` | Percentage of memory limit above which COND-002 is triggered. Valid range: 50–100. |
| `ELIGIBILITY_NETWORK_P95_MBPS` | `500` | p95 network throughput (Mbps) above which COND-005 is triggered. Valid range: 100–10000. |
| `ELIGIBILITY_JAVA_MIN_AGE_DAYS` | `7` | Minimum days of metrics history required for Java workloads before `data_maturity` is considered SUFFICIENT. **This is the shared source of truth for Java maturity** — `resource_analysis` reads this same environment variable rather than hard-coding 7. Default: 7. |
| `ELIGIBILITY_BATCH_SPIKE_MATURITY_BLOCK` | `true` | When `true`, workloads with `is_batch_spike=true` are blocked due to `data_maturity=INSUFFICIENT`. |

## Error Handling
- **Missing analysis data:** If `workload_analysis` or `workload_classifications` rows are absent for a workload, the engine emits `verdict=NOT_ELIGIBLE` with `decision_reasons` containing `{ rule_code: "DATA_MISSING", severity: "ERROR" }` rather than failing the entire batch.
- **Risk score unavailable:** If `risk_scores` has no row for the required instance type × AZ, HARD-005 and COND-001 are skipped; a `decision_reason` with `rule_code: "RISK_SCORE_UNAVAILABLE"` is added as an informational note.
- **Database write failure:** Wrapped in a retry (3 attempts, 500ms exponential backoff). If all retries fail, the analysis version is marked `FAILED` in `assembled_snapshots` and the error is logged with full context for manual inspection.
- **Override vs hard-block priority:** Hard blocks HARD-001 (database), HARD-002 (PVC no PDB), HARD-004 (PDB zero disruptions), and HARD-009 (DaemonSet) **cannot be overridden** even with `spot_eligible=true`. These blocks prevent data loss or unrecoverable cluster state. When an operator's `spot_eligible=true` override conflicts with one of these hard blocks, the verdict remains `NOT_ELIGIBLE`, the hard block rule code appears first in `decision_reasons`, and an additional reason is appended: `{ rule_code: 'OVERRIDE_DENIED', severity: 'INFO', message: 'This hard block cannot be overridden. To resolve: [specific remediation action for this rule].' }`. HARD-003 (single replica no HPA), HARD-005 (high risk stateful), HARD-007 (throttled), and HARD-008 (insufficient data) **CAN** be bypassed by an explicit `spot_eligible=true` override — operators accept responsibility for the risk.
- **Dead-letter:** Analysis batch failures are recorded in `dead_letter_jobs` with `module=eligibility_engine` for operator review.

## Hard-Block Rules Reference
| Rule Code | Condition | Rationale |
|---|---|---|
| HARD-001 | `workload_type = database` | Databases have persistent state and connection pools that cannot survive Spot interruption. |
| HARD-002 | PVC attached AND no PDB defined | Stateful workload with no disruption budget — eviction would orphan storage. |
| HARD-003 | Single replica AND no HPA | Single-replica workloads have zero redundancy; interruption causes full outage. |
| HARD-004 | `pdb.minAvailable = total replicas` | PDB configuration allows zero voluntary disruptions; eviction will always be rejected. |
| HARD-005 | `spot_risk_score ≥ 8` AND `classification = stateful` | Risk of interruption too high for stateful workloads. |
| HARD-006 | `operator_override.spot_eligible = false` | Explicit manual operator block; always honoured. |
| HARD-007 | CPU in THROTTLED state | Adding Spot preemption to an already-throttled workload increases unavailability risk. |
| HARD-008 | `data_maturity = INSUFFICIENT` | Insufficient metrics history (batch spike, or Java workload < 7 days old) prevents reliable analysis. |
| HARD-009 | `workload_type = daemonset` | DaemonSets run on every node by design; they cannot be drain-migrated. |

## Conditional Rules Reference
| Rule Code | Condition | Action |
|---|---|---|
| COND-001 | `spot_risk_score ≥ 6` | Warning: recommend fallback instance type families. |
| COND-002 | Memory usage > 80% of limit | Warning: memory pressure increases risk of OOM under Spot interruption. |
| COND-003 | Java runtime AND tight heap flags detected | Warning: JVM re-initialisation on new Spot node introduces latency spike. |
| COND-004 | `hpa.minReplicas = 1` | Warning: brief zero-replica window possible during scale-down + interruption race. |
| COND-005 | p95 network throughput > 500 Mbps | Warning: requires enhanced networking instance types; not all Spot pools support this. |

## Future Enhancements
- **ML-based risk scoring integration:** Replace static `ELIGIBILITY_HARD_RISK_THRESHOLD` with a model-driven interrupt probability estimate that accounts for time-of-day and fleet-level demand.
- **Override TTL:** Add optional `expires_at` to `operator_overrides` so temporary blocks auto-expire without manual cleanup.
- **Explain UI:** Surface `decision_reasons` JSON directly in the frontend workload detail panel with colour-coded rule codes.
- **HARD-005 AZ-aware scoring:** Current implementation uses the highest AZ risk score for a workload; future version should use workload's actual AZ distribution for a weighted average.
- **Batch spike detection feedback loop:** Feed confirmed-safe batch workloads back into the classifier to reduce future `data_maturity=INSUFFICIENT` false-positives.
