# Shared: Logging

## Purpose
Standardized structured logging library used by all components.

## Responsibilities
- Wraps `pino` logger to enforce a consistent JSON log format.
- Automatically injects context variables (e.g., `cluster_id`, `snapshot_id`, `org_id`, `trace_id`).
- Masks sensitive data (e.g., tokens, passwords, AWS keys) before they reach standard output.

## Inputs
- Source: Log statements from application code.
- Format: Strings and objects.

## Outputs
- Destination: `stdout`.
- Format: JSON.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- `pino`

## Configuration
- `LOG_LEVEL`: Configurable log level (debug, info, warn, error).

## Error Handling
- N/A

## Future Enhancements
- Integration with OpenTelemetry for distributed tracing.
