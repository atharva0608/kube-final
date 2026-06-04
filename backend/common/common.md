# Backend Common

## Purpose
Shared backend utilities used across all backend modules. Provides the foundational HTTP middleware, error handling, and configuration loading required by the REST API.

## Responsibilities
- Defines structured error types (`AppError`).
- Provides HTTP middleware: JWT validation, `org_id` scoping, request logging, rate limiting.
- Provides request/response payload formatters and pagination utilities.
- Exposes standard health check endpoints.
- Loads and validates environment configuration.

## Inputs
- Source: Inbound HTTP requests (via Express/Fastify).
- Format: Raw HTTP requests.

## Outputs
- Destination: HTTP responses.
- Format: Standardized JSON responses and error formats.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- `GET /health`, `GET /healthz`, `GET /ready` (Health checks).

## Dependencies
- `shared/logging`
- Express / Fastify

## Configuration
- Config loader reads from standard environment variables with defaults.

## Error Handling
- All errors thrown as structured `AppError` with code, message, and statusCode.
- Middleware chain routes unhandled errors to a standard error formatter.

## Future Enhancements
- N/A
