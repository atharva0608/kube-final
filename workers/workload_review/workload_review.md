# Workers: Workload Review

## Purpose
Review notification dispatch job. Notifies operators when workloads require manual classification or placement review.

## Responsibilities
- Formats notification payloads containing cluster name, workload count, review type (initial or partial), and a link to the review UI.
- Delegates actual delivery to `workers/notifications`.

## Inputs
- Queue: `queue:workload_review`
- Source: `review.pending` event.
- Format: Event payload.

## Outputs
- Destination: Notifications worker queue.
- Format: Internal queue message.

## Events Produced
- N/A (Delegates to notifications worker).

## Events Consumed
- `review.pending`

## Database Tables
- Reads: `workload_reviews`.

## APIs
- N/A

## Dependencies
- `workers/notifications`
- `backend/workload_review`

## Configuration
- N/A

## Error Handling
- Retries 2x on failure to queue notification.

## Future Enhancements
- N/A
