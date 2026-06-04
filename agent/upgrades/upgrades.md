# Agent: Upgrades

## Purpose
Handles automated, in-place binary upgrades of the agent components.

## Responsibilities
- Processes upgrade instructions received via heartbeat.
- Downloads the new binary from a platform-signed URL.
- Verifies the SHA-256 checksum.
- Restarts the pod to apply the upgrade.

## Inputs
- Source: Heartbeat response payload.
- Format: Instruction with URL and checksum.

## Outputs
- Destination: Local filesystem (for binary), process exit.
- Format: Binary overwrite, graceful exit.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Calls `GET /agents/:id/upgrade` (Backend) to get download links if directed.

## Dependencies
- K8s (relies on ReplicaSet to restart the pod after exit).

## Configuration
- N/A

## Error Handling
- Aborts upgrade and continues running if checksum validation fails.

## Future Enhancements
- Custom Resource Definition (CRD) based upgrade coordination.
