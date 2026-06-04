# Metrics Collection: Metrics Server

## Purpose
Parser for fallback metrics sourced from the Kubernetes Metrics Server API.

## Responsibilities
- Parses `metrics.k8s.io` responses when the Kubelet Summary API is unreachable.
- Note: Provides lower resolution data (only CPU/Memory, no Network/Filesystem).

## Inputs
- Source: Metrics payload from the agent.
- Format: JSON matching `metrics.k8s.io` schema.

## Outputs
- Destination: Internal normalization functions.
- Format: Standardized metric objects.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Invoked via `POST /agents/:id/metrics`.

## Dependencies
- N/A

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- N/A
