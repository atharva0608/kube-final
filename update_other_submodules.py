import os

docs = {
    'backend/drift_detection/cluster_hash': """# cluster_hash

## Purpose
Computes and verifies the structural cluster topology hash.

## Responsibilities
- Computes SHA-256 hash of node inventory, node types, counts, and AZ distribution.
- Flags when the cluster hash diverges from an approved plan.

## Dependencies
- Reads `assembled_snapshots`
""",
    'backend/drift_detection/plan_delta': """# plan_delta

## Purpose
Generates patchable deltas for plans when non-structural drift occurs.

## Responsibilities
- Computes diffs between the baseline snapshot and the current snapshot.
- Writes to `plan_deltas` if changes are patchable.

## Database Tables
- Writes: `plan_deltas`
""",
    'backend/eligibility_engine/conditional_rules': """# conditional_rules

## Purpose
Evaluates conditional eligibility rules that result in `ELIGIBLE_WITH_CONDITIONS`.

## Responsibilities
- Flags PVC zone locks.
- Flags StatefulSets for sequential replica drain.
- Flags Batch spikes.
""",
    'backend/eligibility_engine/hard_rules': """# hard_rules

## Purpose
Evaluates hard blocking rules for Spot eligibility.

## Responsibilities
- Blocks databases, DaemonSets, workloads with 1 replica and no HPA.
- Blocks workloads with high spot risk (>= 8).
""",
    'backend/eligibility_engine/operator_overrides': """# operator_overrides

## Purpose
Applies manual operator placement intents that override automated rules.

## Responsibilities
- Applies `workload_config.placement_intent`.
- Honors explicit manual blocks or inclusions.
"""
}

def add_standard_sections(content):
    required = ["## Purpose", "## Responsibilities", "## Inputs", "## Outputs", "## Events Produced", "## Events Consumed", "## Database Tables", "## APIs", "## Dependencies", "## Configuration", "## Error Handling", "## Future Enhancements"]
    for req in required:
        if req not in content:
            content += f"\n{req}\n- N/A\n"
    return content

for path, content in docs.items():
    p = os.path.join('/Users/atharvapudale/Desktop/backend-ecc/Atharva Repo/github/balancekube', path, f"{os.path.basename(path)}.md")
    if os.path.exists(os.path.dirname(p)):
        with open(p, "w") as f:
            f.write(add_standard_sections(content))
        print(f"Updated {path}")
    else:
        print(f"Dir not found: {path}")

