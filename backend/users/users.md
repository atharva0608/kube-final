# users

## Purpose
Manages user identity, authentication, and organization membership within the BalanceKube multi-tenant platform. Enforces role-based access control (RBAC) so that every API call is scoped to the authenticated user's organization and role. Acts as the identity boundary that all other backend modules depend on for authorization context.

## Responsibilities
- Register new users and associate them with exactly one organization.
- Authenticate users via email/password, issuing RS256 JWT access tokens (1-hour TTL) and refresh tokens (30-day TTL).
- Validate and refresh JWT tokens for subsequent requests.
- Manage **API keys** for programmatic access: generate, list, and revoke. Store only the SHA-256 hash; plaintext shown once at creation.
- Enforce **RBAC roles**: `admin` (full access), `operator` (can approve recommendations and trigger execution), `viewer` (read-only).
- Scope all database queries to the authenticated user's `org_id` — no cross-organization data access is possible at the application layer.
- Apply **row-level security (RLS)** on all org-scoped tables as a defence-in-depth guarantee at the PostgreSQL layer.
- Expose profile management endpoints for users to read and update their own profile.

## Inputs
- **Source:** `POST /auth/register` — registration payload: `{ email, password, org_id, role? }`.
- **Source:** `POST /auth/login` — login payload: `{ email, password }`.
- **Source:** `POST /auth/refresh` — refresh payload: `{ refresh_token }`.
- **Source:** `POST /api-keys` — API key creation payload: `{ name }`.
- **Source:** Bearer token or API key header on all protected endpoints.
- **Format:** JSON over HTTPS; passwords hashed with bcrypt (cost factor 12) before storage.

## Outputs
- **Destination:** `users` table — new row on registration.
- **Destination:** `memberships` table — new row on registration associating user with organization.
- **Destination:** `api_keys` table — new row on API key creation.
- **Destination:** API responses — JWT access token, refresh token, user profile, API key list.
- **Format:**
  ```json
  {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "expires_in": 3600,
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "role": "operator",
      "org_id": "uuid"
    }
  }
  ```

## Events Produced
- **N/A** — The users module does not emit NATS events. User creation does not emit `user.created` — downstream onboarding is triggered via `org.created` (owned by the `organizations` module).

## Events Consumed
- **N/A** — The users module is entirely API-driven.

## Database Tables

**Tables this module owns (writes to):**
| Table | Description |
|---|---|
| `users` | One row per user. Columns: `id` (UUID), `org_id` (FK → `organizations`), `email` (unique), `role` (ENUM: `admin`, `operator`, `viewer`), `password_hash` (bcrypt), `created_at`. |
| `memberships` | Explicit org membership records. Columns: `id` (UUID), `user_id` (FK), `org_id` (FK), `role`. Supports future multi-org membership. |
| `api_keys` | API key records. Columns: `id` (UUID), `user_id` (FK), `key_hash` (SHA-256 hex), `name` (human-readable label), `last_used_at` (updated on each authenticated request), `created_at`. |

**Tables this module reads (read-only):**
| Table | Source Domain |
|---|---|
| `organizations` | Organizations — validates `org_id` on registration. |

## APIs
| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new user. Hashes password (bcrypt, cost 12), creates `users` and `memberships` rows. Returns access + refresh tokens. |
| `POST` | `/auth/login` | Authenticate with email/password. Returns access token (1-hour JWT RS256) and refresh token (30-day JWT RS256). |
| `POST` | `/auth/refresh` | Exchange a valid refresh token for a new access token. Refresh token is rotated on each use (sliding window). Old refresh token is invalidated. |
| `GET` | `/users/me` | Return the authenticated user's profile: `{ id, email, role, org_id, created_at }`. |
| `PATCH` | `/users/me` | Update the authenticated user's own profile. Allowed fields: `email`, `password` (re-hashed with bcrypt). Role changes require `admin`. |
| `POST` | `/api-keys` | Generate a new API key. The plaintext key is returned **once** in the response and never retrievable again. Body: `{ name }`. |
| `GET` | `/api-keys` | List all API keys for the authenticated user. Returns metadata only: `{ id, name, last_used_at, created_at }` — never the key itself. |
| `DELETE` | `/api-keys/:id` | Revoke an API key. Deletes the `api_keys` row; the key becomes immediately invalid. |

