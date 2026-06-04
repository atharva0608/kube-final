# Workers: Onboarding

## Purpose
Async onboarding jobs triggered by organization creation, handling external integrations that should not block the initial HTTP response.

## Responsibilities
- Async CloudFormation template pre-generation and upload to S3.
- Cluster discovery polling after role validation.
- Initial AWS access validation retry if the first attempt timed out.

## Inputs
- Queue: `queue:onboarding`
- Source: `org.created` event.
- Format: `OrgCreated` event payload.

## Outputs
- Destination: S3 (CloudFormation template), external AWS APIs.
- Format: AWS API requests.

## Events Produced
- N/A

## Events Consumed
- `org.created`: Triggers the async onboarding sequence.

## Database Tables
- Reads: `organizations`.
- Writes: N/A (Uses `backend/onboarding` service layer).

## APIs
- N/A

## Dependencies
- `shared/aws` (STS, EKS, CloudFormation).
- `backend/onboarding` service.

## Configuration
- N/A

## Error Handling
- Retries 3x with exponential backoff.
- Failure does not block the main onboarding HTTP flow (operator sees result in UI).

## Future Enhancements
- N/A
