# account_collector

## Purpose
The `account_collector` module is responsible for fetching cloud-provider-level metadata (such as ASG membership, exact lifecycle states, reserved instance coverage) directly from the AWS account. Note: This module is largely planned for Phase 4/5 development. Currently, it acts as a placeholder that owns the `node_enrichments` table, which `snapshot_assembly` relies on via a LEFT JOIN.

## Responsibilities
- Pull metadata from AWS APIs (EC2, Auto Scaling).
- Store enrichment data in the `node_enrichments` table.
- Provide data that is not observable from within the Kubernetes cluster.

## Inputs
- **Source:** AWS APIs (EC2 DescribeInstances, AutoScaling DescribeAutoScalingGroups).

## Outputs
- **Destination:** `node_enrichments` table.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- **Tables this module owns (writes to):**
  - `node_enrichments` - Contains node-level data (e.g. ASG name, reserved instance status) fetched from the cloud provider.

## APIs
- N/A

## Dependencies
- AWS SDK (EC2, Auto Scaling).

## Configuration
- N/A

## Error Handling
- N/A (Deferred to Phase 4/5).

## Future Enhancements
- Fully implement the data collection logic in Phase 4/5 to enrich the snapshots accurately with real AWS-level metadata.
