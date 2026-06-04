# Workload Classification: Tag Generation

## Purpose
Coordinates the generation of semantic tags for workloads.

## Responsibilities
- Invokes all specialized detectors (`java_detection`, `database_detection`, etc.).
- Aggregates the resulting tags.
- Identifies the `tag_source` (auto-detected vs operator override).
- Writes the final tag set to the `workload_tags` table.

## Inputs
- Source: Workload metadata from `assembled_snapshots`.
- Format: JSON objects.

## Outputs
- Destination: Database.
- Format: Database inserts.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `workload_tags` (id, cluster_id, workload_id, analysis_version, tags, tag_source, classification, type_source, created_at).

## APIs
- N/A

## Dependencies
- All other detection sub-modules.

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- N/A
