# lock_manager

## Purpose
Manages the per-cluster execution mutex to prevent concurrent Phase 4 executions from corrupting the cluster state.

## Responsibilities
- Acquire and release `execution_locks` before and after execution.
- Auto-expire locks after 2 hours (TTL) to recover from crashes.

## Database Tables
- Writes: `execution_locks` (cluster_id, acquired_at, expires_at, execution_id)

## Inputs
- N/A

## Outputs
- N/A

## Events Produced
- N/A

## Events Consumed
- N/A

## APIs
- N/A

## Dependencies
- N/A

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- N/A
