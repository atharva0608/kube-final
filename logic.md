# BalanceKube — System Logic

The complete logic for every node in the end-to-end flow. Sections follow the flowchart exactly. Sub-points under each node cover implementation detail not shown in the flowchart but required for the node to work correctly.

---

## PHASE 0 — ONBOARDING

---

### Customer Registration

The operator creates an account on BalanceKube. This establishes the multi-tenancy boundary — every subsequent table, API call, and execution is scoped to an organisation. Two rows are created: one `customers` row and one `clusters` row with `connection_status = PENDING` and `onboarding_status = PENDING`. No AWS calls are made at this step.

- `aws_account_id` and `region` are collected here. The cluster name is **not** collected — it will be selected from a live inventory in a later step. Requiring a typed cluster name at registration is the leading cause of "wrong cluster" support tickets, so we eliminate it entirely.
- `karpenter_control_mode` defaults to `observe` on creation. This field controls whether Phase 4 is permitted to create Karpenter NodeClaims. The operator must explicitly change it to `managed` before any node provisioning can occur.
- Returns `cluster_id` and a pre-signed S3 URL for the CloudFormation template that will be generated next.

---

### Create Organisation

Establishes the tenant boundary in the platform database. Every subsequent table (`clusters`, `workload_config`, `application_group_definitions`, `execution_history`) is scoped to this organisation via `customer_id`. Two customers can never access each other's data. The `customer_id` is a UUID, never an integer sequence, to prevent enumeration.

---

### Generate External ID

A UUID generated once per cluster registration and stored in `clusters.external_id`. It is embedded in the CloudFormation template before the operator downloads it.

**Purpose:** prevents the confused deputy attack. AWS requires the caller to supply this UUID when assuming the role via `sts:ExternalId`. An attacker who finds the role ARN but does not have the External ID cannot assume the role. This is a standard AWS cross-account access security requirement.

- Generated server-side using a cryptographically secure random source. Never exposed to the operator in plaintext — they only encounter it embedded inside the CFN template.
- Stored permanently in `clusters.external_id`. Used on every subsequent `sts.assume_role` call from the platform.

---

### Generate CloudFormation Template

A parameterised IAM CloudFormation template is populated with the customer's `external_id` and stored as a pre-signed S3 object. The operator downloads and deploys it into their own AWS account. It creates exactly one IAM role.

**Trust policy on the role:** allows only `arn:aws:iam::PLATFORM_ACCOUNT_ID:root` to assume it, with a `Condition` block requiring `sts:ExternalId` to match the customer's UUID.

**Permission policy on the role** — only the minimum required:
- `ec2:DescribeInstances` — so Phase 1's account collector can enrich node snapshots with EC2 metadata (instance ID, launch time, spot request ID, AZ).
- `ec2:DescribeSpotInstanceRequests` — so the account collector can verify spot request state.
- `ec2:DescribeRegions` — so cluster discovery can confirm region availability.

Nothing more. Every additional permission is a security review cost for the customer's IAM team and a liability for us. The CFN stack output key `BalanceKubeRoleArn` is the only thing the operator needs to copy from the stack after deployment.

---

### Download Template (Manual)

The operator downloads the pre-built CFN template via a "Deploy to AWS" button in the UI. This opens an AWS Console deep-link with the template URL pre-filled. The operator sees exactly which IAM role and policies will be created before clicking Create.

---

### Deploy CloudFormation Stack (Manual)

The operator deploys the stack into their AWS account. Takes 30–60 seconds. When complete, the Outputs tab shows `BalanceKubeRoleArn`.

---

### CloudFormation Creates IAM Role

CFN creates the IAM role with the trust policy (ExternalId condition) and the minimal permission policy. Both are visible in the stack's Resources tab. The customer's IAM team can audit exactly what was created without reading documentation.

---

### CloudFormation Creates Required Policies

The permission policy (`ec2:DescribeInstances`, `ec2:DescribeSpotInstanceRequests`, `ec2:DescribeRegions`) is attached as an inline policy — not a managed AWS policy. This ensures the customer's IAM review shows a concrete, bounded list with no hidden managed-policy expansions.

---

### CloudFormation Configures Cross Account Access

The trust policy on the IAM role allows the BalanceKube platform AWS account to call `sts:AssumeRole` on this role, provided the ExternalId condition is satisfied. This is the only mechanism the platform uses to access the customer's AWS account — there are no long-lived credentials, no access keys stored anywhere.

---

### Copy IAM Role ARN (Manual)

The operator copies the Role ARN from the CloudFormation stack Outputs tab. Format: `arn:aws:iam::123456789012:role/BalanceKubeRole`.

---

### Paste Role ARN In UI (Manual)

The operator pastes the ARN into the BalanceKube UI. The frontend POSTs it to `POST /api/v1/clusters/{id}/validate`.

---

### Validate AWS Access

The backend calls `sts.assume_role(RoleArn=role_arn, RoleSessionName="balancekube-validation", ExternalId=stored_external_id, DurationSeconds=900)`.

- Extracts the account ID from the assumed role ARN and verifies it matches the registered `aws_account_id`. This prevents a customer submitting a role from a different account — a mistake that would grant the platform access to the wrong AWS account.
- On success: stores `role_arn` in the clusters table, sets `connection_status = CONNECTED`, caches temporary STS credentials in Redis (`sts_creds:{cluster_id}`, TTL = expiry minus 60 seconds). Returns 200.
- On failure: returns a specific, actionable error message. `AccessDenied` → "Role trust policy incorrect — check ExternalId". `NoSuchEntity` → "Role ARN not found". Account mismatch → "Role belongs to a different AWS account". Generic error messages that say "validation failed" create support tickets; specific messages let the operator self-serve.
- This runs synchronously. The UI shows a spinner. The result is returned directly — not queued — because the operator is actively waiting.

---

### Validation Successful? (Decision)

If STS validation fails: the operator sees the specific error and can correct the Role ARN or fix the trust policy. No state changes on failure. They retry.

If it passes: the flow continues to cluster discovery.

---

### Discover Available Clusters

The backend calls `eks.list_clusters()` using the cached STS credentials, in the customer's configured region. Returns all cluster names visible in their account.

- For each cluster name, calls `eks.describe_cluster(name)` to fetch status, Kubernetes version, and ARN. These calls are made in parallel, not serially.
- Only `ACTIVE` clusters are returned to the UI. `CREATING`, `DELETING`, and `FAILED` clusters are filtered out — the operator cannot connect to a cluster that is not stable.
- This eliminates the entire class of "wrong cluster name" support ticket. The operator selects from a live list rather than typing a name.

---

### Display Cluster Inventory

The UI presents the list of ACTIVE EKS clusters available in the operator's account and region. Each row shows cluster name, Kubernetes version, and ARN.

---

### Select Cluster (Manual)

The operator selects their target EKS cluster. The frontend POSTs `cluster_name` and `cluster_arn` to `POST /api/v1/clusters/{id}/select-cluster`.

- The backend calls `eks.describe_cluster(name)` once more to confirm the cluster is still ACTIVE. State may have changed since the discovery call — this prevents registering a cluster that is already being deleted.
- Stores `cluster_name` and `cluster_arn` in the clusters table. The `cluster_arn` is the durable unique identifier — two clusters in different accounts can share the same name, but ARNs are globally unique.

---

### Generate Cluster Registration Token

A 256-bit random token is generated using a cryptographically secure source (`secrets.token_urlsafe(32)`). Only the SHA-256 hash is stored in the `cluster_tokens` table. The plaintext token is shown to the operator exactly once and is never retrievable again — this is the standard pattern for API tokens.

This token is the credential the in-cluster agent uses to authenticate all POST requests to the backend. It never expires automatically, but the operator can revoke it and generate a new one at any time.

---

### One Click Agent Installation

A Helm install command is generated with the `cluster_id` and token pre-filled and shown to the operator. Executing it deploys both agent components simultaneously from a single Helm chart.

**Agent Controller** — a single-replica Deployment with leader election. Responsible for K8s API collection (nodes, pods, PDBs, HPAs, KEDA, NodeClaims, ArgoCD/Flux CRDs), snapshot assembly, CD ownership scanning, and snapshot POST to backend.

**Agent DaemonSet** — one pod per node. Responsible for Kubelet Summary API metrics collection per node, IMDS polling for spot termination notice (ITN) detection, and per-node heartbeat.

The agent has no AWS credentials, no database access, no Redis. It communicates with the backend over HTTPS only using the bearer token. This limits the blast radius if an agent pod is compromised.

---

### Deploy Agent Controller

The Agent Controller Deployment starts, acquires a Kubernetes Lease (`coordination.k8s.io/v1`) for leader election, and begins its startup sequence: paginated LIST of all nodes and pods to build in-memory state (NodeMap, WorkloadMap), then switches to Watch streams for delta updates. Exposes `/healthz`.

