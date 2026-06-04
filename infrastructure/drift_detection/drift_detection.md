# Infrastructure: Drift Detection

## Purpose
Infrastructure supporting Phase 3 drift detection.

## Responsibilities
- Configures cron scheduling for the drift detection worker.
- Sets up alerting rules for when the drift worker fails repeatedly (indicating a stuck queue).

## Inputs
- Source: IaC.
- Format: YAML.

## Outputs
- Destination: Kubernetes CronJobs or BullMQ scheduler infra.
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
