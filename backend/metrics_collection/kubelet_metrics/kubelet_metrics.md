# Metrics Collection: Kubelet Metrics

## Purpose
Parser and ingestion handler for metrics sourced directly from the Kubelet Summary API.

## Responsibilities
- Parses the Kubelet Summary API JSON format.
- Maps Kubelet pod references to our internal Pod UUIDs.
- Extracts CPU, Memory, Network, and Filesystem datapoints.

## Inputs
- Source: Metrics payload from the agent DaemonSet.
- Format: JSON matching Kubelet Summary API structure.

## Outputs
- Destination: Internal normalization functions.
- Format: Standardized metric objects.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A (Handles parsing before DB write).

## APIs
- Invoked via `POST /agents/:id/metrics`.

## Dependencies
- N/A

## Configuration
- N/A

## Error Handling
- Silently drops unparseable pods and logs a warning.

## Future Enhancements
- N/A
