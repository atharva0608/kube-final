# Workers: Recommendations

## Purpose
Recommendation generation and savings estimation job (Final step of Phase 2).

## Responsibilities
- Runs the savings estimator for ELIGIBLE and ELIGIBLE_WITH_CONDITIONS workloads.
- Validates pricing freshness (rejects if pricing data is >60min old).
- Writes the recommendation and savings estimates to the database.
- Publishes the `cluster.analysed` event to signal the end of Phase 2.

## Inputs
- Source: Internal queue trigger from `workers/eligibility_engine`.
- Format: Queue payload.

## Outputs
- Destination: Recommendation tables, NATS events.
- Format: Database rows, `cluster.analysed` event.

## Events Produced
- `cluster.analysed`: Signals that Phase 2 analysis is complete and recommendations are ready.

## Events Consumed
- N/A (Queue driven).

## Database Tables
- Reads: `eligibility_verdicts`, `on_demand_prices`, `spot_prices`, `instance_catalog`.
- Writes: `recommendation_store`, `savings_estimates`.

## APIs
- N/A

## Dependencies
- `backend/recommendations`

## Configuration
- `MAX_PRICING_AGE_MINUTES`: Threshold for stale pricing warning (default: 60).

## Error Handling
- Retries 3x.
- Marks `pricing_freshness='STALE_PRICING'` if data is old, which shows a warning in the UI rather than failing the job.

## Future Enhancements
- Integration with FinOps tools for budget forecasting.
