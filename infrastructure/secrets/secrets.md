# Infrastructure: Secrets

## Purpose
Secret management for the platform.

## Responsibilities
- Integrates AWS Secrets Manager with Kubernetes via External Secrets Operator.
- Prevents hardcoded credentials in Git.
- Automatically injects database credentials, API keys, and JWT secrets into application Pods.

## Inputs
- Source: AWS Secrets Manager.
- Format: Key-Value pairs.

## Outputs
- Destination: Kubernetes Secrets.
- Format: K8s Secret objects.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- External Secrets Operator.

## Configuration
- N/A

## Error Handling
- If a secret is deleted from AWS, the associated Pods will fail to start on the next rollout.

## Future Enhancements
- Automatic pod restarts when secrets change (via Reloader).
