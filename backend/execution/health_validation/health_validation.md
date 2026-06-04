# health_validation

## Purpose
Verifies cluster health post-migration to determine execution success or trigger rollback.

## Responsibilities
- Validates that >= 75% of SPOT group pods are Running on Spot within 10 minutes.
- Validates that zero HIGH/CRITICAL pods are on Spot.
- Validates StatefulSets have no Pending pods > 5 minutes.

## Inputs
- N/A

## Outputs
- N/A

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- N/A

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- N/A
