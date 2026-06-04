# Spot Risk Collection: Historical Dataset

## Purpose
Historical retention of spot risk scores.

## Responsibilities
- Retains a 90-day rolling history of risk scores per instance type per region.
- Enables time-series analysis to determine if an instance type's risk profile is steadily degrading or improving.

## Inputs
- Source: Spot risk worker.
- Format: Database inserts.

## Outputs
- Destination: Analysis engines (Phase 2).
- Format: Time-series queries.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `spot_risk_history` (id, instance_type, region, risk_score, frequency_band, recorded_at). Monthly partitioned.

## APIs
- N/A

## Dependencies
- `backend/database`

## Configuration
- Retention: 90 days (via partition drops).

## Error Handling
- N/A

## Future Enhancements
- N/A
