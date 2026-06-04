# agent_management

## Purpose
Manages the full lifecycle of the BalanceKube in-cluster Go agent: registration, mTLS credential issuance, heartbeat monitoring, upgrade orchestration, and token/certificate rotation. Acts as the control plane for all agent communication, ensuring that only authenticated, up-to-date agents can interact with the platform and that connectivity loss is detected and escalated promptly.

## Responsibilities
- Validate agent registration tokens against `cluster_tokens` (SHA-256 hash comparison) and issue mTLS client certificates signed by the platform CA (30-day validity).
- Return cluster configuration to the agent on registration: snapshot collection interval, backend API version, and feature flags.
- Track agent state through the full lifecycle: `unregistered → registered → active → degraded → unreachable`, with recovery path `unreachable → active` and upgrade path `active → upgrading → active` (or rollback on failure).
- Process heartbeat payloads every 30 seconds, recording `agent_version`, `cluster_id`, `collection_cycle_count`, `last_error`, and `node_count`.
- Apply heartbeat thresholds: missed for 90 seconds (3 × interval) → emit `agent.heartbeat_missed` event; 10 minutes → degrade cluster status; 30 minutes → mark cluster status `unreachable`.
- Orchestrate agent upgrades: provide signed download URLs for new binaries, verify SHA-256 checksums, and track upgrade progress via Kubernetes rolling update.
- Manage **token and certificate rotation**: accept agent-initiated rotation requests 7 days before certificate expiry, issue new certificates signed by the platform CA, support dual-cert operation during the transition window, and retire old certificates on confirmed switchover.
- Store only the SHA-256 hash of registration tokens in the database; plaintext shown once to the operator at generation time, never retrievable again.

## Inputs
- **Source:** `POST /api/v1/agents/register` — agent registration request with `token` (plaintext, verified via hash comparison against `cluster_tokens.token_hash`), `agent_version`, `cluster_id`.
- **Source:** `POST /api/v1/agents/:id/heartbeat` — periodic heartbeat payload: `{ agent_version, cluster_id, collection_cycle_count, last_error, node_count }`. The HTTP 200 response serves as the asynchronous instruction delivery mechanism for the agent (e.g. to push execution plans with ~30-second polling latency).
- **Source:** `POST /api/v1/agents/:id/rotate-token` — agent-initiated rotation request, authenticated with the current valid mTLS certificate.
- **Source:** `GET /api/v1/agents/:id/upgrade` — agent polls for upgrade availability; receives signed binary URL and checksum.
- **Source:** `DELETE /clusters/:id/agent` — operator-initiated agent uninstall.
- **Format:** All API inputs are JSON over HTTPS (mTLS required for all endpoints except initial registration).

## Outputs
- **Destination:** `agents` table — updated on every state transition and heartbeat.
- **Destination:** `agent_tokens` table — new row on rotation; old row updated with `rotated_at`.
- **Destination:** Agent — mTLS client certificate (PEM) returned on registration and rotation.
- **Destination:** NATS topics `agent.heartbeat_missed`, `agent.token_rotated`.
- **Format:**
  ```json
  {
    "event": "agent.heartbeat_missed",
    "cluster_id": "uuid",
    "agent_id": "uuid",
    "last_heartbeat_at": "2024-06-04T07:55:00Z",
    "missed_for_seconds": 95
  }
  ```

## Events Produced
| Event | Description |
|---|---|
| `agent.heartbeat_missed` | Emitted when an agent misses 3 consecutive heartbeats (90 seconds). Payload: `cluster_id`, `agent_id`, `last_heartbeat_at`, `missed_for_seconds`. |
| `agent.token_rotated` | Emitted when a certificate rotation is confirmed (agent sends first heartbeat with new cert). Payload: `cluster_id`, `agent_id`, `rotated_at`, `new_expires_at`. |

## Events Consumed
- **N/A** — Agent management is API-driven and schedule-driven. It does not subscribe to NATS events.

## Database Tables

**Tables this module owns (writes to):**
| Table | Description |
|---|---|
| `agents` | One row per registered agent. Columns: `id` (UUID), `cluster_id` (FK → `clusters`), `version` (semver string), `last_heartbeat_at` (timestamp), `status` (ENUM: `unregistered`, `registered`, `active`, `degraded`, `unreachable`, `upgrading`), `collection_cycle_count` (bigint), `node_count`, `last_error` (text). |
| `agent_tokens` | Tracks certificate/token lifecycle. Columns: `id` (UUID), `agent_id` (FK), `token_hash` (SHA-256 hex string), `expires_at`, `rotated_at` (nullable — set when superseded). |

**Tables this module reads (read-only):**
| Table | Source Domain |
|---|---|
| `cluster_tokens` | Onboarding — used to validate initial registration token hash. |
| `clusters` | Onboarding — used to verify `cluster_id` exists and is in valid state. |

## APIs
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/agents/register` | Register a new agent. Validates token hash, issues mTLS certificate, returns cluster configuration. Returns `{ agent_id, certificate_pem, ca_pem, config: { snapshot_interval_seconds, api_version, feature_flags } }`. |
| `POST` | `/api/v1/agents/:id/heartbeat` | Accept a heartbeat payload. Updates `agents.last_heartbeat_at`, resets missed-heartbeat counter, updates `version`, `node_count`, `last_error`. Returns HTTP 200 on success with optional instruction payload (`{ instructions: [...] }`). |
| `GET` | `/api/v1/agents/:id/upgrade` | Return upgrade availability. Response: `{ upgrade_available: boolean, new_version?, download_url?, sha256_checksum? }`. Download URL is time-limited (15 minutes) and platform-signed. |
| `POST` | `/api/v1/agents/:id/rotate-token` | Initiate certificate rotation. Returns new certificate PEM. Agent continues using old certificate until it sends a heartbeat authenticated with the new one. |
| `DELETE` | `/clusters/:id/agent` | Mark agent as unregistered and invalidate all associated tokens. Used during cluster offboarding. |

## Agent State Machine
```
unregistered
    │
    ▼ POST /api/v1/agents/register
