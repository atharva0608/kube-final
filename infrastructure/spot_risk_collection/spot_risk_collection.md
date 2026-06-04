# Infrastructure: Spot Risk Collection

## Purpose
Infrastructure configuration for the Spot Advisor scrape job.

## Responsibilities
- Egress network policy configuration allowing outbound HTTPS traffic to `spot-price.s3.amazonaws.com`.
- CronJob definitions for Kubernetes scheduling (if not using BullMQ).

## Inputs
- Source: IaC code.
- Format: YAML.

## Outputs
- Destination: EKS cluster network policies.
- Format: Applied policies.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- Kubernetes NetworkPolicies (Cilium/Calico).

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- N/A
