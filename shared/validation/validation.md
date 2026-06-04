# Shared: Validation

## Purpose
Centralized data validation schemas used for API inputs and database writes.

## Responsibilities
- Defines `zod` schemas for request bodies, query parameters, and database payloads.
- Ensures data integrity at the system boundaries.

## Inputs
- Source: Incoming HTTP requests, event payloads.
- Format: Unknown JSON.

## Outputs
- Destination: Application logic.
- Format: Strongly-typed, validated TypeScript objects.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- `zod`

## Configuration
- N/A

## Error Handling
- Converts `zod` validation errors into structured `400 Bad Request` HTTP responses.

## Future Enhancements
- OpenAPI schema generation directly from Zod schemas.
