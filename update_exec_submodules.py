import os

base_dir = '/Users/atharvapudale/Desktop/backend-ecc/Atharva Repo/github/balancekube/backend/execution'

docs = {
    'lock_manager': """# lock_manager

## Purpose
Manages the per-cluster execution mutex to prevent concurrent Phase 4 executions from corrupting the cluster state.

## Responsibilities
- Acquire and release `execution_locks` before and after execution.
- Auto-expire locks after 2 hours (TTL) to recover from crashes.

## Database Tables
- Writes: `execution_locks` (cluster_id, acquired_at, expires_at, execution_id)
""",
    
    'plan_validation': """# plan_validation

## Purpose
Ensures the execution plan matches the current cluster state before taking action.

## Responsibilities
- Validates the 3-part identity: `snapshot_id`, `analysis_version`, `cluster_hash`.
- Aborts execution if the plan is stale.

## Dependencies
- Reads `assembled_snapshots` and `recommendation_store`.
""",

    'capacity_provisioning': """# capacity_provisioning

## Purpose
Handles the optional provisioning of Spot instances using Karpenter NodeClaims before workload migration.

## Responsibilities
- Checks `karpenter_control_mode`. If `managed`, generates NodeClaims. If `observe`, skips provisioning.
- Applies a 20% CPU/memory buffer.
- Polls NodeClaim status every 10s up to 120s.

## Inputs
- Reads `clusters.cluster_template`.
""",

    'spot_placement': """# spot_placement

## Purpose
Handles Node and Pod scheduling guidance via labels and taints.

## Responsibilities
- Applies `balancekube.io/critical-only=true:NoSchedule` taint to on-demand nodes.
- Applies BalanceKube-managed labels to newly provisioned Spot nodes.
""",

    'node_drain': """# node_drain

## Purpose
Safely evicts pods from source nodes to migrate them to target nodes.

## Responsibilities
- Uses Kubernetes Eviction API. Never uses force-delete.
- Respects PodDisruptionBudgets (PDB). Retries on HTTP 429 up to 10 times with 30s delay.
- Enforces pre-drain delay (10s normal, 15s if Istio sidecar).
- Always uncordons nodes on failure.
""",

    'workload_migration': """# workload_migration

## Purpose
Handles complex workload migration strategies, specifically for StatefulSets.

## Responsibilities
- Drains StatefulSet replicas one at a time (DRAIN_STATEFUL_REPLICA).
- Waits for each replica to be rescheduled and report Ready before proceeding to the next.
""",

    'health_validation': """# health_validation

## Purpose
Verifies cluster health post-migration to determine execution success or trigger rollback.

## Responsibilities
- Validates that >= 75% of SPOT group pods are Running on Spot within 10 minutes.
- Validates that zero HIGH/CRITICAL pods are on Spot.
- Validates StatefulSets have no Pending pods > 5 minutes.
""",

    'execution_history': """# execution_history

## Purpose
Records the outcome of every Phase 4 execution run.

## Responsibilities
- Writes the final status (success, rolled_back, failed, aborted) and failure reasons.
- Tracks `nodes_provisioned`, `nodes_drained`, `workloads_migrated`, `savings_realised_monthly`.

## Database Tables
- Writes: `execution_history`
"""
}

def add_standard_sections(content):
    required = ["## Purpose", "## Responsibilities", "## Inputs", "## Outputs", "## Events Produced", "## Events Consumed", "## Database Tables", "## APIs", "## Dependencies", "## Configuration", "## Error Handling", "## Future Enhancements"]
    for req in required:
        if req not in content:
            content += f"\n{req}\n- N/A\n"
    return content

for mod, content in docs.items():
    p = os.path.join(base_dir, mod, f"{mod}.md")
    if os.path.exists(p):
        with open(p, "w") as f:
            f.write(add_standard_sections(content))
        print(f"Updated {mod}")

