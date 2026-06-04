# Workers: Eligibility Engine

## Purpose
Eligibility computation job. Evaluates all hard and conditional rules to determine if a workload is eligible for Spot placement.

## Responsibilities
- Evaluates hard block rules (e.g., Databases, PVCs without PDBs, throttled workloads).
- Evaluates conditional rules (warnings for high risk, tight memory, JVMs).
- Applies operator overrides.
- Computes the final eligibility verdict (`ELIGIBLE`, `ELIGIBLE_WITH_CONDITIONS`, `NOT_ELIGIBLE`) along with structured `decision_reasons`.
- Triggers the recommendation engine upon completion.

## Inputs
- Queue: `queue:eligibility_engine`
- Source: Internal queue trigger from `workers/resource_analysis`.
- Format: Queue payload.

## Outputs
- Destination: Eligibility table, downstream queue.
- Format: Database rows, internal trigger for `workers/recommendations`.

## Events Produced
- N/A

## Events Consumed
- N/A (Queue driven).

## Database Tables
- Reads: `workload_analysis`, `workload_tags`, `operator_overrides`, `risk_scores`.
- Writes: `eligibility_verdicts`.

## APIs
- N/A

## Dependencies
- `backend/eligibility_engine`

## Configuration
- N/A

## Error Handling
- Retries 3x.
- Always computes positive signals even for blocked workloads (to show what would fix the block).

## Future Enhancements
- N/A