**ClusterRole permissions (exact, no extras):** `nodes`, `pods`, `deployments`, `statefulsets`, `daemonsets` — get/list/watch. `poddisruptionbudgets`, `horizontalpodautoscalers`, `scaledobjects` (KEDA) — get/list/watch. `nodeclaims`, `nodepools` (Karpenter) — get/list/watch. `applications` (ArgoCD), `kustomizations` (Flux) — get/list. `leases` — get/create/update (leader election only). `persistentvolumeclaims` — get/list. **Zero write permissions in the ClusterRole.**

**Leader election:** only one Controller pod is active at a time even if multiple replicas are deployed for availability. This prevents the backend from receiving duplicate snapshots. The pod holding the lease logs `LEADER_ACQUIRED`. Non-leader pods sit idle, polling the lease every 5 seconds. On leader failure, a follower acquires within ~15 seconds.

---

### Deploy Agent DaemonSet

One DaemonSet pod runs on every node in the cluster. It has `hostNetwork: true` to reach the Instance Metadata Service (IMDS) at `169.254.169.254` without requiring privileged mode.

On startup each pod fetches its node identity from IMDS: `instance-id`, `instance-type`, `availability-zone`, `instance-life-cycle` (spot or normal). The node name is injected via the Downward API (`spec.nodeName`).

**IMDS polling uses IMDSv2:** first fetch a session token from `/latest/api/token` with `TTL-Seconds: 21600`, then use it as a header on all subsequent IMDS calls. Session token is refreshed before expiry.

**ITN detection loop runs every 5 seconds:** polls `/latest/meta-data/spot/termination-time`. HTTP 404 = no notice (normal). HTTP 200 = ITN received. Immediately POSTs to `POST /api/v1/itn`. This POST must complete in under 2 seconds — AWS gives a 2-minute window from ITN to termination. The backend must receive the event within 2 seconds to give the ITN handler the full remaining window. A pre-established connection pool (not a fresh HTTP connection per call) is used to meet this SLA.

Also polls `/latest/meta-data/events/recommendations/rebalance` every 5 seconds for the earlier EC2 Rebalance Recommendation signal. This is a softer, earlier warning than ITN.

---

### Agent Registration

Both the Controller and DaemonSet pods call `POST /api/v1/agent/register` on startup with their bearer token. The backend validates the token hash against `cluster_tokens`, records `agent_version`, and returns cluster configuration: snapshot interval, backend API version, feature flags.

Collection does not begin until registration succeeds. If registration fails (invalid token, network unreachable), the agent retries with exponential backoff. The backend exposes `GET /health` (no auth) for the agent to use as a connectivity check before attempting registration.

---

### Connectivity Validation

The backend verifies it can receive data from the agent. The UI polls `GET /api/v1/clusters/{id}/status` every 15–30 seconds, showing "waiting for agent connection". Simple interval polling is used — no WebSockets or SSE needed for a one-time wait of 30–120 seconds.

---

### Execution Permission Validation

After the agent connects, the backend verifies the agent has the Kubernetes RBAC permissions it needs. The agent lists its own ClusterRole and confirms all required verbs are present for all resource types. This prevents silent failures later where collection appears to start but returns empty results due to missing permissions.

---

### Validate Read Permissions

The agent confirms it can list and watch: nodes, pods, deployments, statefulsets, daemonsets, PVCs, PDBs, HPAs. If any permission is missing, the backend surfaces a specific missing-permission error to the operator with the exact `kubectl apply` command to fix it. "Missing permissions" errors that say "RBAC error" without identifying the missing verb create support tickets — specific errors do not.

---

### Validate Execution Permissions

The agent confirms it can write node labels and taints (`PATCH nodes`). These are the only write operations Phase 4 performs on the cluster. No Deployment or StatefulSet spec write permissions are needed or checked — Phase 4 never patches workload specs.

---

### Validate Rollback Permissions

The agent confirms it can cordon and uncordon nodes (`PATCH nodes/spec.unschedulable`). This is required for the drain-and-recover execution path in Phase 4. An uncordon call is always issued automatically on any drain step failure to prevent nodes being left permanently in an unschedulable state.

---

### Store Cluster Metadata

On receipt of the first valid snapshot from the agent, the backend writes to four persistent stores and sets `onboarding_status = COMPLETE`.

---

### Cluster Inventory

Stores current cluster state: all nodes with their instance types, AZs, lifecycle labels (spot/on-demand), and Karpenter NodePool membership. Source: `node_snapshots` table.

---

### Node Inventory

Per-node detailed state: allocatable CPU and memory, current taints, readiness condition, Karpenter NodeClaim association. Source: `node_snapshots` table.

---

### Region Metadata

AWS region, availability zones in use, and instance type catalog for the customer's region. Used by the savings estimator and feasibility checks in Phase 2. AZ availability varies per AWS account — not all accounts have the same AZs active in a region.

---

### Kubernetes Metadata

Cluster version, detected components (Karpenter present, KEDA present, ArgoCD present, Flux present, Istio present). These flags gate which collection and execution paths are active for this cluster. Stored in `cluster_meta` JSONB column. If a component is not detected, its collection paths are skipped rather than failing.

---

### Platform Database

PostgreSQL, managed by Alembic migrations. Three tables after Phase 0: `customers`, `clusters`, `cluster_tokens`. Redis is used for STS credential caching and pricing data caching — never as durable storage. If Redis goes down, the platform re-fetches credentials from the source rather than losing data.

---

### Cluster Active

`clusters.onboarding_status = COMPLETE`. The account collector Celery task (Phase 1 Layer 3) is enabled for this cluster. The global pricing collector runs regardless of onboarding state — it is shared across all customers.

---

### Begin Metrics Collection

Phase 1 data collection pipeline starts for this cluster. The agent is already running — it begins POSTing snapshots every 60 seconds. The backend's snapshot ingest API starts receiving, validating, and storing them.

---

## PHASE 1 — DATA COLLECTION PIPELINE

---

### BalanceKube Agent (DaemonSet + Controller)

Two distinct workloads deployed by a single Helm chart. The Agent Controller (Deployment) handles K8s API collection and snapshot assembly. The Agent DaemonSet (per-node) handles metrics from the Kubelet Summary API and IMDS polling. They share nothing at runtime — the Controller does not communicate with DaemonSet pods. Both report independently to the backend.

**Hard rule:** No Phase 2, Phase 3, or Phase 4 engine ever calls the Kubernetes API or AWS API directly. They read exclusively from assembled snapshots. The agent and backend collectors are the only components that touch external APIs.

---

### Cluster Inventory Collection

The Agent Controller builds a complete in-memory view of the cluster by issuing paginated LIST calls for all resource types on startup, then switching to Watch streams for delta updates.

**Pagination pattern:** `v1.list_node(limit=100)` — loop on `metadata.continue` token until absent. Same for pods (`limit=500`). Record the final `resourceVersion` from the last page — this is the cursor for the Watch stream. Log `NODE_LIST_COMPLETE count=N rv=XXXXX` when done. The Watch loop does not start until this log is emitted.

**Watch loop:** `watch.Watch().stream(v1.list_node, resource_version=rv, timeout_seconds=300)`. The 5-minute timeout is intentional — forces a reconnect which refreshes server-side state. On `BOOKMARK` events: save the updated `resourceVersion`. On `410 Gone` (expired resourceVersion): fall back to a full paginated LIST to rebuild state, then resume Watch — logged as `WATCH_REBASE`. On any other error (EOF, network drop): sleep 2 seconds, reconnect from last known `rv`. The in-memory NodeMap is **never dropped on reconnect** — it is the source of truth.

---

### Nodes

Per node, extracted with `.get()` and `None` defaults (some labels absent on non-Karpenter nodes):

- `node.metadata.name`
- `node.metadata.labels["node.kubernetes.io/instance-type"]`
- `node.metadata.labels["topology.kubernetes.io/zone"]`
- `node.metadata.labels["karpenter.sh/capacity-type"]` (spot or on-demand)
- `node.metadata.labels["karpenter.sh/nodepool"]`
- `node.status.allocatable["cpu"]` and `["memory"]`
- `node.status.conditions` (Ready state)
- `node.spec.taints`
- `node.metadata.labels["eks.amazonaws.com/nodegroup"]`

A missing label is recorded as `None`, not treated as an error. Never `KeyError` on label access.

---

### Pods

All pods in all namespaces, `Running` phase only. `Pending`, `Succeeded`, and `Failed` pods are excluded — they do not consume node resources and are not relevant to placement decisions.

**Workload grouping (critical — do not skip):** Pods are not sent one-per-pod. Walk `pod.metadata.owner_references` to find the top-level controller. A pod owned by a ReplicaSet walks up to the Deployment. Group by `(namespace, controller_kind, controller_name)`. The backend receives one `WorkloadSnapshot` per controller. A 5000-pod cluster sends a manageable number of workload records.

**Controller object fetch required:** after grouping pods, fetch each unique controller object (Deployment, StatefulSet, DaemonSet) via the K8s API to read its `metadata.resourceVersion` and `status` fields. Cache controller objects within the snapshot loop — do not re-fetch the same controller for every pod that belongs to it.

