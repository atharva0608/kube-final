# Workers: Resource Analysis

## Purpose
Resource analysis job (Phase 2 E1B). Profiles workload resource utilization against historical metrics to determine provisioning states.

## Responsibilities
- Computes CPU state (THROTTLED/OVER_PROVISIONED/RIGHT_SIZED/UNDER_PROVISIONED).
- Computes memory state (OVER_PROVISIONED/RIGHT_SIZED/UNDER_PROVISIONED).
- Assesses network and storage intensity.
- Detects Java JVMs (affects data maturity rules).
- Detects batch spikes.
- Assesses data maturity (minimum 7 days required for reliable analysis).
- Triggers the eligibility engine upon completion.

## Inputs
- Queue: `queue:resource_analysis`
- Source: Internal queue trigger from `workers/workload_classification`.
- Format: Queue payload.

## Outputs
- Destination: Analysis table, downstream queue.
- Format: Database rows, internal trigger for `workers/eligibility_engine`.

## Events Produced
- N/A

## Events Consumed
- N/A (Queue driven).

## Database Tables
- Reads: `workload_profiles`, `workload_tags`, `assembled_snapshots`.
- Writes: `workload_analysis`.

## APIs
- N/A

## Dependencies
- `backend/resource_analysis`

## Configuration
- `MIN_DATA_MATURITY_DAYS`: Days of metrics required (default: 7).

## Error Handling
- Retries 3x.

## Future Enhancements
- Predictive resource scaling analysis.
