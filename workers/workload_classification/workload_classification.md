# Workers: Workload Classification

## Purpose
Tag generation and classification job (Phase 2 E1A). Runs heuristic detectors to classify workloads based on their properties and images.

## Responsibilities
- Runs all detectors: java, batch, stateful, database, cache, queue, monitoring, unknown.
- Assigns workload type based on priority order.
- Deletes and reinserts `workload_tags` rows on every cycle (ensuring no stale tags).
- Triggers resource analysis upon completion.

## Inputs
- Source: `cluster.collected` event AND `review.completed` event.
- Format: Event payloads.

## Outputs
- Destination: Tags and classifications tables, downstream queue.
- Format: Database rows, internal trigger for `workers/resource_analysis`.

## Events Produced
- N/A (Triggers downstream worker via queue).

## Events Consumed
- `cluster.collected`
- `review.completed`: Unblocks analysis after operator sign-off.

## Database Tables
- Writes: `workload_tags`, `workload_classifications`.

## APIs
- N/A

## Dependencies
- `backend/workload_classification`

## Configuration
- N/A

## Error Handling
- Retries 3x.
- Idempotent: re-running with the same `snapshot_id` produces the same exact tag output.

## Future Enhancements
- ML-based workload classification.
