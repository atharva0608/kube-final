# Frontend: Services

## Purpose
API client wrappers and external service integrations.

## Responsibilities
- Configures the Axios instance with standard headers and base URLs.
- Implements the JWT refresh token interceptor (silent token refresh on 401).
- Provides typed wrapper functions for all backend API endpoints.

## Inputs
- Source: `frontend/hooks`.
- Format: Function calls.

## Outputs
- Destination: Backend API.
- Format: HTTP requests.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Integrates with the entire `backend/*` API surface.

## Dependencies
- Axios.

## Configuration
- `NEXT_PUBLIC_API_URL`

## Error Handling
- Interceptors format and throw standardized errors.

## Future Enhancements
- GraphQL Apollo Client if the API migrates to GraphQL.
