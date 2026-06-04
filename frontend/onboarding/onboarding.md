# onboarding

## Purpose
The onboarding module provides the multi-step wizard UI that guides a new operator through the full BalanceKube account and cluster registration flow. It is a separate feature area because the onboarding UX is fundamentally different from the operational dashboard—it is a linear, stateful wizard rather than a tabbed data browser, and it is the only entry point that a new user will ever see before any cluster data exists.

## Responsibilities
- Render an 8-step wizard that takes the operator from account creation through to a live, agent-connected cluster.
- Step 1: Account creation form (org name, email, password) — calls `POST /orgs`.
- Step 2: CloudFormation template delivery — presents a "Deploy to AWS" deep-link that opens the AWS Console with the CloudFormation template URL pre-filled, and a download button for the YAML template — calls `POST /orgs/:id/cloudformation` to obtain the pre-signed template URL.
- Step 3: ARN paste input — accepts the IAM Role ARN output from the CloudFormation stack with client-side format validation before submission.
- Step 4: Role validation result display — calls `POST /orgs/:id/validate-role` and shows specific, actionable error messages on failure (e.g., wrong ExternalId, missing permissions, ARN not found).
- Step 5: EKS cluster discovery — lists all EKS clusters found in the validated AWS account — calls `GET /orgs/:id/clusters/discover`.
- Step 6: Cluster selection — operator selects one or more clusters from the discovered list.
- Step 7: Agent installation — shows a pre-built `kubectl` / Helm install command with the registration token embedded; one-click copy to clipboard. Calls `POST /clusters` and `POST /clusters/:id/select-cluster`.
- Step 8: Cluster active confirmation — polls `GET /clusters/:id/status` every 15–30 seconds and transitions to the dashboard once agent reports `active`.
- Display real-time connection feedback during the polling phase (spinner, heartbeat icon, elapsed time).
- Persist wizard step in component state (not URL) to prevent direct linking into intermediate steps.

## Inputs
- **Source:** Operator form inputs (org name, email, password, IAM Role ARN, cluster selection)
- **Format:** Validated with Zod schemas from `frontend/shared/validation` before any API call
- **Source:** `POST /orgs` response — `{ org_id, name }` — to anchor subsequent wizard steps to the new org
- **Source:** `POST /orgs/:id/cloudformation` response — `{ template_url: string (pre-signed S3 URL), deploy_to_aws_url: string }`
- **Source:** `POST /orgs/:id/validate-role` response — `{ valid: boolean, error_code?: string, error_message?: string }`
- **Source:** `GET /orgs/:id/clusters/discover` response — `{ clusters: Array<{ cluster_name, arn, region, kubernetes_version }> }`
- **Source:** `POST /clusters` response — `{ cluster_id, registration_token, helm_install_command }`
- **Source:** `GET /clusters/:id/status` response — `{ status: 'pending' | 'active' | 'error', agent_connected: boolean }`

## Outputs
- **Destination:** `POST /orgs` — creates organisation record
- **Destination:** `POST /orgs/:id/cloudformation` — triggers template generation and returns pre-signed URL
- **Destination:** `POST /orgs/:id/validate-role` — submits ARN for cross-account role validation
- **Destination:** `GET /orgs/:id/clusters/discover` — fetches discovered EKS clusters
- **Destination:** `POST /clusters` — registers selected cluster(s) and returns registration token
- **Destination:** `POST /clusters/:id/select-cluster` — confirms cluster selection
- **Destination:** `GET /clusters/:id/status` — polled every 15–30 s to detect agent connection
- **Format:** All request bodies are JSON; all responses parsed via Zod schemas

## Events Produced
N/A — Frontend does not produce domain events.

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access.

## APIs
Backend endpoints called by this module:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/orgs` | Create organisation account (Step 1) |
| `POST` | `/orgs/:id/cloudformation` | Generate CloudFormation template pre-signed URL (Step 2) |
| `POST` | `/orgs/:id/validate-role` | Validate pasted IAM Role ARN (Step 4) |
| `GET` | `/orgs/:id/clusters/discover` | List discovered EKS clusters in the AWS account (Step 5) |
| `POST` | `/clusters` | Register selected cluster and obtain registration token (Step 6–7) |
| `POST` | `/clusters/:id/select-cluster` | Confirm cluster selection (Step 6) |
| `GET` | `/clusters/:id/status` | Poll cluster/agent connection status (Step 8) |

## Dependencies
- **`frontend/shared/api`** — API client for all HTTP calls
- **`frontend/shared/validation`** — Zod schemas for ARN format, email, password strength, and API response parsing
- **`frontend/shared` components** — `Spinner`, `Toast`, `Modal`, `StatusBadge`
- **React Router** — Navigation guard to prevent skipping wizard steps
- **Clipboard API** — One-click copy of Helm install command in Step 7

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:3000` |
| `VITE_POLLING_INTERVAL_MS` | Agent connection polling interval (Step 8) | `15000` |
| `VITE_POLLING_MAX_ATTEMPTS` | Max polling attempts before showing a timeout message | `40` (~10 min) |

## Error Handling
- **ARN format validation:** Client-side Zod check before submitting to `validate-role` endpoint; prevents unnecessary API round trips for obviously malformed ARNs.
- **Role validation failure (Step 4):** Displays error code–specific messages (e.g., `INVALID_EXTERNAL_ID` → "The ExternalId condition in your IAM role trust policy does not match. Re-download the CloudFormation template and redeploy.").
- **Cluster discovery empty list:** Shows an informational message explaining that no EKS clusters were found and prompts the operator to verify the AWS region or IAM permissions.
- **Agent connection timeout:** After `VITE_POLLING_MAX_ATTEMPTS` polling cycles without an `active` status, the wizard shows a troubleshooting guide (check `kubectl get pods -n balancekube`, verify network egress to BalanceKube API).
- **Network errors during wizard:** Each step shows a retry button; wizard state is preserved in component memory so the operator does not lose progress on transient failures.

## Future Enhancements
- Support multi-cluster registration in a single onboarding flow (select multiple clusters in Step 6).
- Webhook-based agent connection notification (replace polling with push notification for faster UX).
- SAML/SSO account creation path as an alternative to email/password Step 1.
- Progress persistence in `sessionStorage` so a browser refresh does not restart the wizard.
