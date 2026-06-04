# kubernetes

## Purpose
The Kubernetes module provides the Helm chart (`charts/balancekube-agent`) that deploys the BalanceKube agent into a customer's EKS cluster. It packages all Kubernetes resource definitions needed for the agent to operate: the controller deployment, the DaemonSet, RBAC, service account, configuration, and the registration secret. This module is delivered to customers as a Helm chart and applied via the `kubectl` / Helm command shown in the onboarding wizard.

## Responsibilities
- Package and maintain the `balancekube-agent` Helm chart.
- Deploy the **Controller Deployment** (1 replica, leader-election enabled) which:
  - Connects to the BalanceKube backend API using the registration token.
  - Drives the collection loop (API-list Kubernetes resources, send inventory snapshots).
  - Exposes `/healthz` liveness and readiness probes on port 8080.
- Deploy the **DaemonSet** (1 pod per node, `hostNetwork=true`) which:
  - Collects node-level metrics (CPU, memory, network, filesystem).
  - Forwards metrics to the controller for aggregation and transmission.
- Deploy **ClusterRole + ClusterRoleBinding** granting read-only access to all collected resource types:
  - `list`, `watch`, `get` on: `nodes`, `pods`, `deployments`, `statefulsets`, `daemonsets`, `replicasets`, `jobs`, `cronjobs`, `horizontalpodautoscalers`, `persistentvolumeclaims`, `poddisruptionbudgets`, `namespaces`, `resourcequotas`, `limitranges`
  - `create`, `update`, `get` on: `leases` (leader election only)
  - Zero write permissions to any workload resources
- Deploy a **ServiceAccount** for the controller and DaemonSet.
- Deploy a **Kubernetes Secret** containing the registration token (value injected at install time via `--set registrationToken=<value>`).
- Deploy a **ConfigMap** containing agent configuration: `platformEndpoint`, `logLevel`, collection interval.
- Support **tolerations** and **nodeSelector** in Helm values to control which nodes the controller and DaemonSet are scheduled on.

## Inputs
- **Source:** Helm values file (`values.yaml` / `values-prod.yaml`) and `--set` overrides at install time
- **Format:** YAML Helm values

Key required values:
| Value | Description |
|---|---|
| `registrationToken` | Short-lived JWT obtained from `POST /clusters` during onboarding. Required. |
| `platformEndpoint` | BalanceKube backend API URL (e.g., `https://api.balancekube.io`). Required. |

Key optional values:
| Value | Description | Default |
|---|---|---|
| `logLevel` | Agent log verbosity (`info` / `debug`) | `info` |
| `image.tag` | Agent container image tag | `latest` |
| `image.repository` | Container image repository | `ghcr.io/balancekube/agent` |
| `controller.resources.requests.cpu` | CPU request for controller | `100m` |
| `controller.resources.requests.memory` | Memory request for controller | `128Mi` |
| `controller.resources.limits.cpu` | CPU limit for controller | `500m` |
| `controller.resources.limits.memory` | Memory limit for controller | `256Mi` |
| `daemonset.resources.requests.cpu` | CPU request per DaemonSet pod | `50m` |
| `daemonset.resources.requests.memory` | Memory request per DaemonSet pod | `64Mi` |
| `tolerations` | Tolerations for controller and DaemonSet | `[]` |
| `nodeSelector` | NodeSelector for controller | `{}` |
| `collectionIntervalSeconds` | How often the agent collects inventory | `60` |

## Outputs
- **Destination:** Kubernetes resources deployed into the customer's cluster:
  - `Deployment/balancekube-agent-controller`
  - `DaemonSet/balancekube-agent-node-collector`
  - `ClusterRole/balancekube-agent`
  - `ClusterRoleBinding/balancekube-agent`
  - `ServiceAccount/balancekube-agent`
  - `Secret/balancekube-agent-token`
  - `ConfigMap/balancekube-agent-config`

## Events Produced
N/A — Infrastructure; the agent itself emits `agent.heartbeat` events to the backend API, but that is application logic, not infrastructure provisioning.

## Events Consumed
N/A

## Database Tables
This module does not provision any database tables. The agent registration record is created in the `agents` and `agent_tokens` tables by the backend API when the registration token is used.

## APIs
N/A — Helm charts do not expose REST APIs.

## Dependencies
- **Helm** (≥ 3.12) — Chart packaging and deployment
- **Kubernetes** (≥ 1.24) — Target cluster API version compatibility
- **EKS** — Primary supported Kubernetes distribution
- **BalanceKube backend API** — The agent connects outbound to `platformEndpoint`; the customer's cluster must have network egress to the BalanceKube API endpoint on port 443.

## Configuration
All configuration is via Helm values (see Inputs table). Additional chart-level configuration:

| Value | Description | Default |
|---|---|---|
| `namespace` | Kubernetes namespace for agent resources | `balancekube` |
| `serviceAccount.create` | Whether to create the ServiceAccount | `true` |
| `leaderElection.enabled` | Enable leader election for controller HA | `true` |
| `healthz.port` | Controller liveness probe port | `8080` |

## Error Handling
- **Invalid registration token:** If the registration token has expired or is invalid, the controller pod will crash-loop with `AUTH_FAILURE` in its logs. Resolution: generate a new token via `POST /agents/register` and upgrade the Helm release with `--set registrationToken=<new-token>`.
- **Missing RBAC permissions:** If the ClusterRole is not applied correctly, the agent will log `PERMISSION_DENIED` errors for specific resource types and report missing permissions in its heartbeat payload (visible in the agent management UI). Resolution: `helm upgrade` to re-apply the ClusterRole.
- **DaemonSet pod scheduling failure:** If nodes have taints that reject the DaemonSet pods, collection data will be missing for those nodes. Resolution: add appropriate `tolerations` to the Helm values.
- **Helm atomic upgrade:** The chart is designed to support `helm upgrade --atomic` so that a failed upgrade rolls back to the previous agent version automatically.

## Future Enhancements
- Helm chart publishing to a public Helm repository (OCI registry) for one-line install without downloading a YAML file.
- Agent auto-upgrade via a Kubernetes operator pattern (watch a ConfigMap for the desired version and self-upgrade).
- Network Policy resource in the chart to restrict the DaemonSet's network access to only the controller.
- Support for OpenShift Security Context Constraints (SCC) as an alternative to standard Kubernetes RBAC.
