# Infrastructure: Storage

## Purpose
Persistent storage provisioning and configuration.

## Responsibilities
- Provisions S3 buckets for CloudFormation template artifacts and Rollback Snapshots.
- Configures IAM policies and bucket policies for least-privilege access.
- Sets lifecycle rules for automatic pruning of old rollback payloads.

## Inputs
- Source: IaC.
- Format: YAML/HCL.

## Outputs
- Destination: AWS S3.
- Format: Cloud resources.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- AWS Provider.

## Configuration
- S3 Bucket replication settings for production environments.

## Error Handling
- N/A

## Future Enhancements
- N/A
