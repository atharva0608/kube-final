# Infrastructure: Events

## Purpose
NATS event bus provisioning and configuration.

## Responsibilities
- Deploys NATS on EKS via the official Helm chart or provisions Amazon MSK (Kafka) if scaling beyond NATS limits.
- Configures JetStream for persistent messaging.
- Defines subject hierarchies and stream retention policies.

## Inputs
- Source: Helm / IaC.
- Format: YAML / HCL.

## Outputs
- Destination: NATS Cluster.
- Format: Message broker infrastructure.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- NATS JetStream.

## Configuration
- Max stream size, max message age.

## Error Handling
- N/A

## Future Enhancements
- N/A
