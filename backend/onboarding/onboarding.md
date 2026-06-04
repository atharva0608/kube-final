# onboarding

## Purpose
The `onboarding` module handles the complete customer journey from first registration through to an Active cluster ready for data collection. It exists as a separate module because it is the only phase that requires external AWS API interaction (STS, EKS) during user-driven flows, and because its state machine (org → IAM → CloudFormation → validation → cluster discovery → registration → agent deploy) is complex enough to warrant isolation from the runtime pipeline.

## Responsibilities
- Create organization records and the initial admin user in a single atomic transaction
- Generate a cryptographically random `external_id` (UUID v4) per organization for IAM trust condition enforcement
- Generate a least-privilege CloudFormation template that provisions a cross-account IAM role with `sts:AssumeRole` trust to the BalanceKube platform account, conditioned on the `external_id`
- Upload the CloudFormation template to S3 and return a pre-signed URL (valid 1 hour) to the frontend
- Validate the IAM role by calling `sts:AssumeRole` from the platform account; cache the resulting credentials in Redis
- Discover all EKS clusters visible from the assumed role in the target AWS account
- Accept cluster selection from the operator; register the cluster row and issue a cluster registration token
- Generate Helm-based agent install instructions (values file + `helm install` command) for the operator to deploy into their cluster
- Track the per-cluster onboarding status through states: `PENDING_CF` → `PENDING_VALIDATION` → `PENDING_AGENT` → `ACTIVE`

## Inputs

### From Frontend (REST)
- **Source**: `POST /api/v1/orgs` — org name, admin email, password
- **Format**: `{ name: string, adminEmail: string, adminPassword: string, awsAccountId?: string }`

- **Source**: `POST /api/v1/orgs/:id/cloudformation` — triggers template generation
- **Format**: `{ awsAccountId: string, roleName?: string }`

- **Source**: `POST /api/v1/orgs/:id/validate-role` — operator confirms CF stack deployed
- **Format**: `{ roleArn: string }`

- **Source**: `GET /api/v1/orgs/:id/clusters/discover` — trigger EKS discovery
- **Format**: Query param `region` (optional, defaults to scanning all enabled regions)

- **Source**: `POST /api/v1/clusters` — register a discovered cluster
- **Format**: `{ orgId: string, clusterName: string, region: string, eksArn: string }`

- **Source**: `POST /api/v1/clusters/:id/select-cluster` — confirm selection
- **Format**: `{ clusterId: string }`

- **Source**: `GET /api/v1/clusters/:id/status` — poll onboarding progress
- **Format**: URL parameter only

### From AWS
- **Source**: `sts:AssumeRole` response — temporary credentials
- **Format**: AWS SDK `Credentials` object `{ accessKeyId, secretAccessKey, sessionToken, expiration }`

- **Source**: `eks:ListClusters` + `eks:DescribeCluster` — cluster discovery
- **Format**: AWS SDK EKS cluster descriptor objects

## Outputs

### API Responses
- **`POST /api/v1/orgs`** → `{ orgId, userId, membershipId }` — 201 Created
- **`POST /api/v1/orgs/:id/cloudformation`** → `{ templateUrl: string (pre-signed S3 URL), externalId: string, stackName: string }` — 200 OK
- **`POST /api/v1/orgs/:id/validate-role`** → `{ valid: boolean, accountId: string, discoveredRegions: string[] }` — 200 OK
- **`GET /api/v1/orgs/:id/clusters/discover`** → `{ clusters: [{ name, arn, region, version, status }] }` — 200 OK
- **`POST /api/v1/clusters`** → `{ clusterId, status: 'PENDING_AGENT' }` — 201 Created
- **`POST /api/v1/clusters/:id/select-cluster`** → `{ agentToken: string, helmValues: string (YAML), installCommand: string }` — 200 OK
- **`GET /api/v1/clusters/:id/status`** → `{ status, lastHeartbeat, agentVersion, nodeCount }` — 200 OK

