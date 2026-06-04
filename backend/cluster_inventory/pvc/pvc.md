# Cluster Inventory: PVCs

## Purpose
PersistentVolumeClaim inventory CRUD and queries. Part of the `cluster_inventory` module.

## Responsibilities
- Persists PVC inventory data from the agent.
- Links PVCs to specific Pods.
- Extracts topology labels to determine if a PVC is zone-locked (e.g., EBS volumes).

## Inputs
- Source: Agent inventory push.
- Format: JSON.

## Outputs
- Destination: Backend and Frontend.
- Format: API responses.

## Events Produced
- N/A

## Events Consumed
- N/A

## Database Tables
- `pvcs` (id, cluster_id, snapshot_id, name, namespace, storage_class, access_modes, capacity_gi, phase, pod_id, az, zone_locked, collected_at).

## APIs
- `GET /clusters/:id/pvcs`

## Dependencies
- `backend/database`

## Configuration
- N/A

## Error Handling
- Standard API errors.

## Future Enhancements
- Support for cross-AZ CSI drivers.
