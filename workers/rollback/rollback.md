# Workers: Rollback

## Purpose
Rollback execution job. Restores the pre-execution state from a rollback snapshot if an execution fails.

## Responsibilities
- Restores node labels and taints to their pre-execution state.
- Removes cordons applied during execution.
- Runs recovery validation to ensure the cluster is healthy.
- Marks the execution as rolled back.

## Inputs
- Queue: `queue:rollback`
- Source: `execution.failed` event (internal).
- Format: Event payload.

## Outputs
- Destination: Agent API, execution tables, NATS events.
- Format: Rollback instructions to agent, database updates, events.

## Events Produced
- `execution.completed` (with status=rolled_back)
- `execution.rolled_back` (Targeted event for alerting)

## Events Consumed
- `execution.failed` (internal).

## Database Tables
- Reads: `rollback_snapshots`.
- Writes: `execution_history` (updates status).

## APIs
- N/A

## Dependencies
- `backend/rollback`
- `backend/agent_management`

## Configuration
- N/A

## Error Handling
- Retries 2x.

## Future Enhancements
- N/A
