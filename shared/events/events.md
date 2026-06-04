# Shared: Events

## Purpose
The definitive registry for all domain events across the BalanceKube platform.

## Responsibilities
- Defines TypeScript interfaces for all event payloads.
- Maintains the event topic routing map (NATS subjects).
- Enforces strict schema validation for events before they are published to the `event_store`.

## Inputs
- Source: Modules generating events.
- Format: Raw data.

## Outputs
- Destination: Type checking and runtime validation.
- Format: Validated event envelopes.

## Events Produced
- N/A (Defines them, doesn't produce them).

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- `zod` (for runtime schema validation).

## Configuration
- N/A

## Error Handling
- Throws validation errors if an event payload does not match its schema.

## Future Enhancements
- AsyncAPI specification generation from these schemas.
