# shared

## Purpose
The shared module is the internal design system and utility library for the BalanceKube frontend. It provides every cross-cutting concern that must be consistent across all feature areas: the API client, TypeScript type definitions, authentication context, reusable UI components, custom hooks, and Zod validation schemas. All other frontend feature modules import exclusively from `shared`—no feature module imports directly from another feature module.

## Responsibilities
- **API client (`shared/api`):** Wrap Axios (or fetch) with:
  - `Authorization: Bearer <access_token>` header injection on every outgoing request.
  - Transparent 401 handling: on receiving a 401, silently attempt token refresh via the refresh token `httpOnly` cookie, then retry the original request once. On second 401, clear auth state and redirect to login.
  - Response parsing through the Zod schema registered for each endpoint.
  - Normalised error object: `ApiError { code: string, message: string, details?: Record<string, string> }`.
  - Base URL from `VITE_API_BASE_URL` environment variable.
- **TypeScript interfaces (`shared/types`):** Canonical TypeScript interfaces mirroring all backend data models: `Cluster`, `Node`, `Pod`, `Deployment`, `StatefulSet`, `DaemonSet`, `PVC`, `PDB`, `Workload`, `WorkloadTag`, `EligibilityVerdict`, `Recommendation`, `Execution`, `AuditLog`, `Agent`, `Organisation`, `User`, `ApiKey`, etc.
- **Auth context (`shared/auth`):** React Context providing: current user, access token (in-memory only), `login()`, `logout()`, `refreshToken()` functions. Context wraps the entire application router.
- **Shared components (`shared/components`):**
  - `DataTable`: sortable, filterable, paginated table with server-side pagination support.
  - `Chart`: line chart, bar chart, sparkline wrappers around Recharts (or equivalent).
  - `Modal`: accessible modal with confirm/cancel pattern and `zod`-validated forms inside.
  - `Toast`: global toast notification system (success, warning, error, info).
  - `StatusBadge`: colour-coded badge component (takes a status string and a colour map config).
  - `Spinner`: loading indicator, used at page and component level.
  - `ErrorBoundary`: per-feature error boundary that shows a fallback panel on React render errors.
  - `DateRangePicker`: date range input for audit log and metric time range filters.
  - `JsonDiffViewer`: collapsible syntax-highlighted JSON diff for audit and execution step views.
- **Hooks (`shared/hooks`):**
  - `useCluster(clusterId)`: fetches and caches cluster metadata.
  - `useRecommendation(clusterId, recId)`: fetches and caches recommendation detail.
  - `usePolling(fetchFn, intervalMs, enabled)`: generic polling hook; auto-cancels on component unmount; pauses on error.
- **Zod schemas (`shared/validation`):** Runtime validation schemas for all API response types and all form inputs. Used by the API client to validate responses and by form components to validate user input.
- **Theme / Design tokens (`shared/theme`):** CSS-in-JS or CSS variable definitions for colours, typography, spacing, breakpoints.

## Inputs
- **Source:** Other frontend feature modules import types, components, hooks, and API client from `shared`.
- **Source:** `VITE_API_BASE_URL` environment variable (consumed by the API client).
- **Source:** Browser `httpOnly` cookie containing the refresh token (consumed by the auth context for token refresh).

## Outputs
- **Destination:** Exports re-used by all frontend feature modules.
- **Destination:** HTTP requests to the backend API (via the API client on behalf of feature modules).

## Events Produced
N/A

## Events Consumed
N/A

## Database Tables
N/A — Frontend has no direct database access.

## APIs
The shared API client wraps calls to any backend endpoint. No specific endpoint is owned by `shared`—it provides the transport mechanism used by all feature modules. The API client implements:
- `api.get<T>(path, params?)` — typed GET with Zod response validation
- `api.post<T>(path, body?)` — typed POST
- `api.patch<T>(path, body?)` — typed PATCH
- `api.delete(path)` — DELETE

## Dependencies
- **React** — Context API, hooks, component model
- **TypeScript** — Type safety across all exports
- **Axios (or fetch)** — HTTP transport
- **Zod** — Runtime schema validation (API responses and form inputs)
- **Recharts (or equivalent)** — Chart rendering primitives wrapped by `Chart` components
- **React Router** — Used by `ErrorBoundary` for navigation on auth failure
- **Vite** — Build environment for `VITE_*` env variable access

## Configuration
| Variable | Purpose | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL used by the API client | `http://localhost:3000` |
| `VITE_APP_ENV` | Environment label (affects error reporting verbosity) | `dev` |
| `VITE_POLLING_INTERVAL_MS` | Default polling interval for `usePolling` hook | `15000` |

## Error Handling
- **Zod parse failure on API response:** If the backend returns a response that does not match the registered Zod schema, the API client throws an `ApiError` with `code: 'RESPONSE_SCHEMA_MISMATCH'`. Feature modules receive this as a standard error and show it as a "Unexpected response format" error card.
- **Network error (no response):** Caught by the API client and wrapped in `ApiError { code: 'NETWORK_ERROR' }`. Feature modules may choose to show a retry button or a connectivity warning.
- **Auth failure in context:** `logout()` clears in-memory access token, removes all cached query data, and navigates to `/login`.
- **`usePolling` error:** On consecutive API errors during polling, the hook applies exponential backoff (up to 5× the base interval) to avoid hammering a degraded backend.

## Future Enhancements
- Shared stale-while-revalidate cache layer (React Query or SWR) to replace ad-hoc `usePolling` in feature modules with a unified cache invalidation strategy.
- Component library documentation site (Storybook) for the `shared/components`.
- Centralised feature flag context (for gradual rollout of new UI features without deploys).
- WebSocket client in `shared/api` for real-time subscription support when the backend adds push capabilities.
