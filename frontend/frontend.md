# Frontend

## Purpose
Root frontend documentation. The BalanceKube frontend is a modern single-page application (SPA) providing the dashboard interface for operators to view cluster states, classify workloads, review recommendations, and approve execution plans.

## Responsibilities
- Renders the user interface.
- Manages client-side state and caching.
- Authenticates users via the backend API (JWT).
- visualizes complex Kubernetes topology and pricing data.

## Inputs
- Source: User interaction.
- Format: Clicks, form submissions.

## Outputs
- Destination: Backend API.
- Format: REST API calls.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A (Reads/Writes via backend API).

## APIs
- N/A

## Dependencies
- React / Next.js, Tailwind CSS, TanStack Query (React Query).

## Configuration
- `NEXT_PUBLIC_API_URL`: Points to the backend API.

## Error Handling
- Global error boundaries catch rendering crashes.
- Axios interceptors catch 401s and trigger token refreshes.

## Future Enhancements
- Real-time updates via WebSockets.
