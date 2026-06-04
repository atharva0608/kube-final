# Infrastructure: Kustomize

## Purpose
Kubernetes manifest overlays.

## Responsibilities
- Provides environment-specific overrides for base Helm charts where Helm templating is insufficient.
- Used primarily for raw manifests not packaged in Helm (e.g., third-party CRDs, monitoring stack overrides).

## Inputs
- Source: `kustomization.yaml` files.
- Format: YAML.

## Outputs
- Destination: `kubectl apply -k`.
- Format: Patched manifests.

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
