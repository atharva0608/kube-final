# Backend Events

## Purpose
Domain event publisher using the outbox pattern. This module ensures reliable, at-least-once delivery of domain events to downstream consumers while maintaining per-cluster ordering.

## Responsibilities
- Publishes events using the transactional outbox pattern (writes to `event_store` BEFORE publishing).
- Manages NATS as the primary transport, with Redis Streams/PostgreSQL LISTEN-NOTIFY as fallback.
- Guarantees at-least-once delivery (sweeper job retries unpublished events).
- Guarantees per-cluster ordering within a single domain.
- Handles dead-lettering for events that fail to process after all retries.

## Inputs
- Source: Function calls from other backend domains.
- Format: TypeScript discriminated union types (`DomainEvent` interface).

## Outputs
- Destination: `event_store` table and NATS topics.
- Format: Standard envelope (`event_id`, `event_type`, `schema_version`, `emitted_at`, `cluster_id`, `payload`).

## Events Produced
- All events across the system are routed through this module, but it does not originate business events itself.

## Events Consumed
- N/A

## Database Tables
- `event_store` (id, event_type, payload JSONB, schema_version, published, emitted_at, published_at) - Owned.
- `dead_letter_jobs` - Written to for permanent failures.

## APIs
- N/A (Internal module only).

## Dependencies
- `shared/events` (Event definitions and schemas).
- NATS client.

## Configuration
- `NATS_URL`: NATS server connection string.
- `EVENT_SWEEPER_INTERVAL_MS`: How often to poll for unpublished outbox events (default: 5000).

## Error Handling
- Sweeper job retries unpublished events at-least-once. 
- Workers that fail to process events write to `dead_letter_jobs` after exhausting retries.
- Cross-domain ordering is NOT guaranteed; consumers must be idempotent.

## Future Enhancements
- Kafka support for higher throughput environments.
