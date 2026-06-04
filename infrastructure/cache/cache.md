# Infrastructure: Cache

## Purpose
Redis caching layer provisioning and configuration.

## Responsibilities
- Provisions AWS ElastiCache for Redis.
- Configures cluster mode for horizontal scaling (if required).
- Configures VPC security groups allowing access only from worker/backend pods.
- Manages parameter groups (e.g., `maxmemory-policy`).

## Inputs
- Source: IaC.
- Format: HCL.

## Outputs
- Destination: AWS ElastiCache.
- Format: Redis cluster.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- AWS ElastiCache.

## Configuration
- Eviction policy (e.g., `volatile-lru`).

## Error Handling
- Failover handled natively by ElastiCache Multi-AZ.

## Future Enhancements
- N/A
