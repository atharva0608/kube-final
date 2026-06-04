# Infrastructure: Database

## Purpose
PostgreSQL cluster provisioning and configuration.

## Responsibilities
- Provisions AWS RDS for PostgreSQL.
- Configures Multi-AZ deployments for high availability in production.
- Sets automated backup retention policies and maintenance windows.
- Manages security groups allowing traffic only from the EKS cluster.

## Inputs
- Source: IaC.
- Format: HCL.

## Outputs
- Destination: AWS RDS.
- Format: Relational database cluster.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- AWS RDS.

## Configuration
- RDS instance size based on environment variables.

## Error Handling
- Automated failover handled natively by RDS Multi-AZ.

## Future Enhancements
- Aurora Serverless v2 for cost optimization in non-prod environments.
