# Backend Drift Detection Resource Diff

## Overview
`backend/drift_detection/resource_diff` is the documentation entry for the `resource_diff` module within the BalanceKube repository.
Resource Diff support within the drift detection, plan delta generation, and invalidation.
This folder is part of the `backend` domain and provides focused behavior for `Resource Diff`.

## Current folder responsibilities
- Owns the module-level responsibilities for `resource_diff` in the `backend` domain.
- Implements the primary behavior and contracts for the `Resource Diff` feature area.
- Supports the broader `Backend` workflow and integrates with sibling modules in the same domain.

- This leaf module is one part of the `drift_detection` domain within `backend`. Related sibling modules include `configuration_diff`, `impact_analysis`, `node_diff`, `plan_delta`, `pod_diff`, `reanalysis`, `snapshot_comparator`.

## Subfolders
- This module has no further nested subfolders.

## Related documentation
- `balancekube.md` for the overall BalanceKube architecture and domain relationships.
- `backend/backend.md` for the root of the `backend` domain documentation.
- `backend/drift_detection/drift_detection.md` for the parent domain documentation, if available.

## Notes
- Use this document to describe the folder purpose, submodule summaries, and cross-domain interactions.
