# Infrastructure: Pricing Collection

## Purpose
Infrastructure configuration for external AWS Pricing API integration.

## Responsibilities
- Configures NAT Gateway scaling to handle high-bandwidth bulk JSON downloads.
- Sets up IAM roles for service accounts (IRSA) allowing the worker to call `ec2:describe_spot_price_history`.
- Configures Redis memory limits and eviction policies for caching pricing data.

## Inputs
- Source: IaC code.
- Format: HCL, YAML.

## Outputs
- Destination: AWS IAM, EKS, Redis.
- Format: Applied configurations.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- AWS IAM.

## Configuration
- NodeSelector to schedule pricing workers on network-optimized nodes.

## Error Handling
- N/A

## Future Enhancements
- N/A