**`active_rolling_update` flag:** set `true` when `status.updatedReplicas != status.replicas` (Deployment/StatefulSet) or `status.updatedNumberScheduled != status.desiredNumberScheduled` (DaemonSet). Phase 4 reads this flag before every drain step and blocks execution for workloads mid-rollout.

Per-pod fields extracted before grouping: `cpu_request`, `mem_request`, `cpu_limit`, `mem_limit` per container (summed across containers), `pod.spec.affinity`, `pod.spec.topologySpreadConstraints`, `pod.spec.nodeSelector`, `pod.spec.tolerations`. These scheduling constraints are stored and read back by Phase 4 — never modified by BalanceKube.

---

### Deployments

Controller metadata: name, namespace, `spec.replicas`, `status.availableReplicas`, `status.updatedReplicas`. `active_rolling_update` is `true` when `status.updatedReplicas != status.replicas` at collection time.

---

### StatefulSets

Same fields as Deployments plus: `spec.volumeClaimTemplates` presence (indicates persistent storage that may be zone-locked), ordered pod management policy. StatefulSets are treated differently by Phase 2 — drain steps are generated per-replica sequentially, never in parallel.

---

### DaemonSets

Name, namespace, `status.numberAvailable`, `status.desiredNumberScheduled`. DaemonSet pods are collected and grouped like any other workload, but Phase 2's eligibility engine handles them differently — they are never candidates for drain-based spot migration because DaemonSet pods are node-scoped and not interchangeable.

---

### PVCs

`spec.storageClassName`, `spec.volumeName`, `metadata.labels["topology.kubernetes.io/zone"]` if present.

**Zone-locking:** EBS-backed PVCs are zone-locked — a pod with an EBS PVC can only run in the AZ where the volume was created. Phase 2 uses this to set `zone_locked_pvc = true`. Phase 4 uses it to constrain NodeClaim provisioning to the correct AZ (Phase 4 intent source P6). A workload with a zone-locked PVC becomes `ELIGIBLE_WITH_CONDITIONS` rather than `ELIGIBLE`.

---

### PDBs

`spec.selector`, `spec.minAvailable`, `spec.maxUnavailable`, `status.currentHealthy`, `status.disruptionsAllowed`.

Phase 2 uses `disruptionsAllowed == 0` as a hard eligibility block. Phase 4 uses the Kubernetes Eviction API (not force-delete) when draining — the API returns `429 Too Many Requests` if a drain eviction would violate the PDB. Phase 4 waits 30 seconds and retries rather than bypassing the PDB. A PDB is a real safety contract and is never overridden.

---

### Namespaces

Full namespace list used to populate `never_touch_namespaces` enforcement. Namespaces such as `kube-system`, `monitoring`, `cert-manager` are listed in the cluster template — Phase 4 generates zero execution steps for workloads in these namespaces.

---

### Labels

All workload and node labels collected. These are the primary signal for tag generation in Phase 2. Labels with known semantics read explicitly: `app`, `app.kubernetes.io/name`, `app.kubernetes.io/component`, `tier`, `environment`.

**Important:** the `criticality` and `tier=critical` label are explicitly **not** used to infer business criticality. Labels are inconsistent across teams — one team's `criticality=high` is another team's `tier=prod`. Business criticality is always set by the operator at review time, never inferred from labels.

---

### Annotations

All workload annotations collected. BalanceKube writes its own structured annotations (`balancekube.io/*`) to workload objects — Phase 3 reads these back. ArgoCD annotations (`argocd.argoproj.io/*`), Helm annotations (`meta.helm.sh/*`), and Flux annotations are read to populate the CD ownership map.

---

### Affinity Rules

`spec.template.spec.affinity` (nodeAffinity, podAffinity, podAntiAffinity) per workload. Phase 2 records these as informational signals. Phase 4 reads developer-written affinity and treats it as READ ONLY — if a developer's nodeAffinity conflicts with the group's placement intent, it becomes an `INTENT_CONFLICT` block that surfaces to the operator rather than being silently overridden. BalanceKube never modifies a workload's affinity spec.

---

### Taints and Tolerations

Node taints read from node objects. Pod tolerations read from pod specs. Phase 4 writes `balancekube.io/critical-only=true:NoSchedule` taints to reserved on-demand nodes to prevent spot-eligible workloads from landing there. Phase 4 reads existing tolerations and carries them forward to NodeClaim selection — a pod with a spot-only toleration must not be placed on OD-only nodes.

---

### Metrics Collection

The Agent DaemonSet on each node calls the Kubelet Summary API at `https://{NODE_IP}:10250/stats/summary` every 60 seconds. This gives actual CPU and memory usage per pod, per container — not just requests and limits. The DaemonSet authenticates using the node's own service account token with the `nodes/stats` permission.

---

### Kubelet Summary API

Returns `usageCoreNanoSeconds` (cumulative CPU) and `workingSetBytes` (memory) per pod. The DaemonSet computes a CPU rate from consecutive readings. Memory is read directly as working set — this excludes file cache and gives a realistic view of actual memory pressure.

**Fallback:** if the Kubelet Summary API is unavailable on a node, that node's metrics are marked as unavailable and the snapshot is sent with null metrics. This does not block the snapshot — Phase 2 handles null metrics via `data_maturity = INSUFFICIENT`. Collection continues on all other nodes.

---

### Metrics Server

If a Metrics Server is installed, the Agent Controller queries it via `metrics.k8s.io/v1beta1` as an alternative source. Metrics Server data is lower resolution but more broadly available. The two sources are not merged — Kubelet Summary API data (from the DaemonSet) is preferred. Metrics Server data is used only when Kubelet data is unavailable for a workload.

---

### CPU Usage, Memory Usage, Network Usage, Filesystem Usage

CPU: rate in millicores computed from cumulative `usageCoreNanoSeconds`. Memory: `workingSetBytes` in MiB. Network and filesystem: collected per-pod and included in the snapshot for Phase 2's analysis engines. All metrics feed the workload profiler (Phase 1 backend) which computes rolling P50/P95 over 7 days.

---

### Cluster Event Collection

The Agent Controller watches the Kubernetes Events API for events relevant to Spot operations. Warning-type events collected per pod: `OOMKilled`, `BackOff`, `FailedScheduling`, `Evicted`, `SpotInterrupted`. Repeated `OOMKilled` events feed into Phase 2's memory analysis (indicates under-provisioned memory).

---

### Spot Termination Notices

The DaemonSet polls IMDS every 5 seconds for `http://169.254.169.254/latest/meta-data/spot/termination-time`. HTTP 404 = no notice (normal). HTTP 200 = ITN received. Immediately POSTs to `POST /api/v1/itn` with `{node_name, instance_id, termination_time, detected_at}`.

**2-minute window:** AWS gives 2 minutes from ITN to actual termination. The DaemonSet must detect and report within 2 seconds to give Phase 4's ITN handler the remaining ~110-second window to act. This is a hard SLA, not a best-effort target. Using a pre-established connection pool for the POST is required to meet it.

---

### Node Conditions

Node conditions (`Ready`, `MemoryPressure`, `DiskPressure`, `PIDPressure`, `NetworkUnavailable`) collected from `node.status.conditions` in the Watch stream. A node that transitions to `NotReady` triggers a Phase 3 `NODE_COMPOSITION` drift event if the node was part of an active plan.

---

### Pod Conditions

Pod conditions (`Ready`, `ContainersReady`, `PodScheduled`, `Initialized`) included in pod snapshots. Phase 3's `PLACEMENT_MISMATCH` detection requires a pod to have been `Running` for over 15 minutes before a mismatch is counted — this prevents false positives during normal pod startup.

---

### Kubernetes Events

Warning-type events collected: `OOMKilled`, `BackOff`, `FailedScheduling`, `Evicted`. These feed Phase 2's resource analysis and Phase 3's drift detection. An `OOMKilled` event on a workload that is `RIGHT_SIZED` for memory indicates memory spikes that P95 alone does not capture.

---

### Pricing Collection Worker

A central Celery beat task running on the BalanceKube backend — not in the customer's cluster. This is Layer 1 (Global) data — collected once and shared across all customers. Runs every 15 minutes for spot prices, daily for on-demand prices and interruption rates. One Celery task per region, running in parallel — never serialised across regions.

---

### AWS Pricing API

**Spot prices:** `ec2.describe_spot_price_history(InstanceTypes=[...], StartTime=now()-15min, MaxResults=1000)`. Must paginate on `NextToken`. After DB write: Redis keys updated in pipeline — `SET price:{instance_type}:{az} {spot_price} EX 600` — all keys for a region in one round trip.

**On-demand prices:** bulk JSON file downloaded from `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/{region}/index.json` daily. This is faster and more reliable than paginating the Pricing API (which returns 100 results per page over 500+ pages per region). The bulk file is publicly accessible — no IAM required.

