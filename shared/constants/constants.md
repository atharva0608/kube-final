# Shared: Constants

## Purpose
Centralized configuration values, enums, and static maps used across the application.

## Responsibilities
- Defines string literals used for database ENUM types (e.g., Worker Status, Execution Status).
- Defines default TTLs, retry counts, and system limits.
- Holds standard regex patterns (e.g., UUID validation).

## Inputs
- Source: Imported directly by application code.
- Format: TypeScript `const` and `enum`.

## Outputs
- Destination: Application logic.
- Format: Native JavaScript types.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- N/A (Should ideally have zero external dependencies).

## Configuration
- Values here act as the default configuration before environment overrides are applied.

## Error Handling
- N/A

## Future Enhancements
- N/A
