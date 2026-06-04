# Shared: Pricing

## Purpose
Common types and calculation logic for AWS pricing and savings estimations.

## Responsibilities
- Provides standard formulas for converting hourly costs to monthly costs (`price * 24 * 30`).
- Calculates percentage savings.
- Holds instance catalog types (vCPU, memory, network performance).

## Inputs
- Source: `on_demand_prices` and `spot_prices` data.
- Format: Decimal values.

## Outputs
- Destination: Recommendation engine.
- Format: Savings estimates.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- `decimal.js` or equivalent for precise financial math.

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- N/A