**AWS throttling:** wrapped in `tenacity.retry` with `wait_random_exponential(min=1, max=30)` and `stop_after_attempt(5)`. Jitter prevents synchronised retries across multiple regional tasks hitting the same account rate limit simultaneously.

---

### On Demand Prices, Spot Prices, Instance Catalog

Spot prices stored in `global_pricing`: `(instance_type, az, region, spot_price, captured_at)`. On-demand in `od_pricing`: `(instance_type, region, od_price_usd, updated_at)` — one row per type per region, upserted on each daily refresh. Instance catalog (vCPU count, memory GiB, instance family) in `instance_metadata` — used by Phase 4's feasibility check.

---

### Spot Risk Collection Worker

A separate Celery beat task running daily. Fetches the AWS Spot Advisor JSON from `https://spot-price.s3.amazonaws.com/spot.js` — a static JSONP file. Strips the JSONP wrapper before JSON parsing.

**Important caveat:** Spot Advisor data is per-region, not per-AZ, and is historical — not real-time. It must only be used as an informational risk signal, not as a hard scheduling input. A `stable` vs `volatile` label on a node pool is useful context for the operator. It is not a guarantee of future interruption rates.

---

### AWS Spot Advisor

Returns interruption frequency band per instance type per region (0–4, mapping to `<5%`, `5–10%`, `10–15%`, `15–20%`, `>20%`). Stored as a float midpoint in `interruption_rates`. Used in Phase 4 for node pool labels (`stable` if rate < 10%, `volatile` if >= 10%).

**Stale fallback:** if the fetch fails, the previous value is retained — Redis TTL is 86400s. The pipeline does not fail on a stale interruption rate. Logged as `IRATE_FETCH_FAILED` but not alerted — a stale interruption rate is acceptable for an informational signal.

---

### Metadata Collection Worker

Runs at cluster connection time and then daily. Uses the STS assumed role for the customer's account. Collects which AZs are active for the customer's account in their configured region (AZ availability varies per account), and instance metadata (vCPU count, memory) for each instance type in use.

---

### Snapshot Assembly

A Celery task triggered immediately when the backend receives a snapshot POST from the Agent Controller. Joins the three data layers into a single `assembled_snapshot` row.

**The join:** `node_snapshots` (Layer 2 — from agent) + `node_enrichment` (Layer 3 — from account collector) + `global_pricing` (Layer 1 — from Redis/Postgres). This is a LEFT JOIN — if Layer 3 enrichment is not yet available for some nodes, assembly proceeds with those fields null. Assembly never blocks on enrichment.

After writing to `assembled_snapshots`: publishes `cluster.collected.{cluster_id}` on NATS. Phase 2 subscribes to this event.

**Hard rule:** No Phase 2, Phase 3, or Phase 4 engine ever queries `node_snapshots` or `workload_snapshots` directly. They all read from `assembled_snapshots`. This keeps the intelligence layer independently testable.

---

### assembled_snapshots

Postgres table: `(cluster_id, snapshot_at, payload JSONB)`. Retained 7 days — this is the audit trail and replay source. All subsequent intelligence reads from this table.

---

### cluster.collected Event

NATS topic `cluster.collected.{cluster_id}`. Published by the backend's snapshot assembly task after each `assembled_snapshot` is written. Phase 2 subscribes and triggers a new analysis cycle on receipt.

---

## PHASE 2 — WORKLOAD INTELLIGENCE ENGINE

---

### cluster.collected Event

Phase 2 subscribes to `cluster.collected.{cluster_id}`. On receipt, it loads the assembled snapshot for this cluster and begins the analysis pipeline. Phase 2 makes **zero** K8s or AWS API calls. Every byte of input comes from Phase 1 tables.

---

### Load Assembled Snapshot

Read the most recent `assembled_snapshots` row for this cluster. Extract the full workload and node inventory, pricing data, and cluster metadata. This single read is the only data source for all Phase 2 engines — no additional DB queries are made during analysis.

---

### Review State Check

Before running analysis, Phase 2 checks whether all workloads in the snapshot have been through operator review. A workload with `review_status = 'pending_review'` in `workload_config` means the operator has not yet confirmed the classification is correct.

**Key design decision:** analysis always runs — even during pending review. Customers see rightsizing data, eligibility verdicts, and savings estimates immediately after connecting. Only Phase 3 planning is blocked until confirmation. This avoids the "everything frozen until all workloads are reviewed" onboarding problem.

---

### First Optimisation Cycle? (Decision)

If this is the first time Phase 2 has run for this cluster: all workloads are new and all need review. The operator sees the complete workload list grouped by namespace with auto-detected classifications.

If not the first cycle: check for workloads in the snapshot that have no `workload_config` row. These are workloads deployed since the last cycle. Only these new workloads need review.

---

### Generate Initial Workload Review

`run_classification_preview()` runs the type detection logic only (no utilisation analysis — not enough data yet). Produces for each workload: detected type, `is_java` flag, replica count, `hpa_managed`, and a plain-English reason string for why each type was assigned.

`workload_config` rows are created for every workload with `review_status = 'pending_review'`. Analysis continues so the operator sees data immediately. Only Phase 3 planning is blocked.

---

### pending_review

The state all new workloads enter. Visible in the UI as "Needs Review". The operator reviews auto-detected classifications and can:
- Confirm the classification as correct
- Override `workload_type` if wrong
- Set `workload_purpose` (WEB, API, WORKER, BATCH, DATABASE, CACHE, QUEUE, STREAMING, MONITORING, SECURITY, SYSTEM, ML, GPU)
- Set `business_criticality` (CRITICAL, IMPORTANT, STANDARD) — the **only** field Phase 2 never guesses. Criticality is always operator-set.
- Assign to an `application_group` (required for Phase 3/4)
- Set `excluded = true` to exclude from all analysis permanently

---

### Operator Validation

The operator reviews classifications at the review screen. Touching any field via `PATCH /api/v1/workloads/{id}/config` implicitly sets `review_status = confirmed` — operator intent is authoritative. The `workload_purpose` and `business_criticality` fields are the primary fields for unknown workloads.

---

### Review Complete

`workload_config.review_status = 'confirmed'`. The workload is eligible to proceed through Phase 3 planning.

---

### Check For New Workloads

On subsequent cycles, Phase 2 checks for workloads in the current snapshot that have no `workload_config` row. Only these new workloads enter the pending_review queue. Existing confirmed workloads continue through analysis uninterrupted.

---

### New Workloads Detected? (Decision)

If new workloads: create `workload_config` rows for them with `pending_review`, notify the operator. Existing confirmed workloads are unaffected.

If no new workloads: all workloads already have `workload_config` rows. Continue directly to analysis.

---

### Continue Analysis

All workloads with `review_status = 'confirmed'` and not in `workload_exclusions` proceed through E1A (classification and tagging) and E1B (utilisation and rightsizing). Excluded workloads are skipped entirely — no rows written to any analysis table for them.

---

### E1A Metadata Collection

Phase 2 assembles a metadata bundle for each workload from the assembled snapshot. No inference happens here — only collection.

Collected: Kubernetes kind (`controller_kind`), all labels, all annotations, namespace, PVC presence and zone-locking, service type, network profile, historical utilisation percentiles (P50/P95 CPU and memory from `workload_profiles`), restart count and last restart time, scheduling constraints (nodeSelector, tolerations, affinity rules).

---

### Tag Generation

The Tag Generation Engine transforms the metadata bundle into a set of semantic tags. Tags are not mutually exclusive — a Redis StatefulSet gets `stateful`, `cache`, and `database` simultaneously. Each tag has a deterministic detection rule and a `tag_source` that records exactly how it was assigned. No confidence scores on tags — a tag is either present or absent.

**Detection rules:**

| Tag | Detection Method | tag_source |
|-----|-----------------|-----------|
| `stateless` | Deployment kind, no PVC, no sticky session labels | `kind_detection` |
| `stateful` | StatefulSet kind OR `has_pvc = true` | `kind_detection` / `pvc_detection` |
| `batch` | CronJob kind OR active batch spike | `kind_detection` |
| `database` | Image substring: postgres, mysql, mongo, cassandra, etc. | `image_detection` |
| `cache` | Image substring: redis, memcached, dragonfly | `image_detection` |
| `queue` | Image substring: rabbitmq, activemq, nats, pulsar | `image_detection` |
| `streaming` | Image substring: kafka, redpanda | `image_detection` |
| `ai_ml` | Image substring: pytorch, tensorflow, ray, triton | `image_detection` |
| `gpu` | Resource request: `nvidia.com/gpu` or `amd.com/gpu` | `resource_detection` |
| `monitoring` | Image/namespace: prometheus, grafana, loki, alertmanager | `image_detection` |
| `system` | Namespace: kube-system, cert-manager, ingress-nginx | `namespace_detection` |
| `critical` | Operator sets `business_criticality = CRITICAL` only | `operator` |
| `unknown` | No other tag matched | escalate to operator review |

