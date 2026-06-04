# Agent: Registration

## Purpose
One-time registration process executed on the agent's very first startup. Exchanges a short-lived registration token for a long-lived mTLS client certificate used for all subsequent communication.

## Responsibilities
- Exchanges the short-lived `registration_token` for a long-lived mTLS client certificate.
- POSTs to the backend `POST /api/v1/agents/register` with bearer token.
- Stores the newly issued certificate in a Kubernetes Secret within the agent's namespace.
- Prevents data collection until registration succeeds.
- On restart, checks whether the stored certificate is still valid before skipping re-registration.

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
- **Idempotency with validity check:** If agent restarts after registration, it checks whether the cert Secret exists AND whether the stored certificate is still valid (not expired, not within the `AGENT_CERT_ROTATION_LEAD_DAYS` window). If the certificate is still valid, registration is skipped. If the certificate is already expired or within the rotation window, the agent treats this as a first-time registration regardless of whether the Secret exists — it clears the old Secret content and replaces it with the newly issued certificate. This prevents the agent from running with an expired cert after a restart, which would cause all subsequent API calls to fail silently.
- If the registration token has already been consumed (`TOKEN_ALREADY_USED` response), the agent logs a fatal error and stops. The operator must generate a new token and update the Helm release.

## Future Enhancements
- N/A
