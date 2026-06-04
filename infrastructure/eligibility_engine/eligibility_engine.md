# Infrastructure: Eligibility Engine

## Purpose
Infrastructure supporting the rules engine evaluation.

## Responsibilities
- Ensures fast caching of hard/conditional rules if loaded from an external source.
- Scales the worker pods rapidly to prevent pipeline bottlenecks between Analysis and Recommendations.

## Inputs
- Source: IaC.
- Format: YAML.

## Outputs
- Destination: EKS.
- Format: Applied resources.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- Redis.

## Configuration
- N/A

## Error Handling
- N/A

## Future Enhancements
- N/A
