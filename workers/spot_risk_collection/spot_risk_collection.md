# Workers: Spot Risk Collection

## Purpose
Spot Advisor scrape job. Pulls historical interruption data to compute risk scores for Spot instances.

## Responsibilities
- Fetches the AWS Spot Instance Advisor JSON (static JSONP file).
- Strips the JSONP wrapper before parsing.
- Maps AWS interruption frequency bands to an internal 0-10 risk score.
- Caches risk scores in Redis with an 86400s (24h) TTL.

## Inputs
- Queue: `queue:spot_risk_collection`
- Source: Cron schedule (daily).
- Format: Internal trigger.

## Outputs
- Destination: Risk score tables and Redis cache.
- Format: Database rows, Redis keys.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- Writes: `interruption_rates`, `risk_scores`, `spot_risk_history`.

## APIs
- N/A

## Dependencies
- External: `https://spot-price.s3.amazonaws.com/spot.js`

## Configuration
- `SPOT_RISK_REFRESH_CRON`: default `0 0 * * *`.

## Error Handling
- Retries 3x on network failure.
- On final failure: retains previous values (stale is acceptable for this informational signal). Logs `IRATE_FETCH_FAILED` but does not alert.

## Future Enhancements
- Real-time spot interruption prediction via ML.
