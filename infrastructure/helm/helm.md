# Infrastructure: Helm

## Purpose
Kubernetes application packaging for BalanceKube.

## Responsibilities
- Maintains the Helm chart for the `backend` API and `workers`.
- Maintains the Helm chart for the `agent` (deployed on customer clusters).
- Defines Deployment, Service, Ingress, HPA, ConfigMap, and Secret templates.

## Inputs
- Source: Helm `values.yaml` files.
- Format: YAML.

## Outputs
- Destination: Kubernetes API.
- Format: K8s manifests.

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
- Default values provided in `values.yaml`, overridden per environment.

## Error Handling
- Helm rollback used during failed deployment pipelines.

## Future Enhancements
- OCI-compliant Helm chart registry.