### Database Writes
- `organizations` — new row on org creation
- `users` — admin user row on org creation
- `memberships` — org-user join with role=`ADMIN`
- `cloudformation_stacks` — stack name, external_id, role ARN, status
- `clusters` — cluster row with `org_id`, EKS ARN, region, status
- `cluster_tokens` — short-lived bearer token for the agent

### Events Published
- **`org.created`** — `{ orgId, adminUserId, createdAt }` — after org commit
- **`cluster.registered`** — `{ clusterId, orgId, region, registeredAt }` — after cluster row commit

### Redis Writes
- Key: `sts:creds:{orgId}` — value: `{ accessKeyId, secretAccessKey, sessionToken }` — TTL: `credential.expiration - 60s`

## Events Produced
| Event | Description |
|---|---|
| `org.created` | Fired immediately after the organization and admin user rows are committed to PostgreSQL |
| `cluster.registered` | Fired immediately after a cluster row is committed and a cluster token is issued |

## Events Consumed
N/A — the onboarding module is purely request-driven; it does not subscribe to any upstream events.

## Database Tables

### Tables Owned (Written)
| Table | Key Columns | Notes |
|---|---|---|
| `organizations` | `id (UUID PK)`, `name`, `aws_account_id`, `external_id`, `plan`, `status`, `created_at` | `external_id` is UUID v4, generated once, immutable |
| `users` | `id (UUID PK)`, `email`, `password_hash`, `created_at` | Passwords hashed with bcrypt, cost factor 12 |
| `memberships` | `org_id (FK)`, `user_id (FK)`, `role` | role enum: `ADMIN` / `MEMBER` / `VIEWER` |
| `cloudformation_stacks` | `id (UUID PK)`, `org_id (FK)`, `stack_name`, `external_id`, `role_arn`, `status`, `template_s3_key`, `created_at` | `status`: `PENDING` / `DEPLOYED` / `VALIDATED` / `FAILED` |
| `clusters` | `id (UUID PK)`, `org_id (FK)`, `name`, `eks_arn`, `region`, `status`, `registered_at` | `status`: `PENDING_CF` / `PENDING_VALIDATION` / `PENDING_AGENT` / `ACTIVE` |
| `cluster_tokens` | `id (UUID PK)`, `cluster_id (FK)`, `token_hash`, `expires_at`, `revoked_at` | Token value is returned once; only hash stored |

### Tables Read (Cross-Domain, Read-Only)
| Table | Purpose |
|---|---|
| `agents` | Check if an agent has registered against a cluster after token issuance, to determine `ACTIVE` status |