registered
    │
    ▼ First heartbeat received
active ◄──────────────────────────────────┐
    │                                     │
    ▼ 90s no heartbeat                    │ Heartbeat restored
degraded ─────────────────────────────────┘
    │
    ▼ 10 min no heartbeat
[cluster status: degraded]
    │
    ▼ 30 min no heartbeat
unreachable
    │
    ▼ Heartbeat restored
active

active ─► upgrading ─► active (success)
                   └─► rollback (binary verification fail)
```

## Certificate Rotation Sequence
1. Agent detects its certificate will expire in ≤ 7 days and calls `POST /api/v1/agents/:id/rotate-token`.
2. Platform CA issues a new client certificate (30-day validity) and returns it as PEM.
3. Agent stores the new certificate alongside the old one.
4. Agent continues sending heartbeats authenticated with the **old** certificate during the transition window.
5. Agent sends one heartbeat authenticated with the **new** certificate to confirm successful storage.
6. Platform retires the old certificate: sets `agent_tokens.rotated_at` to the current timestamp.
7. Platform emits `agent.token_rotated` event.

## Token Security Model
- Registration token plaintext is generated by the platform at cluster onboarding time and shown **once** to the operator in the UI. It is never stored in plaintext and is never retrievable again.
- The database stores only the SHA-256 hash in `agent_tokens.token_hash` (and `cluster_tokens.token_hash`).
- mTLS client certificates issued post-registration replace token-based auth for all subsequent communication.
- Certificates are signed by a platform-internal CA; the CA public key is provided to the agent at registration and used to verify all future responses from the platform.

## Dependencies
- **onboarding** module — reads `cluster_tokens` for initial registration validation and `clusters` for cluster existence checks.
- **Platform CA** — internal certificate authority for signing mTLS client certificates. Managed as a separate internal service; private key never leaves the signing service.
- **BullMQ** — periodic heartbeat-monitoring job that checks `agents.last_heartbeat_at` against current time and emits `agent.heartbeat_missed` when thresholds are breached.
- **NATS** — for publishing `agent.heartbeat_missed` and `agent.token_rotated` events.
- **shared/db** — PostgreSQL client; all agent state transitions are serialised via `SELECT FOR UPDATE`.
- **shared/logger** — structured logging with `agent_id`, `cluster_id`, `agent_version` context.

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `AGENT_HEARTBEAT_INTERVAL_SECONDS` | `30` | Expected heartbeat interval. Used to compute missed-heartbeat thresholds. |
| `AGENT_HEARTBEAT_MISSED_THRESHOLD` | `3` | Number of missed intervals before `agent.heartbeat_missed` is emitted (3 × 30s = 90s). |
| `AGENT_DEGRADE_THRESHOLD_MINUTES` | `10` | Minutes without heartbeat before cluster status is set to `degraded`. |
| `AGENT_UNREACHABLE_THRESHOLD_MINUTES` | `30` | Minutes without heartbeat before cluster status is set to `unreachable`. |
| `AGENT_CERT_VALIDITY_DAYS` | `30` | Validity period for issued mTLS client certificates. |
| `AGENT_CERT_ROTATION_LEAD_DAYS` | `7` | Days before expiry at which agent initiates rotation. |
| `AGENT_UPGRADE_URL_TTL_MINUTES` | `15` | Time-to-live for signed upgrade binary download URLs. |
| `AGENT_HEARTBEAT_MONITOR_INTERVAL_SECONDS` | `30` | How often the BullMQ heartbeat monitor job runs its check. |
| `PLATFORM_CA_SIGN_ENDPOINT` | *(required)* | Internal URL of the platform CA signing service. No default. |

## Error Handling
- **Invalid registration token:** Returns HTTP 401. Does not reveal whether the token exists but is expired vs. was never valid — identical error response to prevent enumeration.
- **Duplicate registration:** If an `agents` row already exists for the `cluster_id` with `status != unregistered`, registration is rejected with HTTP 409 until the existing agent is explicitly unregistered via `DELETE /clusters/:id/agent`.
- **Heartbeat from unknown agent:** Returns HTTP 404. The agent must re-register.
- **Heartbeat monitor job failure:** The BullMQ job uses at-least-once delivery; duplicate heartbeat checks are idempotent (they re-read `last_heartbeat_at` from the database each run). Failures are retried 3 times with 10s backoff before dead-lettering.
- **Certificate rotation failure (CA unavailable):** Returns HTTP 503. Agent retries rotation on next collection cycle. The existing certificate remains valid during this window; no disruption to heartbeats.
- **Upgrade binary verification failure:** Agent reports failure via next heartbeat's `last_error` field. Platform transitions agent status to `active` (rollback) and flags the upgrade as failed in the operator UI.

## Future Enhancements
- **Agent fleet view:** API endpoint that returns a summary of all agents across all clusters in an organization, with status, version, and last heartbeat.
- **Automatic upgrade scheduling:** Allow operators to configure a maintenance window during which agent upgrades are automatically applied without manual trigger.
- **Certificate pinning enforcement:** Reject heartbeats from agents using certificates signed by a revoked or expired intermediate CA, even if the certificate itself has not yet expired.
- **Agent resource usage reporting:** Extend the heartbeat payload to include agent CPU and memory consumption on the cluster, surfaced in the UI for observability.
- **mTLS certificate revocation (CRL/OCSP):** Implement certificate revocation list or OCSP stapling for immediate invalidation of compromised agent certificates without waiting for expiry.