**The `critical` tag is never inferred from labels.** Labels like `criticality=high` or `tier=critical` are unreliable and inconsistent across teams. The engine reads them for awareness but never uses them to set the `critical` tag. Business criticality is an explicit operator decision made at review time.

**Image detection reliability:** Image substring matching works well for standard images (`postgres:14`, `redis:7-alpine`). It does not reliably detect:
- Distroless Java images with no `java` in the name
- Custom JVM builds
- Renamed private registry images (e.g. `internal.registry.io/our-redis-fork`)

For these cases, the workload falls through to `unknown` and is escalated to the operator. This is correct behaviour — a false `database` tag on an unrecognised workload is worse than an escalation. The engine does not guess.

**`workload_tags` rows** are deleted and re-inserted on every analysis cycle — no stale tags accumulate. One row per tag per workload.

---

### Workload Classification

After tagging, each workload is assigned a `workload_type` using a priority-ordered rule. If `workload_config.workload_type_override` is set, that override is used (`workload_type_source = 'operator_override'`) and auto-detection is skipped entirely.

Auto-detection priority order (first match wins):

1. `DAEMON` — DaemonSet kind
2. `STATEFUL` — StatefulSet kind
3. `BATCH` — CronJob kind OR `is_batch_spike == true`
4. `WEB` — Deployment AND `hpa_managed == true`
5. `WORKER` — Deployment AND `hpa_managed == false`

---

### Store workload_tags

One row per tag per workload. Rows are deleted and re-inserted on every cycle — never accumulate stale tags from prior cycles. The `tag_source` column records exactly how each tag was assigned, making every classification fully auditable.

---

### E1B Resource Analysis

Reads `workload_tags` and the assembled snapshot's utilisation data. Computes CPU and memory states, data maturity, and rightsizing recommendations.

---

### Java Detection

Check container image names and environment variable names. Either match → `is_java = true`.

**Image name substrings checked (case-insensitive):** `java`, `jdk`, `jre`, `openjdk`, `corretto`, `temurin`, `eclipse-temurin`, `graalvm`, `azul`, `zulu`.

**Environment variable names checked:** `JAVA_OPTS`, `JVM_OPTS`, `JAVA_TOOL_OPTIONS`, `JAVA_HOME`.

**What this detection misses:** Distroless Java images (e.g. `gcr.io/distroless/java`), Spring Native / GraalVM native images (no JVM at all), custom renamed images. For these cases, `is_java` is `false` and the workload follows normal data maturity rules. This is acceptable — `is_java` only affects `data_maturity`. The consequence of a missed Java detection is that a Java workload reaches `MATURE` at 7 days rather than being conservatively capped at `SUFFICIENT` until 7 days. The risk is small and the alternative (guessing Java from heuristics) creates false positives.

**`is_java` affects only data_maturity — never eligibility.** A 3-replica Java service with HPA is perfectly Spot-eligible. Java is a sizing concern, not a stability concern.

**Why Java needs different data maturity treatment:** JVM workloads in the first days after deployment show atypical CPU behaviour. Class loading at startup, JIT compilation warming up, initial GC pauses, and heap sizing self-adjustment all produce CPU readings that are not representative of steady-state. A P95 computed from day-1 readings of a JVM workload can be off by 3–5x compared to a P95 from day-7 onwards. Capping at `SUFFICIENT` until 7 days of data exist avoids acting on unrepresentative profiles. After 7 days, Java follows normal rules with no special treatment.

---

### Batch Detection

A workload is `is_batch_spike = true` if its current replica count exceeds 3× the P50 replica count from the 7-day `workload_metrics` history.

**Implementation:**
1. Query `workload_metrics` for `max(replica_count)` over the last 30 minutes for this workload.
2. Compute `p50_replica_count` from `workload_metrics` over the last 7 days using a Postgres percentile window function. Do this in SQL, not Python.
3. **Zero-guard:** if `p50_replica_count IS NULL` or `== 0`, set `is_batch_spike = false` and return. A CronJob between runs normally has 0 replicas — dividing by zero or marking every scale-out as a spike would be incorrect.
4. Spike check: `is_batch_spike = (recent_max >= 3 × p50_replica_count)`.

If `is_batch_spike = true`: assign `workload_type = BATCH`, `data_maturity = INSUFFICIENT`. Analysis still runs and produces a result. `INSUFFICIENT` data_maturity is the signal to Phase 3 not to act — no separate "paused" state is needed.

---

### CPU Analysis

`cpu_util_ratio = p95_cpu_usage / cpu_request` (from `workload_profiles`).

| State | Condition |
|-------|-----------|
| `THROTTLED` | `p95_usage > cpu_request` (CFS throttle or ratio > 1.0) |
| `OVER_PROVISIONED` | ratio < 0.25 (using less than 25% of requested CPU) |
| `RIGHT_SIZED` | ratio between 0.25 and 0.80 |
| `UNDER_PROVISIONED` | ratio > 0.80 |

`THROTTLED` is a hard block in the eligibility engine. The workload already has a compute problem — adding Spot preemption on top of a throttled workload makes a bad situation worse. The correct fix is to increase the CPU request, not to place it on cheaper nodes.

---

### Memory Analysis

`mem_util_ratio = p95_mem_usage / mem_request`.

| State | Condition |
|-------|-----------|
| `OVER_PROVISIONED` | ratio < 0.40 |
| `RIGHT_SIZED` | ratio between 0.40 and 0.85 |
| `UNDER_PROVISIONED` | ratio > 0.85 |

Memory has no `THROTTLED` state — Kubernetes OOMKills pods rather than throttling memory. Memory thresholds are more conservative than CPU (0.40 vs 0.25) because memory spikes are harder to predict from P95 alone and an OOM kill causes an immediate pod restart.

---

### Network Analysis

Checks for high cross-node or cross-AZ network traffic patterns. If a workload has significant network egress and belongs to a group with `latency_sensitive = true`, this is passed through to Phase 4 as a constraint for AZ-scoped node provisioning. No blocking decisions are made in Phase 2 based on network alone — network analysis is informational at this stage.

---

### Storage Analysis

Checks for PVC usage patterns. If a PVC is zone-locked (EBS-backed), sets `zone_locked_pvc = true` on the workload snapshot. This becomes `COND A` in the eligibility engine — the workload is `ELIGIBLE_WITH_CONDITIONS` and Phase 4 must provision nodes in the same AZ as the PVC.

---

### Data Maturity Analysis

A deterministic, rule-based assessment of how much historical data exists. Not a score. Not a confidence value.

| State | Conditions | Phase 3 Behaviour |
|-------|-----------|-------------------|
| `MATURE` | ≥7 days data AND >100 data points AND `is_batch_spike == false` AND (not Java OR Java with >7 days data) | Full analysis trusted. Phase 3 proceeds normally. |
| `SUFFICIENT` | 3–7 days data, OR Java with <7 days data, OR 1–2 resolved batch spikes in last 24h | Analysis used with care. Phase 3 proceeds but applies conservative node selection. |
| `INSUFFICIENT` | <3 days data, OR `is_batch_spike == true` (active spike right now) | Phase 3 does not act. Workload stays on current nodes until data matures. |

**Why not "confidence"?** The word "confidence" implies ML scoring and invites "why is it 72%?" questions. `data_maturity` is explicit: it describes the age and completeness of available metrics. The rules are fixed and enumerated — no explanation beyond the table above is needed.

---

### workload_analysis

Written at the end of E1B. One row per workload, upserted on every cycle. Contains `workload_type`, `is_java`, `is_batch_spike`, `cpu_util_ratio`, `mem_util_ratio`, `cpu_state`, `mem_state`, `data_maturity`, `cpu_recommendation_m`, `mem_recommendation_mib`, `recommendation_reason`.

Also contains three identity fields that Phase 3 and Phase 4 use to detect stale plans:
- `snapshot_id` — which assembled_snapshot this analysis was built from.
- `analysis_version` — increments each cycle. Phase 3 detects stale plans by comparing the version in the plan against the current version.
- `cluster_hash` — SHA-256 of the cluster topology at analysis time. Inputs to the hash: sorted set of distinct instance_type × AZ pairs. **Not** node counts, workloads, PVCs, or replica counts — including those would invalidate plans constantly on HPA scaling or deployments.

---

### Placement Eligibility Engine

Reads `workload_tags` and `workload_analysis` for each workload. Produces a verdict: `ELIGIBLE`, `ELIGIBLE_WITH_CONDITIONS`, or `NOT_ELIGIBLE`. No scores. No weights. Fully deterministic rules with human-readable `decision_reasons`.

---

### Operator Overrides

Checked before any rules run:
- `spot_eligible_override = false` → immediately `NOT_ELIGIBLE`, reason `"operator_excluded"`. Skip all rules.
- `spot_eligible_override = true` → skips the conditions check but **hard blocks still run**. If a hard block fires, the override is ignored. An operator who overrides to `true` is saying "I've handled the conditions" — not "ignore the single-replica safety rule".
- `spot_eligible_override = null` → run normal rules.

