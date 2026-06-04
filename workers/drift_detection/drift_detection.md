# Workers: Drift Detection

## Purpose
Phase 3 drift detection scheduled job. Continuously compares the planned state against the live cluster state while a recommendation is pending approval.

## Responsibilities
- Runs the snapshot comparator against the latest inventory.
- For patchable drift: generates a `plan_delta` and updates the recommendation in-place.
- For invalidating drift: marks the recommendation as `STALE` and publishes `cluster.reanalyse`.
- Publishes drift events.

## Inputs
- Source: `cluster.analysed` event (immediate run) + Cron (every 5 mins).
- Format: Event payload or cron trigger.

## Outputs
- Destination: Drift/delta tables, NATS events.
- Format: Database rows, events.

## Events Produced
- `drift.detected`
- `drift.patchable`
- `drift.invalidated`
- `cluster.reanalyse` (Internal, forces Phase 2 rerun).

## Events Consumed
- `cluster.analysed`

## Database Tables
- Reads: `recommendation_store`, `assembled_snapshots`.
- Writes: `drift_events`, `plan_deltas`.

## APIs
- N/A

## Dependencies
- `backend/drift_detection`

## Configuration
- `DRIFT_CHECK_CRON`: default `*/5 * * * *`.

## Error Handling
- Retries 3x.

## Future Enhancements
- Webhook triggers to external GitOps systems on drift.
