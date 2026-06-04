# Pricing Collection: On Demand

## Purpose
On-Demand pricing data storage and queries.

## Responsibilities
- Stores global On-Demand instance pricing for AWS.
- Used as the baseline to calculate potential savings for workloads currently running on On-Demand nodes.

## Inputs
- Source: Pricing Collection Worker.
- Format: Database upserts.

## Outputs
- Destination: Recommendation Engine.
- Format: Database queries.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `on_demand_prices` (id, instance_type, region, price_usd_hr, updated_at).

## APIs
- N/A (Internal module only).

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- N/A