---

### Hard Block Rules

Three rules. Any one fires → `NOT_ELIGIBLE`, no further checks.

**BLOCK 1 — Single replica:** `replica_count == 1 AND workload_type != DAEMON`. A single replica hit by a Spot ITN means a full service outage with zero tolerance window. DaemonSets are excluded — losing one DaemonSet pod during Spot reclaim is expected and handled by the DaemonSet controller.

**BLOCK 2 — PDB blocks all disruption:** `has_pdb == true AND pdb_max_unavailable == 0 AND pdb_min_available == replica_count`. The PDB literally prevents any eviction. A Spot ITN will cause the node to hang in `Terminating` indefinitely waiting for a pod eviction that the PDB will never allow. This is a real production failure mode, not a theoretical concern.

**BLOCK 3 — Workload throttled:** `cpu_state == THROTTLED`. This workload already has a compute problem. Adding Spot preemption on top of a throttled workload makes a bad situation worse. The fix is to increase the CPU request. Once right-sized, the workload will likely become eligible.

---

### Conditional Rules

No hard block fired → check conditions. Any condition present → `ELIGIBLE_WITH_CONDITIONS`. Phase 3 records the conditions and Phase 4 must respect them.

**COND A** — `zone_locked_pvc == true`: Phase 4 must provision nodes in the same AZ as the PVC. EBS volumes cannot be attached across AZs.

**COND B** — `workload_type == STATEFUL AND replica_count >= 2`: Phase 4 must use sequential per-replica drain, not full-node drain. StatefulSet pods have identity and ordered shutdown matters for quorum-based systems.

**COND C** — `is_batch_spike == true`: Phase 4 must not drain this workload's nodes during the active spike window. The job is at peak load.

**COND D** — `workload_type == BATCH AND hpa_managed == false`: Phase 4 must ensure node capacity exists before the batch job starts rather than relying on scale-out after an ITN.

**COND E** — `workload_type == STATEFUL AND image matches kafka, elasticsearch, redis, mongodb, cassandra, postgres, mysql`: Phase 4 must use operational health gates before draining any member. These data-tier StatefulSets may require quorum checks, minimum ISR verification (Kafka), or replica lag validation (Postgres/MySQL) before drain.

If no conditions apply and no hard blocks fired → `ELIGIBLE`.

---

### Decision Reasons

Every verdict is stored with a `decision_reasons JSONB` list — an ordered list of human-readable facts. Example for `NOT_ELIGIBLE`:

```json
["✗ replica_count == 1", "✗ tagged stateful", "→ Fix: scale to >=2 replicas"]
```

Example for `ELIGIBLE`:

```json
["✓ tagged stateless", "✓ replica_count >= 3", "✓ pdb exists with headroom", "✓ hpa_managed"]
```

The operator sees exactly which rules fired. No "why is it 83?" questions are possible.

**Positive signals are always computed, even for blocked workloads.** A throttled workload that also has `multi_replica` and `hpa_managed` shows those signals alongside the block reason, with the message: "Fix CPU throttling and this workload would be eligible." This gives the operator actionable context, not just a red X.

---

### Eligibility Verdict

Written to `workload_placement_eligibility`. One row per workload, upserted. Fields: `verdict`, `eligibility_source`, `block_reason`, `conditions JSONB`, `decision_reasons JSONB`, `positive_signals JSONB`.

---

### Savings Estimator

Runs only for `ELIGIBLE` and `ELIGIBLE_WITH_CONDITIONS` workloads. All numbers explicitly labelled "Potential Savings Estimate" — never presented as a commitment or guarantee.

**Current cost baseline:** `current_monthly_cost = od_price_hourly × 24 × 30 × node_count`. On-demand price is always used as the baseline even if the node is already on Spot — OD is the correct comparison point.

**Spot cost:** cheapest fitting Spot instance type from `global_pricing` for the workload's AZ. Uses rightsized CPU/memory recommendations if available, otherwise current requests. If no Spot price found for this instance type in this AZ: `savings_estimate_available = false`. The UI shows "pricing unavailable" rather than zero.

**Pricing freshness:** if `global_pricing.captured_at` is older than 60 minutes, `pricing_freshness = 'STALE_PRICING'`. The UI shows a warning: "Pricing data is stale — estimate may be inaccurate." This prevents decisions based on hours-old spot prices.

---

### Recommendation Store

The four analysis tables (`workload_analysis`, `workload_placement_eligibility`, `workload_savings`, `workload_tags`) collectively form the recommendation store. Also includes `application_group_definitions` and `workload_config`.

---

### cluster.analysed Event

NATS topic `cluster.analysed.{cluster_id}`. Published after all Phase 2 engines complete and write their results. Phase 3 subscribes to this event. The payload includes `snapshot_id`, `analysis_version`, and `cluster_hash`.

---

## PHASE 3 — DRIFT DETECTION ENGINE

---

### cluster.analysed Event

Phase 3 subscribes to `cluster.analysed.{cluster_id}`. On receipt, it loads the recommendation from Phase 2 tables and begins the drift detection loop.

**Phase 3 reads exclusively from Phase 1 + Phase 2 tables.** The only K8s API calls Phase 3 makes are writes: patching node labels/taints and pod annotations.

**Design principle:** Kubernetes is the scheduler, not BalanceKube. Phase 3 writes scheduling intent as standard Kubernetes objects (labels, taints, annotations). The kube-scheduler or Karpenter reads these and makes placement decisions. ArgoCD syncs, HPA scale-outs, and rollouts all work normally because they speak the same K8s API that Phase 3's annotations target.

---

### Load Recommendation

Read `workload_analysis`, `workload_placement_eligibility`, and `workload_savings` for this cluster. These are the Phase 2 outputs — the planned state. Also load `application_group_definitions` and `workload_config` for the current group topology.

---

### Load Planned Snapshot

Read the `assembled_snapshot` that corresponds to `workload_analysis.snapshot_id`. This is the exact cluster state Phase 2 analysed against. Phase 3 compares current state against this baseline — not against a hypothetical ideal.

---

### snapshot_id, analysis_version, cluster_hash

The three identity fields that define plan validity. Phase 3 reads these from `plan_baselines`. If the current `cluster_hash` has diverged from the baseline hash, the plan is structurally invalid and Phase 2 re-analysis is triggered. If only `analysis_version` has advanced, a Plan Delta may be sufficient.

---

### Current Cluster State

The most recent `assembled_snapshot` for this cluster. Phase 3 reads exclusively from this table — it does not call the K8s API for workload enumeration.

---

### Generate Current Snapshot

Load the most recent assembled_snapshot. Extract current node inventory, workload placements, resource profiles, and PDB/HPA states. This is compared against the planned snapshot across two distinct planes.

---

### Snapshot Comparator

Compares planned snapshot against current snapshot across two planes:

**Plane 1 — Node Layout:** Planned node inventory vs current node inventory. Dimensions: instance type, AZ, capacity type (spot/on-demand), nodepool membership, node count per type, allocatable CPU/memory totals. Feeds classifier D2 (NODE_COMPOSITION).

**Plane 2 — Workload Placement:** Planned workload-to-node assignments vs actual pod placement in current snapshot. Dimensions: workload → node_type mapping, spot vs on-demand assignment per workload, AZ distribution, CPU/memory profile delta vs plan baseline, replica count vs plan headroom. Feeds classifiers D1 (WORKLOAD_LEVEL) and D3 (PLACEMENT_MISMATCH).

Keeping the planes separate prevents mis-classifying a patchable Plane 1 change as a full re-analysis trigger.

---

### Current State vs Planned State

The comparison anchor is always "what did Phase 2 plan?" vs "what is actually running now?" — not "what is the ideal state?" vs "what is running?". The plan is the baseline, not a theoretical ideal.

---

### Node Level Diff

Detects changes to the node inventory since the plan was created.

---

### Node Added

A new node appears in the current snapshot not in the planned snapshot. Not always a drift event — Karpenter scaling in response to load is expected. Becomes a `NODE_COMPOSITION` drift event only if:
- The new node changes total allocatable CPU by more than 20% from the plan baseline, or
- It came from an AWS managed node group not yet in BalanceKube's tracked inventory.

---

### Node Removed

A node present in the planned snapshot is now missing or `NotReady` for more than 10 minutes. If this node was part of an active plan, triggers `NODE_COMPOSITION` drift and re-analysis.

---

### Node Type Changed

A node's instance type label has changed (rare, but possible during managed node group updates). Triggers `NODE_COMPOSITION` drift.

---

### Pod Level Diff

Detects changes to workload placement and configuration.

---

### New Workload

A workload appears in the current snapshot with no `workload_config` row. Triggers Phase 2 to generate a partial review for the new workload. The existing plan is not blocked — only the new workload is held in `pending_review`.

---

### Workload Removed

A workload in the plan no longer appears in the current snapshot. If it was part of an active migration plan, that plan's steps for this workload are marked `SKIPPED_WORKLOAD_REMOVED`. The plan continues for remaining workloads.

