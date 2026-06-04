# Pricing Collection: Instance Catalog

## Purpose
Hardware specifications for cloud instances.

## Responsibilities
- Stores CPU (vCPU), memory (GiB), and network performance tiers for all supported instance types.
- Used by the savings estimator to find alternative instance types that fit a workload's resource profile if the current node type is unavailable as Spot.

## Inputs
- Source: Pricing Collection Worker (via `DescribeInstanceTypes`).
- Format: Database inserts.

## Outputs
- Destination: Recommendation Engine, Drift Detection.
- Format: Database queries.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `instance_catalog` (id, instance_type, vcpu, memory_gi, network_perf, instance_family, architecture, updated_at).

## APIs
- N/A

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- Instance capability flags (e.g., EBS optimized, NVMe attached).
