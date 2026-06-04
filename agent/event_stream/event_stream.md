# Agent: Event Stream

## Purpose
Optional real-time event streaming from the cluster to the backend.

## Responsibilities
- Watches for critical Kubernetes Events (`v1.Event`), such as OOMKills, Evictions, or NodeNotReady.
- Filters out high-volume noise (e.g., normal pod scheduling events).
- Streams filtered events to the backend for faster reaction times in Phase 3 (Drift Detection) or Phase 4 (Execution).

## Inputs
- Source: Kubernetes API Server (`v1.Event` stream).
- Format: Kubernetes Event objects.

## Outputs
- Destination: Backend API.
- Format: HTTP POST (`POST /agents/:id/events`).

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Calls `POST /agents/:id/events` (Backend).

## Dependencies
- K8s API.

## Configuration
- Event filter rules (provided by backend during registration/heartbeat).

## Error Handling
- Drops events if the backend is unreachable to prevent memory pressure on the agent.

## Future Enhancements
- Dedicated WebSocket connection for low-latency streaming.
