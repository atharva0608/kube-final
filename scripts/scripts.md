# Scripts

## Purpose
Utility scripts for local development, database migrations, and CI/CD operations.

## Responsibilities
- `migrate.sh`: Wrapper for running golang-migrate or node-pg-migrate against local or remote databases.
- `seed.sh`: Populates a fresh local database with test data (organizations, users, mock inventory).
- `build.sh`: Compiles TypeScript and builds Docker images locally.
- `deploy-local.sh`: Deploys the stack to a local kind/minikube cluster using Helm.
- `lint-folder-docs.sh`: Verifies that all `*.md` files conform to the standard structure.

## Inputs
- Source: Developer CLI.
- Format: Shell commands.

## Outputs
- Destination: Local dev environment or CI runner.
- Format: Executed actions.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- bash/zsh, docker, psql.

## Configuration
- `.env.local` files.

## Error Handling
- Scripts exit with non-zero codes on failure to halt CI pipelines.

## Future Enhancements
- N/A
