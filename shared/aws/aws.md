# Shared: AWS

## Purpose
Centralized AWS SDK wrappers for STS, EKS, EC2, and CloudFormation interactions.

## Responsibilities
- Manages STS `AssumeRole` logic using the organization's `external_id`.
- Implements AWS API throttling retry logic (exponential backoff).
- Fetches pricing data via the EC2 Pricing API.
- Generates CloudFormation templates for customer onboarding.

## Inputs
- Source: Function arguments from backend/workers.
- Format: Organization credentials and target regions.

## Outputs
- Destination: AWS APIs.
- Format: SDK calls.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- Reads: AWS credentials cache from Redis.

## APIs
- N/A

## Dependencies
- `@aws-sdk/client-sts`
- `@aws-sdk/client-eks`
- `@aws-sdk/client-ec2`

## Configuration
- Default AWS region (fallback).

## Error Handling
- Maps AWS SDK errors (e.g., `AccessDenied`, `ThrottlingException`) to internal `AppError` types.

## Future Enhancements
- Support for AWS Organizations bulk discovery.
