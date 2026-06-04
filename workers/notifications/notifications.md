# Workers: Notifications

## Purpose
Notification dispatch job. Delivers system alerts to operators via their configured channels (Email, Slack, Webhook).

## Responsibilities
- Reads organization notification preferences.
- Formats message payloads based on the channel and event type.
- Delivers notifications to SES (email), Slack (webhook), or custom HTTP endpoints.
- Records delivery status in the `notifications` table.

## Inputs
- Queue: `queue:notifications`
- Source: Notification events (`review.pending`, `drift.detected`, `execution.started`, etc.).
- Format: Event payloads.

## Outputs
- Destination: External APIs (AWS SES, Slack), `notifications` table.
- Format: HTTP requests, database rows.

## Events Produced
- N/A

## Events Consumed
- `review.pending`
- `drift.detected`
- `execution.started`, `execution.completed`, `execution.rolled_back`
- `agent.heartbeat_missed`
- `recommendation.ready`

## Database Tables
- Writes: `notifications`.

## APIs
- N/A

## Dependencies
- External: AWS SES, Slack APIs.
- `backend/notifications`

## Configuration
- Channel specific credentials/URLs configured per-org.

## Error Handling
- Retries 5x with exponential backoff on delivery failure.
- Dead-letters if all retries fail.

## Future Enhancements
- Teams/Discord integrations.
