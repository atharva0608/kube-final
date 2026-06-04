# Workers: Execution

## Purpose
Phase 4 execution orchestration job. Drives the actual mutation of the Kubernetes cluster by sending a signed execution plan to the agent.

## Responsibilities
- Acquires a distributed cluster lock (Redis `SET NX EX`).
- Validates 3-part identity (`snapshot_id`, `analysis_version`, `cluster_hash`).
- Generates the execution plan based on the recommendation.
- Signs the execution plan with an HMAC.
- Sends the plan to the agent.
- Monitors agent execution progress.
- Triggers rollback on failure.

## Inputs
- Queue: `queue:execution`
- Source: `recommendation.approved` event.
- Format: Event payload.

## Outputs
- Destination: Agent API, execution tables, NATS events.
- Format: Execution plan HTTP request, database rows, events.

## Events Produced
- `execution.started`
- `execution.completed`

## Events Consumed
- `recommendation.approved`

## Database Tables
- Writes: `execution_history`, `execution_locks`.

## APIs
- N/A

## Dependencies
- `backend/execution`
- `backend/agent_management` (to communicate with agent).

## Configuration
- N/A

## Error Handling
- NO AUTO-RETRY. Human approval is required for each execution attempt (Phase 4 is not inherently idempotent across full failures).
- If lock is held: queues execution for retry after the current run completes.
- On failure: triggers `workers/rollback`.

## Future Enhancements
- Integration with external change management systems (e.g., ServiceNow).
