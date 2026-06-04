# Frontend: Hooks

## Purpose
Custom React Hooks for state and side-effects.

## Responsibilities
- Wraps `react-query` hooks for API data fetching (e.g., `useWorkloads`, `useRecommendations`).
- Manages complex local state (e.g., table filtering, sorting, pagination).
- Interfaces with browser APIs (e.g., `useLocalStorage`, `useMediaQuery`).

## Inputs
- Source: Component renders.
- Format: Function arguments.

## Outputs
- Destination: Component state.
- Format: Reactive values and mutator functions.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- Calls various backend REST endpoints.

## Dependencies
- TanStack Query (React Query).

## Configuration
- Query cache times.

## Error Handling
- Propagates loading and error states to components.

## Future Enhancements
- N/A
