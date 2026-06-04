# Infrastructure: Workload Classification

## Purpose
Infrastructure for the compute-heavy Phase 2 E1A engine.

## Responsibilities
- Helm configuration for allocating higher CPU limits to the classification worker pods.
- Setting up HPA to scale classification workers based on the `cluster.collected` event backlog.

## Inputs
- Source: IaC.
- Format: YAML.

## Outputs
- Destination: EKS.
- Format: Applied resources.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- KEDA (Kubernetes Event-driven Autoscaling) if scaling by queue depth.

## Configuration
- HPA max replicas limits to prevent database connection exhaustion.

## Error Handling
- N/A

## Future Enhancements
- N/A
