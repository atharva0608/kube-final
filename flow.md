# PHASE 0 — ONBOARDING FLOW

```mermaid
flowchart TD

A[Customer Registration]

A --> B[Create Organization]

B --> C[Generate External ID]

C --> D[Generate CloudFormation Template]

D --> E[Download Template<br>Manual]

E --> F[Deploy CloudFormation Stack<br>Manual]

F --> G[CloudFormation Creates IAM Role]

G --> H[CloudFormation Creates Required Policies]

H --> I[CloudFormation Configures Cross Account Access]

I --> J[Copy IAM Role ARN<br>Manual]

J --> K[Paste Role ARN In UI<br>Manual]

K --> L[Validate AWS Access]

L --> M{Validation Successful?}

M -->|No| N[Display Validation Errors]

M -->|Yes| O[Discover Available Clusters]

O --> P[Display Cluster Inventory]

P --> Q[Select Cluster<br>Manual]

Q --> R[Generate Cluster Registration Token]

R --> S[One Click Agent Installation]

S --> T[Deploy Agent Controller]

S --> U[Deploy Agent DaemonSet]

T --> V[Agent Registration]
U --> V

V --> W[Connectivity Validation]

W --> X[Execution Permission Validation]

X --> Y[Validate Read Permissions]

Y --> Z[Validate Execution Permissions]

Z --> AA[Validate Rollback Permissions]

AA --> AB[Store Cluster Metadata]

AB --> AC[Cluster Inventory]
AB --> AD[Node Inventory]
AB --> AE[Region Metadata]
AB --> AF[Kubernetes Metadata]

AC --> AG[(Platform Database)]
AD --> AG
AE --> AG
AF --> AG

AG --> AH[Cluster Active]

AH --> AI[Begin Metrics Collection]
```

---

# PHASE 1 — DATA COLLECTION PIPELINE

```mermaid
flowchart TD

subgraph Cluster_Specific_Data

A[BalanceKube Agent]

A --> B[Cluster Inventory Collection]

B --> C[Nodes]
B --> D[Pods]
B --> E[Deployments]
B --> F[StatefulSets]
B --> G[DaemonSets]
B --> H[PVCs]
B --> I[PDBs]
B --> J[Namespaces]
B --> K[Labels]
B --> L[Annotations]
B --> M[Affinity Rules]
B --> N[Taints & Tolerations]

A --> O[Metrics Collection]

O --> P[Kubelet Summary API]
O --> Q[Metrics Server]

P --> R[CPU Usage]
P --> S[Memory Usage]
P --> T[Network Usage]
P --> U[Filesystem Usage]

Q --> R
Q --> S
Q --> T
Q --> U

A --> V[Cluster Event Collection]

V --> W[Spot Termination Notices]
V --> X[Node Conditions]
V --> Y[Pod Conditions]
V --> Z[Kubernetes Events]

end

subgraph Global_Platform_Data

AA[Pricing Collection Worker]

AA --> AB[AWS Pricing API]

AB --> AC[On Demand Prices]
AB --> AD[Spot Prices]
AB --> AE[Instance Catalog]

AF[Spot Risk Collection Worker]

AF --> AG[AWS Spot Advisor]

AG --> AH[Interruption Rates]

AH --> AI[Historical Spot Risk Dataset]

AJ[Metadata Collection Worker]

AJ --> AK[Region Metadata]

AJ --> AL[Availability Zone Metadata]

AJ --> AM[Instance Metadata]

end

C --> AN[Snapshot Assembly]
D --> AN
E --> AN
F --> AN
G --> AN
H --> AN
I --> AN
J --> AN
K --> AN
L --> AN
M --> AN
N --> AN

R --> AN
S --> AN
T --> AN
U --> AN

W --> AN
X --> AN
Y --> AN
Z --> AN

AC --> AN
AD --> AN
AE --> AN

AI --> AN

AK --> AN
AL --> AN
AM --> AN

AN --> AO[assembled_snapshots]

AO --> AP[cluster.collected Event]

AP --> AQ[Phase 2]
```

---

# PHASE 2 — WORKLOAD INTELLIGENCE ENGINE

