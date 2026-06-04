# node_drain

## Purpose
Safely evicts pods from source nodes to migrate them to target nodes.

## Responsibilities
- Uses Kubernetes Eviction API. Never uses force-delete.
- Respects PodDisruptionBudgets (PDB). Retries on HTTP 429 up to 10 times with 30s delay.
- Enforces pre-drain delay (10s normal, 15s if Istio sidecar).
- Always uncordons nodes on failure.

## Inputs
- N/A

## Outputs
- N/A

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
