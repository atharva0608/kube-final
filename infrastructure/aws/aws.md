# aws

## Purpose
The AWS module provisions the core cloud infrastructure that the BalanceKube platform requires to run. It creates the network foundation, managed database services, caching layer, compute environment for platform services, identity management, object storage, TLS certificates, and DNS—everything the application tier depends on before any BalanceKube code can be deployed.

## Responsibilities
- **VPC:** Provision a dedicated VPC with public and private subnets across at least two availability zones, NAT gateways for private subnet egress, security groups for backend API, worker, RDS, and Redis tiers.
- **RDS PostgreSQL:** Provision a Multi-AZ PostgreSQL instance (version 15+) with:
  - Encryption at rest (AWS-managed KMS key)
  - Automated backups (configurable retention, default 7 days)
  - Parameter group tuned for application workloads
  - Security group allowing inbound from backend API and worker security groups only
- **ElastiCache Redis:** Provision a Redis cluster (cluster mode disabled, single primary with optional replica) with:
  - Encryption in transit (TLS)
  - Security group allowing inbound from backend API and worker security groups only
  - Snapshot retention (default 1 day)
- **Compute (ECS or EKS):** Provision either an ECS cluster (Fargate) or an EKS cluster for running platform services (backend API, BullMQ workers). Task/pod definitions are managed per-service but the cluster infrastructure is provisioned here.
- **IAM:** Provision IAM roles for platform services with least-privilege policies: backend API role, worker role, execution worker role (elevated memory limit), agent registration role.
- **S3 buckets:**
  - CloudFormation template storage bucket (server-side encryption, no public access, pre-signed URL delivery, 24-hour object expiry lifecycle rule)
  - Snapshot payload overflow bucket (SSE-S3, lifecycle rule to delete objects older than 7 days)
  - Terraform state bucket (versioned, server-side encryption, MFA delete enabled)
- **ACM certificates:** Provision TLS certificates for the BalanceKube API domain (DNS-validated via Route53).
- **Route53:** Manage DNS records for the API (`api.balancekube.io` or equivalent) pointing to the load balancer.
- **DynamoDB:** Provision the Terraform state lock table (used only by the Terraform backend configuration itself).

## Inputs
- **Source:** Terraform variable file (`.tfvars`) per environment
- **Format:** HCL variable definitions

Key input variables:
| Variable | Description | Default |
|---|---|---|
| `environment` | `dev` / `staging` / `prod` | `dev` |
| `region` | AWS region | `us-east-1` |
| `vpc_cidr` | VPC CIDR block | `10.0.0.0/16` |
| `rds_instance_class` | RDS instance type | `db.t3.medium` |
| `rds_multi_az` | Enable Multi-AZ RDS | `false` (dev), `true` (prod) |
| `rds_backup_retention_days` | Automated backup retention | `7` |
| `redis_node_type` | ElastiCache node type | `cache.t3.micro` |
| `redis_num_replicas` | Replica count | `0` (dev), `1` (prod) |

## Outputs
- **Destination:** Terraform outputs consumed by other modules:
  - `vpc_id`, `private_subnet_ids`, `public_subnet_ids`
  - `rds_endpoint`, `rds_port`, `rds_db_name`, `rds_credentials_secret_arn`
  - `redis_endpoint`, `redis_port`
  - `cloudformation_template_bucket_name`, `snapshot_payload_bucket_name`
  - `api_certificate_arn`
  - `route53_zone_id`

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
This module provisions the AWS infrastructure that backs all PostgreSQL tables used by the application. Specific tables owned by this infrastructure layer:

| Provisioned Resource | Backs Application Tables |
|---|---|
| RDS PostgreSQL instance | All application tables: `organizations`, `users`, `clusters`, `nodes`, `pods`, `assembled_snapshots`, `execution_history`, `audit_logs`, etc. |
| ElastiCache Redis | BullMQ job queues, Redis Streams event fallback, execution lock keys |
| S3 (`cloudformation_template_bucket`) | CloudFormation template delivery for onboarding |
| S3 (`snapshot_payload_bucket`) | Large snapshot payloads via `payload_ref` in `assembled_snapshots` |

## APIs
N/A — Infrastructure modules do not expose REST APIs.

## Dependencies
- **Terraform AWS provider** (`hashicorp/aws` ≥ 5.0)
- **Terraform** (≥ 1.5)
- **AWS account** with sufficient IAM permissions for resource provisioning
- **Root module** — provides environment variables and remote state configuration

## Configuration
All configuration is via Terraform variables. See Inputs table above. Additional:

| Variable | Description | Default |
|---|---|---|
| `enable_deletion_protection` | Enable RDS deletion protection | `false` (dev), `true` (prod) |
| `log_retention_days` | CloudWatch log retention | `30` |
| `tags` | AWS resource tags map | `{ Project = "balancekube", ManagedBy = "terraform" }` |

## Error Handling
- **RDS provisioning failure:** Terraform will destroy partially created resources and report the failure. Multi-AZ is only enabled in production to reduce cost in dev/staging while maintaining resilience where it matters.
- **ACM certificate validation timeout:** DNS validation must be complete within 30 minutes of certificate request; if the Route53 record is not propagated in time, Terraform times out. Resolution: re-run `terraform apply` once DNS propagation is confirmed.
- **NAT Gateway limit:** AWS account-level NAT Gateway limits may cause provisioning failures in new accounts; request a limit increase before applying in production.

## Future Enhancements
- Aurora Serverless v2 for RDS (auto-scaling, lower idle cost in dev).
- ElastiCache Redis cluster mode enabled for horizontal scaling in production.
- AWS Secrets Manager integration for database credentials rotation (currently credentials are stored in Secrets Manager but not auto-rotated).
- Multi-region active-passive failover using Route53 health checks and RDS cross-region read replica.