```mermaid
flowchart TD

A[cluster.collected Event]

A --> B[Load Assembled Snapshot]

B --> C[Review State Check]

C --> D{First Optimization Cycle?}

D -->|Yes| E[Generate Initial Workload Review]

E --> F[pending_review]

F --> G[Operator Validation]

G --> H[Review Complete]

D -->|No| I[Check For New Workloads]

I --> J{New Workloads Detected?}

J -->|Yes| K[Generate Partial Review]

K --> L[pending_review]

L --> M[Operator Validation]

M --> H

J -->|No| N[Continue Analysis]

H --> N

N --> O[E1A Metadata Collection]

O --> P[Tag Generation]

P --> Q[Workload Classification]

Q --> R[Store workload_tags]

R --> S[E1B Resource Analysis]

S --> T[Java Detection]
S --> U[Batch Detection]
S --> V[CPU Analysis]
S --> W[Memory Analysis]
S --> X[Network Analysis]
S --> Y[Storage Analysis]
S --> Z[Data Maturity Analysis]

T --> AA[workload_analysis]
U --> AA
V --> AA
W --> AA
X --> AA
Y --> AA
Z --> AA

AA --> AB[Placement Eligibility Engine]

AB --> AC[Operator Overrides]
AB --> AD[Hard Block Rules]
AB --> AE[Conditional Rules]

AC --> AF[Decision Reasons]
AD --> AF
AE --> AF

AF --> AG[Eligibility Verdict]

AG --> AH[Savings Estimator]

AH --> AI[Pricing Freshness Validation]

AI --> AJ[(Recommendation Store)]

AJ --> AK[snapshot_id]
AJ --> AL[analysis_version]
AJ --> AM[cluster_hash]
AJ --> AN[decision_reasons]
AJ --> AO[savings_estimate]

AO --> AP[cluster.analysed Event]
```

---

# PHASE 3 — DRIFT DETECTION ENGINE

```mermaid
flowchart TD

A[cluster.analysed Event]

A --> B[Load Recommendation]

B --> C[Load Planned Snapshot]

C --> D[snapshot_id]
C --> E[analysis_version]
C --> F[cluster_hash]

G[Current Cluster State]

G --> H[Generate Current Snapshot]

D --> I[Snapshot Comparator]
E --> I
F --> I
H --> I

I --> J[Current State vs Planned State]

J --> K[Node Level Diff]
J --> L[Pod Level Diff]
J --> M[Resource Diff]
J --> N[Configuration Diff]

K --> O[Node Added]
K --> P[Node Removed]
K --> Q[Node Type Changed]

L --> R[New Workload]
L --> S[Workload Removed]
L --> T[Replica Count Changed]
L --> U[PVC Attached]

M --> V[CPU Profile Changed]
M --> W[Memory Profile Changed]
M --> X[Storage Profile Changed]

N --> Y[PDB Changed]
N --> Z[HPA Changed]
N --> AA[Criticality Changed]
N --> AB[Purpose Changed]

O --> AC[Impact Analysis]
P --> AC
Q --> AC
R --> AC
S --> AC
T --> AC
U --> AC
V --> AC
W --> AC
X --> AC
Y --> AC
Z --> AC
AA --> AC
AB --> AC

AC --> AD{Patchable?}

AD -->|Yes| AE[Generate Plan Delta]

AE --> AF[Update Existing Plan]

AF --> AG[Ready For Execution]

AD -->|No| AH[Invalidate Recommendation]

AH --> AI[Trigger Phase 2 Reanalysis]

AI --> AJ[Phase 2]

AG --> AK[Execution Ready]
```

---

# PHASE 4 — EXECUTION ENGINE

```mermaid
flowchart TD

A[Approved Recommendation]

A --> B[Acquire Cluster Lock]

B --> C{Lock Acquired?}

C -->|No| D[Queue Execution]

C -->|Yes| E[Load Recommendation]

E --> F[Execution Validation]

F --> G[Validate snapshot_id]
F --> H[Validate analysis_version]
F --> I[Validate cluster_hash]

G --> J
H --> J
I --> J

J{Plan Still Valid?}

J -->|No| K[Return To Phase 3]

J -->|Yes| L[Generate Execution Plan]

L --> M[Sign Execution Plan]

M --> N[Agent Polls Heartbeat]

N --> O[Backend Delivers Execution Plan]

O --> P[Agent Validate Plan]

P --> Q{Plan Valid?}

Q -->|No| R[Reject Execution]

R --> K

Q -->|Yes| S[Agent Create Rollback Snapshot]

S --> T[Agent Provision Capacity]

T --> U[Agent Drain Source Nodes]

U --> V[Agent Migrate Workloads]

V --> W[Agent Apply Spot Placement]

W --> X[Agent Health Validation]

X --> Y{Validation Passed?}

Y -->|Yes| Z[Agent Report Success]

Y -->|No| AA[Agent Trigger Rollback]

AA --> AB[Restore Rollback Snapshot]

AB --> AC[Recovery Validation]

AC --> AD[Agent Report Rolled Back]

Z --> AE[(Execution History)]

AD --> AE

AE --> AF[Phase 1]
```

---

# COMPLETE END-TO-END BALANCEKUBE FLOW

```mermaid
flowchart LR

P0[Phase 0<br>Onboarding]

P1[Phase 1<br>Data Collection]

P2[Phase 2<br>Workload Intelligence]

P3[Phase 3<br>Drift Detection]

P4[Phase 4<br>Execution Planning]

AG[Agent<br>Execution Engine]

P0 --> P1

P1 --> Snapshots[(assembled_snapshots)]

Snapshots --> P2

P2 --> Recommendations[(Recommendation Store)]

Recommendations --> P3

P3 -->|Patch Plan| P4

P3 -->|Reanalyse| P2

P4 --> AG

AG --> Cluster[Kubernetes Cluster]

Cluster --> P1

AG --> Execution[(Execution History)]

Execution --> P1
```