## APIs
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/orgs` | Create org + admin user. Returns orgId and userId. Idempotent on email — returns 409 if email already registered. |
| `GET` | `/api/v1/orgs/:id` | Get organization details including CF stack status. Requires org membership. |
| `POST` | `/api/v1/orgs/:id/cloudformation` | Generate CloudFormation YAML template with minimal IAM permissions and ExternalId condition. Upload to S3. Return pre-signed URL valid for 1 hour. |
| `POST` | `/api/v1/orgs/:id/validate-role` | Attempt `sts:AssumeRole` with the provided role ARN. On success, store credentials in Redis and return account confirmation. |
| `GET` | `/api/v1/orgs/:id/clusters/discover` | List EKS clusters using cached STS credentials. Scans all enabled AWS regions unless `region` query param is provided. |
| `POST` | `/api/v1/clusters` | Register a cluster. Creates cluster row, advances status to `PENDING_AGENT`. |
| `POST` | `/api/v1/clusters/:id/select-cluster` | Confirm cluster selection. Generates agent bearer token, writes to `cluster_tokens`. Returns Helm values YAML and install command. |
| `GET` | `/api/v1/clusters/:id/status` | Returns current onboarding status, last agent heartbeat timestamp, agent version if available, and node count if `ACTIVE`. |

## Dependencies

### Internal Modules
| Module | Usage |
|---|---|
| `common/auth` | JWT verification middleware on protected routes |
| `common/errors` | Structured error classes (e.g., `AwsRoleAssumptionError`, `ClusterAlreadyRegisteredError`) |
| `common/logger` | Structured JSON logging with correlation IDs |
| `database` | PostgreSQL pool, transaction helpers |
| `events` | NATS publisher for `org.created` and `cluster.registered` |
| `notifications` | Create welcome notification after org creation |

### External Services
| Service | SDK / Method | Purpose |
|---|---|---|
| AWS STS | `@aws-sdk/client-sts` `AssumeRoleCommand` | Validate the cross-account IAM role |
| AWS EKS | `@aws-sdk/client-eks` `ListClustersCommand`, `DescribeClusterCommand` | Discover EKS clusters in target account |
| AWS S3 | `@aws-sdk/client-s3` `PutObjectCommand`, `getSignedUrl` | Upload CF template; generate pre-signed download URL |
| Redis | `ioredis` | Cache STS credentials with TTL |

### CloudFormation Template — IAM Permissions Granted
The generated CF template provisions an IAM Role with the following minimum permissions:
```
ec2:DescribeInstances
ec2:DescribeSpotInstanceRequests
ec2:DescribeRegions
ec2:DescribeSpotPriceHistory
ec2:DescribeInstanceTypes
eks:ListClusters
eks:DescribeCluster
sts:GetCallerIdentity
```
The trust policy conditions on:
```json
{
  "StringEquals": {
    "sts:ExternalId": "<org.external_id>"
  }
}
```

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `AWS_PLATFORM_ACCOUNT_ID` | — | BalanceKube platform AWS account ID (required for trust policy) |
| `AWS_PLATFORM_ROLE_ARN` | — | ARN of the platform role that assumes customer roles |
| `S3_CF_BUCKET` | — | S3 bucket for CloudFormation template uploads |
| `CF_TEMPLATE_PRESIGN_TTL` | `3600` | Pre-signed URL expiry in seconds (1 hour) |
| `STS_CRED_REDIS_TTL_BUFFER` | `60` | Seconds before credential expiry to evict from Redis cache |
| `CLUSTER_TOKEN_TTL_HOURS` | `720` | Agent token validity in hours (30 days default) |
| `EKS_DISCOVERY_REGIONS` | all enabled regions | Comma-separated region list to scan during discovery |
| `BCRYPT_COST_FACTOR` | `12` | bcrypt cost factor for password hashing |

## Error Handling

| Scenario | Behavior |
|---|---|
| `sts:AssumeRole` fails | Return `{ valid: false, error: 'AWS_ROLE_ASSUMPTION_FAILED', detail: string }` to frontend; do not retry automatically — user must fix IAM policy |
| EKS discovery returns empty | Return empty cluster array with `{ warning: 'NO_CLUSTERS_FOUND' }`; not an error |
| S3 upload fails | Retry 3× with exponential backoff (100ms base). On persistent failure return `500` with `CF_TEMPLATE_UPLOAD_FAILED` |
| Duplicate org email | Return `409 Conflict` with `EMAIL_ALREADY_REGISTERED` |
| Redis unavailable for STS cache | Fall through — re-call STS on next request (no caching, higher latency but functional) |
| Cluster already registered | Return `409 Conflict` with `CLUSTER_ALREADY_REGISTERED` |
| DB transaction failure | Rollback all writes atomically; return `500` with correlation ID for support |

## Future Enhancements
- **Multi-AWS-account support per org**: Allow an org to register multiple AWS accounts (payer + linked accounts) with a single IAM role per account
- **GCP / Azure onboarding**: Extend the CloudFormation pattern to GCP Service Account JSON and Azure Managed Identity for multi-cloud support
- **Self-service role validation UI polling**: Replace manual "I've deployed the stack" confirmation with SNS/EventBridge webhook from CloudFormation stack events
- **SAML/OIDC SSO**: Replace local password auth for enterprise customers with SAML or OIDC-based single sign-on during org creation
- **Automated CF stack deployment**: Use the AWS CloudFormation API to deploy the stack directly from BalanceKube, eliminating the manual deploy step