---

### Replica Count Changed

Current replica count differs from the planned replica count. If within normal HPA operating range (below P95 historical replica count): minor drift event — plan is patched with updated headroom calculations. HPA-driven replica changes are tagged `drift_source=hpa` and **do not count toward the drift score**. Only persistent structural changes count.

If it exceeds the P95 replica count and pods are Pending: becomes `REPLICA_SPIKE` (CRITICAL).

---

### PVC Attached

A PVC is newly attached to a workload that previously had none. This changes the workload's zone-locking status and invalidates any plan that assumed the workload was freely movable. Triggers Phase 2 re-analysis for this workload.

---

### Resource Diff

Detects changes to workload resource profiles since the plan was created.

---

### CPU Profile Changed

`cpu_request` or `cpu_util_ratio` changed beyond threshold:
- ±20% → `WORKLOAD_LEVEL` WARN
- ±50% → CRITICAL

Cooldown: 30 minutes between consecutive events for the same workload to suppress noise. On CRITICAL: triggers Phase 2 re-analysis for the affected workload.

---

### Memory Profile Changed

`mem_request` or `mem_util_ratio` changed beyond threshold:
- ±25% → WARN
- ±60% → CRITICAL

Memory threshold is tighter than CPU because memory pressure directly causes OOM kills, not just performance degradation.

---

### Storage Profile Changed

New PVC attached, PVC storage class changed, or zone-lock status changed. Always triggers Phase 2 re-analysis for the affected workload — storage constraints affect placement feasibility in a binary way and cannot be patched.

---

### Configuration Diff

Detects changes to Kubernetes policy objects that affect placement safety.

---

### PDB Changed

A PDB's `minAvailable` or `maxUnavailable` changed since the plan was created. If the change reduces eviction headroom to zero, the affected workload is set to `NOT_ELIGIBLE` and Phase 2 re-analysis is queued.

---

### HPA Changed

An HPA's `minReplicas` or `maxReplicas` changed. If `minReplicas` dropped to 1, the workload may now hit the single-replica hard block and Phase 2 re-analysis is queued.

---

### Criticality Changed

`workload_config.business_criticality` changed by the operator since the last plan. Triggers Phase 2 re-analysis — criticality affects eligibility and Phase 4 group placement assignments.

---

### Purpose Changed

`workload_config.workload_purpose` changed by the operator. Triggers Phase 2 re-analysis — purpose drives tag generation and eligibility.

---

### Impact Analysis

For each diff event, Phase 3 determines severity (WARN, CRITICAL) and whether the existing plan can be patched (updated in place) or must be fully rebuilt via Phase 2 re-analysis.

**Six drift types:**
- `WORKLOAD_LEVEL` — resource request drift
- `NODE_COMPOSITION` — node inventory changes
- `PLACEMENT_MISMATCH` — pod on wrong lifecycle class for >15 minutes, not in rolling update, no recent ITN
- `PRICING_SHIFT` — spot price increased >40% in 1 hour for an instance type in the plan
- `REPLICA_SPIKE` — replica count exceeds `max(p95_replicas, 2× p50_replicas)` AND pods are Pending
- `APPLICATION_GROUP_CHANGE` — workload's application group changed since last plan baseline

`OWNERSHIP_CONFLICT` is tracked separately in `deployment_conflicts` — it is a configuration authority dispute, not workload drift. It never enters the drift score.

**PLACEMENT_MISMATCH — detection guard:** a mismatch is only counted when all three are true: (1) pod has been Running on the wrong lifecycle class for >15 minutes, (2) the workload is not in a rolling update window, and (3) no spot interruption event on that node in the last 10 minutes. This eliminates false positives during node upgrades, spot replacements, and rolling deploys.

---

### Patchable? (Decision)

**Patchable (Plan Delta, no Phase 2 re-analysis):**
- Replica count change within normal HPA range
- Spot price shift that does not make spot more expensive than OD
- New node that does not change plan capacity assumptions significantly

**Not patchable (Phase 2 re-analysis triggered):**
- New workload with no classification (requires operator review)
- Storage profile change (zone-lock status changed)
- PDB now blocks all eviction
- Application group topology changed
- Cluster hash mismatch (structural topology change)

---

### Generate Plan Delta

For patchable drift: Phase 3 updates the existing plan's parameters in place — recalculates headroom, updates capacity requirements, adjusts step ordering if needed. The plan remains in `PENDING_APPROVAL` status. The operator receives a notification that the plan was automatically updated.

---

### Update Existing Plan

`recommendation_store` row updated: new `plan_delta_at` timestamp, updated step parameters. No new approval required for minor patches. For moderate patches (step reordering, capacity changes): requires re-acknowledgement but not full re-approval.

---

### Ready For Execution

The plan has passed drift validation, any patches have been applied, and it is in `PENDING_APPROVAL` state. Ready for Phase 4.

---

### Invalidate Recommendation

The current plan cannot be safely executed against the current cluster state. The plan is marked `STALE`. Phase 2 re-analysis is triggered.

---

### Trigger Phase 2 Reanalysis

Publish `cluster.reanalyse.{cluster_id}` on NATS. Phase 2 runs a new analysis cycle. The existing plan remains `STALE` until Phase 2 completes and Phase 3 produces a new valid plan.

---

### Execution Ready

The plan is valid, drift-checked, and waiting for operator approval. NATS event `cluster.drift_detected.{cluster_id}` published. Phase 4 subscribes.

---

## PHASE 4 — EXECUTION ENGINE

---

### Approved Recommendation

Phase 4 is triggered by `cluster.drift_detected.{cluster_id}` from Phase 3. An operator-approved `MigrationPlan` in `APPROVED` status is the gate to execution. Phase 4 never executes without an approved plan — except the ITN emergency path which is pre-approved implicitly at cluster connection time.

**Hard rule — Phase 4 never:**
- Writes to any Deployment, StatefulSet, or DaemonSet spec
- Adds, modifies, or removes developer-written affinity or tolerations
- Creates a NodeClaim when `karpenter_control_mode != 'managed'`
- Bypasses a PDB
- Force-deletes pods
- Leaves a node cordoned on step failure
- Auto-remediates a failed verification

---

### Acquire Cluster Lock

A distributed lock (Redis `SET NX EX`) is acquired for the `cluster_id` before any execution begins. This prevents two concurrent execution runs on the same cluster — which could drain nodes simultaneously in ways that violate the global disruption budget.

---

### Lock Acquired? (Decision)

If the lock is already held: the new run is queued. It will be retried after the current execution completes and the lock is released.

If acquired: proceed to load the recommendation.

---

### Load Recommendation

Load the approved `MigrationPlan` and its `MigrationPlanSteps`. Also load the cluster template for this cluster — the source of truth for group definitions, execution defaults, execution mode, and execution policy (time windows).

**Execution modes:**
- `OBSERVE` — build plan, mark all steps `DRY_RUN`, publish `plan_ready`, stop. No cluster changes.
- `PLAN_ONLY` — build plan, notify operator, stop. Awaits explicit approval.
- `PLAN_AND_EXECUTE` — full execution after approval.

---

### Execution Validation

Seven checks, all pure reads — no K8s calls. Any failure blocks execution for the affected scope.

---

### Validate snapshot_id

The `snapshot_id` in the approved plan matches the `snapshot_id` in the current `workload_analysis`. If they differ, the plan was built against a different cluster state. Return to Phase 3.

---

### Validate analysis_version

The `analysis_version` in the plan matches the current `workload_analysis.analysis_version`. If Phase 2 has run since the plan was approved, the analysis version will have incremented. This catches cases where a Phase 2 cycle ran between plan approval and execution start.

---

### Validate cluster_hash

The `cluster_hash` in the plan matches the current `workload_analysis.cluster_hash`. If the cluster topology changed structurally since the plan was approved, the hash will differ. Return to Phase 3 for re-analysis.

---

### Plan Still Valid? (Decision)

If all three identity fields match: proceed to plan execution.

If any field mismatches: the plan is stale. Return to Phase 3. Phase 3 re-evaluates whether the existing plan can be patched or whether Phase 2 re-analysis is needed.

---

### Generate Execution Plan

Phase 4 generates node-side steps only. Step types: `VERIFY_NODE_CAPACITY`, `CREATE_KARPENTER_NODECLAIM` (conditional), `APPLY_NODE_LABELS`, `APPLY_NODE_TAINT`, `DRAIN_SOURCE_NODE`, `DRAIN_STATEFUL_REPLICA`, `UNCORDON_NODE`, `VERIFICATION`.

The resource_version of each workload is extracted from the assembled snapshot payload at approval time and recorded for the generation recheck (E6.5) between approval and execution. This detects any post-approval deployment before execution begins without requiring live Kubernetes API calls.

