# Workload Classification: Queue Detection

## Purpose
Heuristic detector for message queue workloads.

## Responsibilities
- Inspects container images for common queue brokers: `rabbitmq`, `activemq`, `nats`, `pulsar`, `sqs` (if localstack).
- Applies the `queue` tag.

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
