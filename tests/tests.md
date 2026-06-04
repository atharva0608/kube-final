# Tests

## Purpose
Root directory for all automated test suites.

## Responsibilities
- Defines unit tests (`*.test.ts`), integration tests, and end-to-end (E2E) tests.
- Contains mock data payloads and test fixtures (e.g., sample Kubelet metrics, spot pricing JSON).
- Houses Playwright/Cypress tests for the frontend UI.
- Defines test database setup and teardown hooks.

## Inputs
- Source: CI/CD pipeline or local `npm run test`.
- Format: Jest / Vitest configurations.

## Outputs
- Destination: Test runner output.
- Format: Test reports, coverage metrics.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- Provisions temporary, isolated PostgreSQL databases per test suite runner.

## APIs
- N/A

## Dependencies
- Jest / Vitest, Supertest, Playwright.

## Configuration
- Jest config files.

## Error Handling
- Fails the build on test failures.

## Future Enhancements
- Mutation testing.
