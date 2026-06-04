# Workers: Pricing Collection

## Purpose
AWS pricing refresh job. Maintains an up-to-date catalog of Spot and On-Demand prices required for savings estimations.

## Responsibilities
- Fetches Spot prices every 15 minutes via `ec2:describe_spot_price_history`.
- Fetches On-Demand prices daily via bulk JSON download from AWS pricing endpoint.
- Updates Redis cache keys in a single pipeline round trip.
- Runs one task per region in parallel.

## Inputs
- Source: Cron schedules.
- Format: Internal triggers.

## Outputs
- Destination: Pricing tables, Redis cache.
- Format: Database rows, Redis keys.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- Writes: `on_demand_prices` (upsert), `spot_prices`, `instance_catalog`.

## APIs
- N/A

## Dependencies
- `shared/aws` (EC2 Pricing API).

## Configuration
- `SPOT_PRICE_REFRESH_CRON`: default `*/15 * * * *`.
- `OD_PRICE_REFRESH_CRON`: default `0 0 * * *`.

## Error Handling
- Throttle handling via `tenacity.retry` with exponential backoff (max 30s) and jitter.
- Retries 5x on failure.

## Future Enhancements
- Support for Azure/GCP pricing ingestion.
