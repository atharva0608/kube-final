# Workload Classification: Stateful Detection

## Purpose
Heuristic detector for stateful workloads.

## Responsibilities
- Identifies `StatefulSet` controllers.
- Identifies `Deployments` or `DaemonSets` that have persistent volume claims (PVCs) attached.
- Applies the `stateful` tag.

## Inputs
- Source: Workload manifest and PVC bindings.
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
