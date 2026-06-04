# Infrastructure: Recommendations

## Purpose
Infrastructure supporting the final Phase 2 savings estimation.

## Responsibilities
- Configures database indexing on `recommendation_store` and `savings_estimates` to support complex frontend UI queries (filtering by status, savings amount).
- Sets up archival storage (e.g., S3 buckets) if recommendations older than 90 days need to be cold-stored instead of deleted.

## Inputs
- Source: IaC.
- Format: YAML/HCL.

## Outputs
- Destination: Live infrastructure.
- Format: Configured resources.

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
