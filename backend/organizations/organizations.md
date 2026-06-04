# organizations

## Purpose
Manages the top-level tenant entity in the BalanceKube multi-tenant architecture. Every cluster, user, recommendation, and audit record is scoped to an organization. This module is the authoritative source for organization identity, AWS account linkage, and the platform-wide execution mode gate (`karpenter_control_mode`) that must be explicitly unlocked before Phase 4 can provision NodeClaims.

## Responsibilities
- Create and persist organization records with a UUID primary key (never integer, to prevent enumeration attacks).
- Generate and store a cryptographically random `external_id` used as the AWS IAM `ExternalId` condition in cross-account role assumption — prevents confused deputy attacks.
- Store the AWS cross-account role ARN encrypted at rest using AES-256-GCM; decrypt only when needed for AWS API calls.
- Default `karpenter_control_mode` to `'observe'` on creation; require an explicit `PATCH` by an `admin` to change to `'managed'` before Phase 4 can create Karpenter NodeClaims.
- Publish `org.created` event after a new organization is persisted, triggering downstream onboarding workers.
- Expose read and update APIs for organization settings, with field-level validation (e.g., `aws_role_arn` format, `karpenter_control_mode` enum).

## Inputs
- **Source:** `POST /orgs` — organization creation payload: `{ name, aws_role_arn, aws_account_id, region }`.
- **Source:** `PATCH /orgs/:id` — update payload with any subset of: `{ name, aws_role_arn, aws_account_id, region, karpenter_control_mode }`.
- **Source:** `GET /orgs/:id` — authenticated read request scoped to the caller's `org_id`.
- **Format:** JSON over HTTPS; `aws_role_arn` validated against the regex `^arn:aws:iam::\d{12}:role\/.+$` before acceptance.

## Outputs
- **Destination:** `organizations` table — one row per organization.
- **Destination:** NATS topic `org.created` — published immediately after the `organizations` row is committed.
- **Destination:** API responses — organization record (with `aws_role_arn_encrypted` never returned; instead, a masked form is returned: `arn:aws:iam::123456789012:role/***`).
- **Format:**
  ```json
  {
    "event": "org.created",
    "org_id": "uuid",
    "name": "Acme Corp",
    "external_id": "random-uuid-used-as-externalid"
  }
  ```

## Events Produced
| Event | Description |
|---|---|
| `org.created` | Published after a new organization is persisted. Payload: `{ org_id, name, external_id }`. Consumed by `workers/onboarding` to bootstrap initial infrastructure (CloudFormation stack, IAM validation). |

## Events Consumed
- **N/A** — The organizations module is API-driven. It does not subscribe to any NATS events.

## Database Tables

**Tables this module owns (writes to):**
| Table | Description |
|---|---|
| `organizations` | One row per tenant organization. Columns: `id` (UUID, PK — never integer), `name` (text), `external_id` (UUID — AWS ExternalId condition for cross-account role assumption), `aws_role_arn_encrypted` (bytea — AES-256-GCM encrypted), `aws_account_id` (12-digit string), `region` (AWS region string), `karpenter_control_mode` (ENUM: `observe`, `managed`, default: `observe`), `created_at`. |

**Tables this module reads (read-only):**
- None. Organizations is a root-level module with no upstream data dependencies.

## APIs
| Method | Path | Description |
|---|---|---|
| `POST` | `/orgs` | Create a new organization. Generates `external_id` (random UUID), encrypts `aws_role_arn` with AES-256-GCM, persists record, publishes `org.created`. Requires platform-level or initial registration context (called once per onboarding flow). |
| `GET` | `/orgs/:id` | Retrieve organization details. Returns all fields except `aws_role_arn_encrypted` — instead returns a masked ARN. Scoped to authenticated user's `org_id` (cannot read another org's record). |
| `PATCH` | `/orgs/:id` | Update organization settings. All fields are optional. Changing `karpenter_control_mode` from `observe` to `managed` requires `admin` role and triggers a confirmation step in the UI (two-step acknowledgment). |

## karpenter_control_mode Gate
The `karpenter_control_mode` field is the platform's primary safety gate for Phase 4 execution:

| Value | Effect |
|---|---|
| `observe` | Default. BalanceKube can analyse, recommend, and simulate but **cannot** create Karpenter `NodeClaim` objects. Phase 4 steps of type `CREATE_KARPENTER_NODECLAIM` are skipped; the execution plan assumes nodes are pre-provisioned. |
| `managed` | BalanceKube can create and manage `NodeClaim` objects in the cluster. Phase 4 will provision Spot nodes automatically. **Requires explicit admin action to set.** |

