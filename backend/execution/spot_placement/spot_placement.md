# spot_placement

## Purpose
Handles Node and Pod scheduling guidance via labels and taints.

## Responsibilities
- Applies `balancekube.io/critical-only=true:NoSchedule` taint to on-demand nodes.
- Applies BalanceKube-managed labels to newly provisioned Spot nodes.

## Inputs
- N/A

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
