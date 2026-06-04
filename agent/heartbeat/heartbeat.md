# Agent: Heartbeat

## Purpose
Maintains a persistent liveness signal and receives asynchronous instructions from the backend.

## Responsibilities
- Sends a POST to `POST /api/v1/agents/:id/heartbeat` every 30 seconds.
- Payload includes agent version, collection cycle count, last error, and node count.
- Processes the HTTP 200 response body, which may contain an `instructions` array. Each instruction has a `type` field. Supported instruction types:
  - `EXECUTE_PLAN` — the backend has delivered a signed execution plan. The agent immediately verifies the HMAC signature, performs a local pre-execution check (nodes referenced in plan present and Ready? any referenced workload in rolling update?), then begins executing the plan steps.
  - `PUSH_INVENTORY` — the backend requests an out-of-cycle inventory collection. The agent triggers an immediate inventory snapshot and POST.
  - `UPGRADE` — the backend signals an upgrade is available. The agent polls `GET /api/v1/agents/:id/upgrade` for the signed binary URL.
- An empty `instructions` array or absent field means no action needed; heartbeat is purely a liveness signal for that cycle.

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
- Calls `POST /api/v1/agents/:id/heartbeat` (Backend).

## Dependencies
- Agent internal state.

## Configuration
- Heartbeat interval: 30s (controlled by `AGENT_HEARTBEAT_INTERVAL_SECONDS` returned at registration).

## Error Handling
- Logs failure but continues attempting on schedule. Backend tracks missed heartbeats.
- If the heartbeat response cannot be parsed (malformed JSON), the instruction is skipped and logged. The next heartbeat cycle is unaffected.
- If an `EXECUTE_PLAN` instruction has an invalid HMAC signature, the plan is rejected and the backend is notified via the next heartbeat's `last_error` field.

## Future Enhancements
- N/A
