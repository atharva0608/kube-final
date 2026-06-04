# Spot Risk Collection: Interruption Rates

## Purpose
Raw interruption rate data storage.

## Responsibilities
- Stores the raw frequency bands (<5%, 5-10%, 10-15%, 15-20%, >20%) provided by AWS Spot Advisor.
- Calculates the `float_midpoint` of the band for numeric comparisons.

## Inputs
- Source: AWS Spot Advisor parser.
- Format: Parsed objects.

## Outputs
- Destination: Database.
- Format: Database rows.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `interruption_rates` (id, instance_type, region, frequency_band, float_midpoint, updated_at).

## APIs
- N/A

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- N/A
