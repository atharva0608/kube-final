# Agent: Cluster Inventory

## Purpose
Collects and transmits the complete Kubernetes resource state to the backend platform.

## Responsibilities
- Packages in-memory `NodeMap` and `WorkloadMap` into a structured inventory payload.
- Pushes inventory to the backend when instructed by a heartbeat or locally triggered.
- Operates statelessly, treating the current memory snapshot as truth.

## Inputs
- Source: Agent Controller's in-memory state.
- Format: K8s resource structs.

## Outputs
- Destination: Backend API.
- Format: HTTP POST (`POST /agents/:id/inventory`).

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Calls `POST /agents/:id/inventory` (Backend).

## Dependencies
- `agent/controller`

## Configuration
- N/A

## Error Handling
- Retries on network failure. Backend handles deduplication based on snapshot context.

## Future Enhancements
- N/A
