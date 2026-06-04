# Workload Classification: Database Detection

## Purpose
Heuristic detector for database workloads.

## Responsibilities
- Inspects container images for common databases: `postgres`, `mysql`, `mongo`, `cassandra`, `mariadb`, `cockroachdb`.
- Applies the `database` tag (which acts as a hard block for Spot instance eligibility).

## Inputs
- Source: Workload manifest.
- Format: JSON.

## Outputs
- Destination: Tag generator.
- Format: Tag struct.

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
