# Infrastructure

## Purpose
Root infrastructure documentation. The BalanceKube platform is deployed as a cloud-native application on AWS, utilizing EKS, RDS, and ElastiCache. This module defines the Infrastructure as Code (IaC) and deployment manifests.

## Responsibilities
- Provisions the underlying AWS resources (VPC, EKS, RDS, ElastiCache, MSK/NATS).
- Manages Kubernetes application deployment manifests (Helm/Kustomize).
- Defines CI/CD pipelines for building and deploying the platform.
- Provisions monitoring, secret management, and networking configurations.

## Inputs
- Source: Developer commits, environment variable overrides.
- Format: Terraform HCL, Kubernetes YAML, GitHub Actions YAML.

## Outputs
- Destination: AWS, Kubernetes API.
- Format: Live infrastructure resources.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A (Provisions the database server itself).

## APIs
- N/A

## Dependencies
- Terraform, Helm, Docker, AWS CLI.

## Configuration
- Configured per environment (dev, staging, prod) via Terraform `tfvars`.

## Error Handling
- Terraform state locking via DynamoDB.
- Helm atomic rollbacks on failed deployments.

## Future Enhancements
- Cross-region disaster recovery replication.
