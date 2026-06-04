# Spot Risk Collection: Risk Normalization

## Purpose
Converts raw AWS frequency bands into the internal BalanceKube risk scale.

## Responsibilities
- Maps AWS bands (0-4) to a 0-10 linear risk score.
- Categorizes scores into risk levels (`low`: ≤3, `medium`: 4-6, `high`: ≥7).
- Caches the normalized score in Redis for fast access during Phase 2.

## Inputs
- Source: Raw interruption rates.
- Format: Integer bands.

## Outputs
- Destination: Database and Redis.
- Format: Normalized scores.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `risk_scores` (id, instance_type, region, risk_score, interruption_band, risk_level, updated_at).

## APIs
- N/A

## Dependencies
- `backend/database`
- Redis

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- N/A
