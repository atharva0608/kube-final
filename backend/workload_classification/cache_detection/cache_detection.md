# Workload Classification: Cache Detection

## Purpose
Heuristic detector for cache workloads.

## Responsibilities
- Inspects container images for common caching solutions: `redis`, `memcached`, `dragonfly`, `valkey`.
- Applies the `cache` tag.

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
