# Infrastructure: Resource Analysis

## Purpose
Infrastructure for the Phase 2 E1B resource profiling engine.

## Responsibilities
- Allocates high memory limits to the analysis worker pods, as processing 90-day time-series arrays requires significant heap space.
- Configures PostgreSQL query timeouts to prevent long-running analytical queries from blocking operational transactions.

## Inputs
- Source: IaC.
- Format: YAML.

## Outputs
- Destination: EKS, PostgreSQL.
- Format: Applied resources and configurations.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- PostgreSQL performance tuning parameters.

## Configuration
- `statement_timeout` configuration on the specific database role used by this worker.

## Error Handling
- N/A

## Future Enhancements
- Spark/Presto cluster provisioning for heavy data crunching.