## RBAC Permission Matrix
| Action | viewer | operator | admin |
|---|---|---|---|
| Read cluster data | ✅ | ✅ | ✅ |
| Read recommendations | ✅ | ✅ | ✅ |
| Approve recommendations | ❌ | ✅ | ✅ |
| Trigger execution | ❌ | ✅ | ✅ |
| Set operator overrides | ❌ | ✅ | ✅ |
| Manage organization settings | ❌ | ❌ | ✅ |
| Manage users | ❌ | ❌ | ✅ |
| View audit logs | ❌ | ✅ | ✅ |

## JWT Token Details
- **Algorithm:** RS256 (asymmetric; private key held server-side, public key distributed for verification).
- **Access token TTL:** 3600 seconds (1 hour).
- **Refresh token TTL:** 30 days (sliding — rotated on each use).
- **Claims:** `sub` (user UUID), `org_id`, `role`, `iat`, `exp`.
- **Refresh token rotation:** On each `/auth/refresh` call, the old refresh token is immediately invalidated and a new one is issued. Concurrent use of the same refresh token (replay attack) is detected and causes all refresh tokens for that user to be invalidated.

## API Key Authentication
- API keys are passed via the `Authorization: ApiKey <key>` header.
- The platform computes SHA-256 of the presented key and compares it against `api_keys.key_hash`.
- `api_keys.last_used_at` is updated asynchronously (via a write-behind queue) to avoid adding latency to every authenticated request.
- API keys inherit the `role` of the user who created them and are scoped to the same `org_id`.

## Dependencies
- **organizations** module — validates `org_id` on user registration; `organizations` table must exist and the org must be in valid state.
- **shared/auth** — JWT RS256 signing and verification utilities; bcrypt helpers.
- **shared/db** — PostgreSQL client; all user writes use serializable isolation to prevent race conditions on registration.
- **Redis** — Refresh token revocation list (for invalidating compromised tokens before expiry) and `last_used_at` write-behind queue.
- **shared/logger** — structured logging with `user_id`, `org_id` context (passwords and tokens never logged).

## Configuration
| Environment Variable | Default | Description |
|---|---|---|
| `JWT_PRIVATE_KEY_PATH` | *(required)* | Path to RSA private key PEM file for JWT signing. No default. |
| `JWT_PUBLIC_KEY_PATH` | *(required)* | Path to RSA public key PEM file for JWT verification. No default. |
| `JWT_ACCESS_TOKEN_TTL_SECONDS` | `3600` | Access token time-to-live. |
| `JWT_REFRESH_TOKEN_TTL_DAYS` | `30` | Refresh token time-to-live (sliding window). |
| `BCRYPT_COST_FACTOR` | `12` | bcrypt work factor for password hashing. Valid range: 10–14. |
| `API_KEY_LAST_USED_WRITE_BEHIND_INTERVAL_SECONDS` | `60` | How often the write-behind queue flushes `last_used_at` updates to PostgreSQL. |
| `REFRESH_TOKEN_REVOCATION_LIST_TTL_DAYS` | `30` | Redis TTL for revoked refresh token entries (matches refresh token TTL). |

## Error Handling
- **Invalid credentials:** Returns HTTP 401 with a generic `"Invalid email or password"` message — does not distinguish between unknown email and wrong password to prevent user enumeration.
- **Expired access token:** Returns HTTP 401 with `code: "TOKEN_EXPIRED"`. Client should call `/auth/refresh`.
- **Revoked or expired refresh token:** Returns HTTP 401 with `code: "REFRESH_TOKEN_INVALID"`. Client must re-authenticate via `/auth/login`.
- **Refresh token replay detected:** All active refresh tokens for the user are immediately invalidated. User must re-authenticate. A security alert is written to `audit_logs`.
- **Duplicate email registration:** Returns HTTP 409 with `code: "EMAIL_ALREADY_EXISTS"`.
- **bcrypt hashing failure:** Returns HTTP 500; the request is not persisted. Error is logged with full context (excluding the password).
- **Database write failure on registration:** Registration is atomic — if either the `users` or `memberships` insert fails, both are rolled back.

## Future Enhancements
- **Multi-organization membership:** Allow users to belong to multiple organizations, switching context via a session-scoped `org_id` claim. `memberships` table is pre-structured for this.
- **SSO / SAML / OIDC:** Add an identity provider integration so enterprise customers can use their existing IdP (Okta, Azure AD) without creating separate BalanceKube passwords.
- **MFA (TOTP):** Add TOTP-based multi-factor authentication as an optional security layer for `admin` and `operator` roles.
- **Session management UI:** Allow users to view and revoke active refresh tokens and API keys from a security dashboard.
- **Rate limiting on auth endpoints:** Apply per-IP and per-email rate limiting on `/auth/login` and `/auth/refresh` to mitigate brute-force attacks.
