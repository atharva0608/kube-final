# Infrastructure: Cluster Inventory

## Purpose
Infrastructure configuration specifically related to the Cluster Inventory module (both backend API and worker).

## Responsibilities
- Helm configurations for deploying the cluster inventory worker with appropriate resource limits.
- Horizontal Pod Autoscaler (HPA) settings to handle inventory burst traffic from thousands of agents.
- NATS topic configuration for inventory-related events.

## Inputs
- Source: Terraform / Helm variable files.
- Format: HCL, YAML.

## Outputs
- Destination: EKS cluster.
- Format: Deployed Kubernetes objects.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- Base platform infrastructure.

## Configuration
- HPA triggers based on queue depth and CPU utilization.

## Error Handling
- N/A

## Future Enhancements
- Dedicated read replicas for heavy inventory queries.
