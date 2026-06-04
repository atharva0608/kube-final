# Agent: Registration

## Purpose
One-time registration process executed on the agent's very first startup.

## Responsibilities
- Exchanges the short-lived `registration_token` for a long-lived mTLS client certificate.
- POSTs to the backend `POST /api/v1/agents/register` with bearer token.
- Stores the newly issued certificate in a Kubernetes Secret within the agent's namespace.
- Prevents data collection until registration succeeds.

## Inputs
- Source: Operator-provided Helm value (`REGISTRATION_TOKEN`).
- Format: JWT string.

## Outputs
- Destination: Backend API, local K8s Secret.
- Format: HTTP POST, K8s Secret object.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Calls `POST /api/v1/agents/register` (Backend).

## Dependencies
- K8s API (to create Secret).

## Configuration
- Uses `GET /health` on backend as a pre-registration connectivity check.

## Error Handling
- Retries with exponential backoff if registration fails or network is unreachable.
- Idempotent: If agent restarts after registration, it skips this step if the cert Secret exists.

## Future Enhancements
- N/A
