# Pricing Collection: Normalization

## Purpose
Standardizes pricing costs.

## Responsibilities
- Converts hourly instance prices (`$/hr`) to estimated monthly prices (`$/month`).
- Provides per-vCPU and per-GiB cost breakdowns for comparative analysis.

## Inputs
- Source: Hourly prices from AWS.
- Format: Floats.

## Outputs
- Destination: UI and Analysis engine.
- Format: Normalized monthly floats (using formula `hourly * 24 * 30`).

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
