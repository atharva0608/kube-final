# Infrastructure: Docker

## Purpose
Containerization definitions for all modules.

## Responsibilities
- Provides `Dockerfile` definitions for `backend`, `workers`, `frontend`, and `agent`.
- Implements multi-stage builds to minimize final image sizes.
- Ensures non-root user execution inside containers for security.

## Inputs
- Source: Application source code.
- Format: Source files.

## Outputs
- Destination: ECR (Elastic Container Registry).
- Format: Docker images.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- N/A

## APIs
- N/A

## Dependencies
- Base images (e.g., `node:20-alpine`, `golang:1.22-alpine`).

## Configuration
- N/A

## Error Handling
- Build failures halt the CI pipeline.

## Future Enhancements
- Distroless base images.
