# Pricing Collection: Spot Price

## Purpose
Spot pricing data storage and fast lookups.

## Responsibilities
- Stores real-time Spot prices per Instance Type, Region, and Availability Zone.
- Provides the target cost basis for savings estimation.

## Inputs
- Source: Pricing Collection Worker.
- Format: Database upserts and Redis SETs.

## Outputs
- Destination: Recommendation Engine.
- Format: Fast Redis lookups (`price:{instance_type}:{az}`).

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `spot_prices` (id, instance_type, region, az, price_usd_hr, collected_at).

## APIs
- N/A

## Dependencies
- `backend/database`
- Redis.

## Configuration
- N/A

## Error Handling
- Redis cache misses fall back to the PostgreSQL database.

## Future Enhancements
- N/A
