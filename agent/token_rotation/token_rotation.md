# Agent: Token Rotation

## Purpose
Automates the lifecycle and rotation of the mTLS client certificate before expiration.

## Responsibilities
- Agent initiates rotation 7 days before certificate expiry.
- Requests a new certificate via `POST /agents/:id/rotate-token`.
- Stores the new certificate and uses it for the next heartbeat.
- Relies on the backend to retire the old certificate once the new one is used.

## Inputs
- Source: Local certificate expiry check.
- Format: Internal trigger.

## Outputs
- Destination: Backend API, local K8s Secret.
- Format: HTTP POST, Secret update.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Calls `POST /agents/:id/rotate-token` (Backend).

## Dependencies
- K8s API (to update Secret).

## Configuration
- Rotation window: 7 days prior to expiry.

## Error Handling
- Continues using the old valid certificate and retries rotation periodically if the request fails.

## Future Enhancements
- SPIFFE/SPIRE integration.
