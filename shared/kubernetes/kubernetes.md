# Shared: Kubernetes

## Purpose
Utility functions for interacting with Kubernetes manifests and resource calculations.

## Responsibilities
- Calculates resource requests and limits (converting `100m` to millicores, `1Gi` to MiB).
- Parses topology spread constraints and affinity rules.
- Contains TypeScript interfaces for Kubernetes objects used in `snapshot_assembly`.

## Inputs
- Source: Raw Kubernetes JSON/YAML data from the agent.
- Format: K8s structs.

## Outputs
- Destination: Internal normalized formats.
- Format: TypeScript objects.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- `@kubernetes/client-node` (for types primarily).

## Configuration
- N/A

## Error Handling
- Gracefully handles missing fields (e.g., pods without resource requests).

## Future Enhancements
- N/A
