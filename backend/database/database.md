# Backend Database

## Purpose
Database connection pool, migration management, and query helper utilities. Provides the foundational persistence layer for the backend services.

## Responsibilities
- Manages the PostgreSQL connection pool.
- Handles row-level security (RLS) enforcement via session variables.
- Executes forward-only, version-controlled database migrations.
- Provides transaction helpers and query builders.

## Inputs
- Source: Function calls from domain modules.
- Format: SQL queries or query builder objects.

## Outputs
- Destination: PostgreSQL database.
- Format: Query results.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A (Cross-cutting infrastructure, owns no business tables).

## APIs
- N/A

## Dependencies
- `pg` or equivalent PostgreSQL client.
- `golang-migrate` / `node-pg-migrate`.

## Configuration
- `DATABASE_URL`: Primary PostgreSQL connection string.
- `DB_POOL_MIN`: Minimum connections (default: 2).
- `DB_POOL_MAX`: Maximum connections (default: 20).
- `DB_IDLE_TIMEOUT_MS`: Connection idle timeout (default: 30000).

## Error Handling
- Connection failures trigger application startup failure.
- Transient query failures are propagated to the caller for retry.
- Redis caching failures (e.g., for locks or pricing) fall back to fetching from the source/DB.

## Future Enhancements
- Read replica support for heavy analytical queries.