**Intent resolution (priority order, first match wins):**
1. `workload_config.placement_intent` set by operator — highest priority
2. `application_group_definitions.placement` (operator manual group)
3. `application_group_definitions.placement` (confirmed template pattern)
4. Developer-written nodeAffinity — READ ONLY. If it conflicts with group placement → `INTENT_CONFLICT` block, surface to operator
5. `topologySpreadConstraints` — READ ONLY, respected in NodeClaim spec
6. PVC zone binding — forces ON_DEMAND for the PVC's AZ
7. `node_selector` / `tolerations` — READ ONLY, carried forward to NodeClaim selection

**Feasibility checks:**
- Per-pod instance fit: does this workload fit in at least one Spot instance type from the pool? If no: `INFEASIBLE_NO_INSTANCE_FIT` → fall back to ON_DEMAND, surface to operator.
- Group total demand vs available capacity: if insufficient → plan includes a `CREATE_KARPENTER_NODECLAIM` step. **Crucially**, before this step can be executed, Phase 4 checks `clusters.karpenter_control_mode`. If it is `observe`, the engine is blocked from creating NodeClaims and execution halts. It must be `managed` for Phase 4 to provision capacity.

**Global execution ordering:** LOW/MEDIUM criticality groups execute first (lower blast radius on failure). HIGH/CRITICAL groups execute last. Never drain two nodes in the same AZ simultaneously. Groups with no shared drain-candidate nodes run concurrently.

**Latency vs HA conflict:** for any group with `criticality = HIGH AND latency_sensitive = true`, these directly conflict — single-AZ reduces HA, multi-AZ increases latency. Plan generation for this group is **blocked** until the operator makes an explicit choice: prioritise latency (single AZ, accept HA risk) or prioritise HA (multi-AZ, accept latency cost). BalanceKube never silently resolves this conflict.

---

### Sign Execution Plan

The execution plan is signed with an HMAC before being sent to the execution agent. This prevents a tampered plan from being accepted — the agent verifies the signature before acting on any step.

---

### Send Execution Plan To Agent

The signed plan is delivered to the Agent Controller. The agent polls for plans — the backend delivers them via the instructions array in the heartbeat HTTP response.

---

### Agent Validate Plan

The Agent Controller verifies the plan signature. If the signature is invalid, the plan is rejected and the backend is notified.

The agent also performs a local pre-execution check: are the nodes referenced in the plan still present and Ready? Is any referenced workload currently in a rolling update? These checks happen immediately before plan execution begins, not just at plan approval time.

---

### Plan Valid? (Decision)

If signature check or local pre-execution checks fail: the agent rejects the plan and notifies the backend. The backend returns to Phase 3.

If valid: the agent creates a rollback snapshot and begins execution.

---

### Agent Create Rollback Snapshot

Before touching anything, the agent snapshots the current state of all nodes and workloads in the plan scope. This snapshot is stored on the backend in `execution_results.state_before`. It is the recovery point for the rollback path.

---

### Agent Provision Capacity

If plan steps require new Spot nodes (`CREATE_KARPENTER_NODECLAIM`): provisioning happens **first**. No workload is drained until target capacity exists and is verified Ready. This is a hard sequencing rule — draining before capacity exists would cause pods to go Pending.

**NodeClaim spec:** built from `cluster_template.node_pool_strategy.spot`. Instance types filtered to those that fit all workloads in the group (checking CPU and memory requests against allocatable capacity minus system reservation of 110m CPU / 1Gi memory). 20% buffer added to total group resource demand.

Requires `clusters.karpenter_control_mode = 'managed'` and a designated `karpenter_nodepool_name`. If either is missing: step marked `FAILED` with `KARPENTER_PERMISSION_MISSING` — not a silent no-op.

Poll NodeClaim status every 10 seconds. Timeout 120 seconds → `FAILED`, dependent steps blocked.

---

### Agent Drain Source Nodes

For each source node hosting workloads being moved: cordon, then evict pods using the Kubernetes Eviction API.

**Why the Eviction API (not force-delete):** the Eviction API respects PDBs. A `429 Too Many Requests` response means the PDB would be violated. Phase 4 waits 30 seconds and retries. If the PDB blocks eviction past `drain_timeout_seconds`, the step is marked `DRAIN_PDB_BLOCKED`, the node is automatically uncordoned, and the issue is surfaced to the operator. **Phase 4 never bypasses a PDB, even under time pressure.**

**Pre-drain delay:** 10 seconds default. Enforced minimum 15 seconds if `cluster_mutators` includes ISTIO — Envoy sidecars need time to stop receiving new connections before the pod is evicted.

**Parallel drain rule:** multiple source nodes can be drained simultaneously only if they are in different AZs AND combined in-flight evictions do not exceed `execution_defaults.max_unavailable_percent`. Never drain two nodes in the same AZ simultaneously — this maintains zone availability during execution.

**Failure handling:** on any drain failure, `UNCORDON_NODE` runs automatically. A cordoned node is never left in an unschedulable state after a failure. This is a hard rule implemented in the step dependency chain, not in catch blocks.

---

### Agent Migrate Workloads

After source nodes are drained, pod controllers see their pods evicted and automatically create replacement pods. Phase 4 prepared the environment (Spot nodes exist, correctly labelled, with sufficient capacity) so the scheduler places new pods on the right nodes. BalanceKube did not touch the Deployment or StatefulSet spec.

**StatefulSets:** handled sequentially. Evict one replica, wait for it to become Running+Ready on the target node (up to 5 minutes), then proceed to the next replica. Each step `depends_on` the previous. Never evict two StatefulSet replicas simultaneously.

---

### Agent Apply Spot Placement

After pod recreation, the Agent Controller writes `balancekube.io/*` labels to the target Spot nodes: `lifecycle`, `tier`, `spot-pool` (stable or volatile based on interruption rate), and `group`. These labels guide future scheduling — when the workload is scaled out by HPA, new pods land on correctly labelled nodes.

Phase 4 writes **only to node objects**. ArgoCD, Flux, and Helm do not manage nodes — there is no ownership conflict.

---

### Agent Health Validation

After workload migration, the agent checks pod health for all workloads in the plan:

- **SPOT group:** at least 75% of pods in group are Running on Spot nodes within 10 minutes. Not 100% — some pods may have landed on OD nodes due to transient resource pressure at scheduling time. These are individually flagged but do not fail the verification.
- **ON_DEMAND group (HIGH/CRITICAL criticality):** zero pods on Spot nodes. Hard check — zero tolerance.
- **MIXED group:** Spot percentage between 40% and 90%.
- **StatefulSet:** all replicas Ready, no pod Pending for more than 5 minutes.

---

### Validation Passed? (Decision)

If verification passes: plan is marked `DONE`. Phase 3's plan baseline is updated with the new clean state. The cycle continues from Phase 1.

If verification fails: the rollback engine activates.

---

### Agent Trigger Rollback

The agent initiates rollback using the state snapshot captured before execution began. Rollback undoes what Phase 4 wrote — node labels and taints, cordons. It does not undo pod placements because pod controllers have already placed pods on new nodes. Rolling back node labels prevents future pods from being guided to those nodes but does not move currently running pods.

---

### Restore Rollback Snapshot

The `state_before` from `execution_results` is applied: node labels and taints restored to pre-execution state. Cordons removed. The cluster is returned to the state it was in before the plan executed.

---

### Recovery Validation

Verifies rollback completed successfully: node labels match pre-execution state, no nodes are still cordoned from the failed plan, all pods that were Running before execution are still Running.

---

### Agent Report Success / Agent Report Rolled Back

The agent reports the final outcome to the backend. The backend writes to `execution_results` with the final status. The outcome (success or rolled back) is surfaced in the UI with the complete audit trail — what changed, when, why, and by whom.

---

### Execution History

`execution_history` and `execution_results` tables form the execution history. Every step's `state_before` and `state_after`, success/failure, error reasons, and verification results are stored. The complete audit trail is always available.

---

### Metrics Feedback

After execution (success or rollback), the Agent Controller sends a fresh snapshot to the backend within 60 seconds. Phase 1 assembles it, Phase 2 analyses it, Phase 3 compares it against the updated baseline. The cycle continues.

---

## COMPLETE END-TO-END FLOW SUMMARY

```
Phase 0: Can we connect to this cluster?
         → STS role, EKS cluster discovery, agent deployment, first snapshot received.

Phase 1: What does the cluster look like right now?
         → Three data layers (global pricing, cluster inventory, account enrichment)
           assembled into one consistent snapshot every 60 seconds.

Phase 2: What should we do?
         → Workloads classified, tagged, assessed for eligibility, savings estimated.
           Operator confirms classifications. Groups assigned.

Phase 3: Is the plan still valid?
         → Drift detection compares current state against plan baseline.
           Patchable drift: plan updated in place.
           Structural drift: Phase 2 re-analysis triggered.

Phase 4: Do it safely.
         → Node-side execution: provision capacity, drain source nodes,
           verify workloads landed correctly. Never touch workload specs.
           Rollback on failure. Always.

Phase 1: Measure results.
         → Fresh snapshot after execution. Cycle repeats.
```