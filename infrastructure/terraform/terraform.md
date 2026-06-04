# Infrastructure: Terraform

## Purpose
Core cloud infrastructure provisioning using HashiCorp Terraform.

## Responsibilities
- Provisions VPCs, subnets, and routing tables.
- Provisions EKS clusters, node groups, and IAM Roles for Service Accounts (IRSA).
- Provisions RDS instances and ElastiCache clusters.
- Manages Terraform state in S3 with DynamoDB locking.

## Inputs
- Source: Developer environment variable overrides (`.tfvars`).
- Format: HCL.

## Outputs
- Destination: AWS.
- Format: Live resources.

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
- Segmented by environment (`dev`, `staging`, `prod`).

## Error Handling
- CI/CD pipelines run `terraform plan` on PR, `terraform apply` on merge.

## Future Enhancements
- Terragrunt integration for DRY configuration across regions.
