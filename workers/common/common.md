# Workers: Common

## Purpose
Worker base classes, retry logic, and dead-letter handling. Provides the foundation for all BullMQ worker processors.

## Responsibilities
- Provides the `BaseWorker` class with standard retry policies.
- Implements dead-letter writing for jobs that exhaust their retries.
- Performs idempotency key checks to prevent duplicate processing.
- Handles graceful shutdown, draining in-flight jobs before process exit.

## Inputs
- Source: BullMQ queues.
- Format: Job payloads.

## Outputs
- Destination: Dead-letter queue/table on failure.
- Format: `dead_letter_jobs` row.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- Writes: `dead_letter_jobs` (id, worker, job_payload, error, attempts, created_at) - Owned. Acts as a shared sink for both Backend event publish failures and Worker job failures.

## APIs
- N/A

## Dependencies
- BullMQ
- `backend/database`

## Configuration
- `WORKER_DEFAULT_RETRY_ATTEMPTS`: (default 3).

## Error Handling
- Centralizes error handling and logging (with `cluster_id` and `snapshot_id` context) for all workers.

## Future Enhancements
- Dead-letter UI replay mechanisms.
