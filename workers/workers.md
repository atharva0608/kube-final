# Workers

## Purpose
Background worker processes for event-driven pipeline execution. This module handles all asynchronous tasks, long-running processes, and scheduled cron jobs.

## Responsibilities
- Processes domain events and queue messages via BullMQ (Redis-backed).
- Enforces retry strategies and exponential backoffs for transient failures.
- Routes permanent failures to dead-letter queues.
- Enables event replay from the `event_store` to recover failed pipeline stages.

## Queues
Each sub-module operates on a dedicated BullMQ queue to allow independent scaling and isolated failure domains:
- `queue:onboarding`
- `queue:cluster_inventory`
- `queue:metrics_collection`
- `queue:pricing_collection`
- `queue:spot_risk_collection`
- `queue:snapshot_assembly`
- `queue:workload_review`
- `queue:workload_classification`
- `queue:resource_analysis`
- `queue:eligibility_engine`
- `queue:recommendations`
- `queue:drift_detection`
- `queue:execution`
- `queue:rollback`
- `queue:notifications`

## Inputs
- Source: NATS events, BullMQ queues, Cron schedules.
- Format: Domain event JSON payloads.

## Outputs
- Destination: Database tables, new events, external APIs (AWS, K8s).
- Format: Varies by specific worker.

## Events Produced
- Varies by sub-worker (e.g., `cluster.collected`, `cluster.analysed`).

## Events Consumed
- Varies by sub-worker (e.g., `org.created`, `recommendation.approved`).

## Database Tables
- `dead_letter_jobs` (id, worker, job_payload, error, attempts, created_at) - Owned by `workers/common`.

## APIs
- N/A (Workers never expose HTTP directly).

## Dependencies
- `shared/events`
- `backend/database`
- BullMQ, Redis

## Configuration
- `REDIS_URL`: Redis connection string for BullMQ.
- `WORKER_CONCURRENCY`: Default concurrency per worker type.

## Error Handling
- Idempotent execution where possible.
- Configurable retry policies per worker type.
- Dead-letter handling on final failure with full context logging.

## Future Enhancements
- Worker autoscale based on queue depth.
