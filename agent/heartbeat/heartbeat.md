# Agent: Heartbeat

## Purpose
Maintains a persistent liveness signal and receives asynchronous instructions from the backend.

## Responsibilities
- Sends a POST to `POST /agents/:id/heartbeat` every 30 seconds.
- Payload includes agent version, collection cycle count, last error, and node count.
- Processes the HTTP response, which may contain instructions (e.g., "push inventory now", "upgrade").

## Inputs
- Source: Internal agent state (version, counters).
- Format: Heartbeat JSON payload.

## Outputs
- Destination: Backend API.
- Format: HTTP POST.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Calls `POST /agents/:id/heartbeat` (Backend).

## Dependencies
- Agent internal state.

## Configuration
- Heartbeat interval: 30s.

## Error Handling
- Logs failure but continues attempting on schedule. Backend tracks missed heartbeats.

## Future Enhancements
- N/A
