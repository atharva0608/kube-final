# Workload Classification: Monitoring Detection

## Purpose
Heuristic detector for observability workloads.

## Responsibilities
- Inspects container images and namespaces for common monitoring tools: `prometheus`, `grafana`, `loki`, `alertmanager`, `datadog-agent`, `newrelic`.
- Applies the `monitoring` tag.

## Inputs
- Source: Workload manifest.
- Format: JSON.

## Outputs
- Destination: Tag generator.
- Format: Tag struct.

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
