# capacity_provisioning

## Purpose
Handles the optional provisioning of Spot instances using Karpenter NodeClaims before workload migration.

## Responsibilities
- Checks `karpenter_control_mode`. If `managed`, generates NodeClaims. If `observe`, skips provisioning.
- Applies a 20% CPU/memory buffer.
- Polls NodeClaim status every 10s up to 120s.

## Inputs
- Reads `clusters.cluster_template`.

## Outputs
- N/A

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
