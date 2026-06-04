# Workers: Cluster Inventory

## Purpose
Periodic cluster inventory refresh job ensuring the platform has the latest view of connected clusters.

## Responsibilities
- Triggers periodic inventory collection cycles on connected agents.
- Tells the agent (via the next heartbeat response) to push fresh inventory.

## Inputs
- Source: Cron schedule (every 5 minutes), `cluster.registered` event, `execution.completed` event.
- Format: Internal queue triggers.

## Outputs
- Destination: Agent heartbeat instruction queue.
- Format: Agent instruction payload.

## Events Produced
- N/A

## Events Consumed
- `cluster.registered`: Schedules the first refresh.
- `execution.completed`: Triggers an immediate post-execution refresh.

## Database Tables
- N/A (Interacts via `backend/cluster_inventory` and `backend/agent_management`).

## APIs
- N/A

## Dependencies
- `backend/cluster_inventory`
- `backend/agent_management`

## Configuration
- `INVENTORY_REFRESH_CRON`: Cron expression for refresh (default: `*/5 * * * *`).

## Error Handling
- N/A for cron triggers (missed cycles catch up on the next run).

## Future Enhancements
- N/A
