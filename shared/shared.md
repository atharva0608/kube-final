# Shared Libraries

## Purpose
Root documentation for the `shared/` directory. This directory contains common TypeScript libraries, types, constants, and utilities used by both the backend API and the background workers.

## Responsibilities
- Prevents code duplication between the `backend/` REST API and `workers/` daemon processes.
- Enforces consistent data structures and validation rules across domain boundaries.
- Provides centralized wrappers for external SDKs (e.g., AWS, Kubernetes).

## Inputs
- Source: Consumed as a local npm module or relative imports.
- Format: TypeScript code.

## Outputs
- Destination: Compiled into the backend and worker Node.js bundles.
- Format: JavaScript.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- Various third-party libraries (`aws-sdk`, `zod`, `pino`, etc.).

## Configuration
- N/A

## Error Handling
- Libraries throw standard `AppError` exceptions that are caught and handled by the caller.

## Future Enhancements
- Extraction into a private npm registry package for use by custom integrations.