Setting `karpenter_control_mode = 'managed'` is logged as a high-priority `audit_logs` entry with `before` and `after` snapshots.

## AWS ExternalId Design
The `external_id` field is a randomly-generated UUID stored in `organizations.external_id`. It is provided to customers during onboarding to include in their IAM trust policy as the `ExternalId` condition:

```json
{
  "Condition": {
    "StringEquals": {
      "sts:ExternalId": "<external_id>"
    }
  }
}
```

This prevents the confused deputy problem: even if an attacker discovers the platform's AWS account ID, they cannot assume the customer's cross-account role without also knowing the unique `external_id`.

## AWS Role ARN Encryption
- `aws_role_arn` is encrypted using AES-256-GCM before being stored in `aws_role_arn_encrypted` (bytea column).
- The encryption key is stored in the platform's secrets manager (AWS Secrets Manager or HashiCorp Vault), not in the database.
- Decryption occurs only when the platform needs to call `sts:AssumeRole` — the plaintext ARN is never persisted in logs or returned in API responses.
- The masked form returned by the API: `arn:aws:iam::123456789012:role/***` (role name replaced with asterisks).

## Dependencies
- **NATS** — for publishing `org.created`; falls back to Redis Streams if NATS is unavailable.
- **AWS Secrets Manager / Vault** — for the AES-256-GCM encryption key used to encrypt `aws_role_arn`.
- **shared/db** — PostgreSQL client; organization creation is transactional (row insert + event publish in the same logical unit using the outbox pattern).
- **shared/crypto** — AES-256-GCM encrypt/decrypt utilities.
- **shared/logger** — structured logging with `org_id` context; never logs `aws_role_arn` plaintext.

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `ORG_ARN_ENCRYPTION_KEY_ID` | *(required)* | Secrets Manager or Vault key ID used for AES-256-GCM encryption of `aws_role_arn`. No default. |
| `NATS_ORG_CREATED_TOPIC` | `org.created` | NATS topic on which `org.created` is published. |
| `KARPENTER_CONTROL_MODE_DEFAULT` | `observe` | Default value for `karpenter_control_mode` on organization creation. Should not be changed in production. |
| `ORG_ID_FORMAT` | `uuid` | Primary key format for `organizations.id`. Always UUID; configuration exists for documentation purposes. |

## Error Handling
- **Duplicate organization name:** Organization names are not enforced as unique at the database level (same company can have multiple orgs for different environments). No uniqueness constraint on `name`.
- **Invalid `aws_role_arn` format:** Returns HTTP 400 with `code: "INVALID_ROLE_ARN"` and a descriptive message before any database write occurs.
- **Encryption key unavailable:** If the AES-256-GCM key cannot be retrieved from Secrets Manager, organization creation is aborted and returns HTTP 503. The error is logged with `org_id` context but without the plaintext ARN.
- **`org.created` publish failure:** Uses the transactional outbox pattern — the event payload is written to `event_store` within the same database transaction as the `organizations` insert. A background worker reliably delivers it to NATS. The HTTP response to the client returns 201 immediately after the database commit.
- **Unauthorized `karpenter_control_mode` change:** Returns HTTP 403 if a non-admin user attempts to change `karpenter_control_mode`. Returns HTTP 400 if an invalid value is submitted.
- **Cross-org access attempt:** The `GET /orgs/:id` endpoint compares the `:id` path parameter against the authenticated user's `org_id` claim from the JWT. A mismatch returns HTTP 403 (not 404) to avoid information leakage.

## Future Enhancements
- **Multi-region support:** Allow an organization to have multiple AWS regions, each with its own `aws_role_arn` and cluster set, managed under a single org record.
- **Organization tiers:** Add a `subscription_tier` field (`free`, `pro`, `enterprise`) to gate feature availability (e.g., `managed` karpenter mode restricted to `pro`+).
- **Organization deletion:** Implement a soft-delete flow with a 30-day retention window before permanent deletion, including cascade invalidation of all clusters, agents, and tokens.
- **IAM role validation on save:** When `aws_role_arn` is saved or updated, asynchronously attempt `sts:AssumeRole` to validate that the role is correctly configured before the operator proceeds to cluster registration.
- **Audit on ARN changes:** Any change to `aws_role_arn` should trigger an immediate re-validation of all clusters in the organization to detect permission drift.
