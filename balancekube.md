# BalanceKube — Master Project Plan & Execution Reference

> **Version:** 1.0.0  
> **Status:** Active Development  
> **Architecture:** Monorepo — Backend · Frontend · Workers · Agent · Infrastructure · Shared  
> **Pipeline:** Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → (loop back to Phase 1)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [End-to-End Data Flow](#3-end-to-end-data-flow)
4. [Repository Structure](#4-repository-structure)
5. [Feature Domains](#5-feature-domains)
6. [Repository Ownership Map](#6-repository-ownership-map)
7. [Phase 0 — Onboarding](#7-phase-0--onboarding)
8. [Phase 1 — Data Collection Pipeline](#8-phase-1--data-collection-pipeline)
9. [Phase 2 — Workload Intelligence Engine](#9-phase-2--workload-intelligence-engine)
10. [Phase 3 — Drift Detection Engine](#10-phase-3--drift-detection-engine)
11. [Phase 4 — Execution Engine](#11-phase-4--execution-engine)
12. [Core Engines](#12-core-engines)
13. [State Machines](#13-state-machines)
14. [Versioning Strategy](#14-versioning-strategy)
15. [Backend Module Reference](#15-backend-module-reference)
16. [Frontend Module Reference](#16-frontend-module-reference)
17. [Workers Module Reference](#17-workers-module-reference)
18. [Agent Module Reference](#18-agent-module-reference)
19. [Infrastructure Module Reference](#19-infrastructure-module-reference)
20. [Shared Module Reference](#20-shared-module-reference)
21. [Database Schema Overview](#21-database-schema-overview)
22. [Data Model Relationships](#22-data-model-relationships)
23. [Database Ownership](#23-database-ownership)
24. [Event Catalog](#24-event-catalog)
25. [Failure Handling Matrix](#25-failure-handling-matrix)
26. [Security Model](#26-security-model)
27. [API Surface](#27-api-surface)
28. [Testing Strategy](#28-testing-strategy)
29. [Deployment & Scripts](#29-deployment--scripts)
30. [Cross-Cutting Concerns](#30-cross-cutting-concerns)
31. [Folder Documentation Standard](#31-folder-documentation-standard)
32. [Agent Lifecycle Management](#32-agent-lifecycle-management)
33. [Decision Log & Design Rationale](#33-decision-log--design-rationale)

---

## 1. Project Overview

BalanceKube is an automated Kubernetes cost-optimisation and workload placement platform. It connects to customer AWS accounts via cross-account IAM roles, deploys a lightweight in-cluster agent (DaemonSet + Controller), continuously collects cluster state and metrics, classifies every workload using a multi-signal intelligence engine, generates Spot placement recommendations with savings estimates, detects drift between the planned and live state, and executes approved node migrations with full rollback capability.

### Core Value Proposition

| Problem | BalanceKube Solution |
|---|---|
| Kubernetes Spot savings require expert placement decisions | Automated multi-signal classification and eligibility engine |
| Spot interruptions risk workload stability | Interruption-rate dataset, PDB awareness, health validation |
| Cluster state drifts after recommendations are generated | Continuous drift detection with patchable plan deltas |
| Manual node drains are risky and slow | Orchestrated execution engine with rollback snapshots |
| Savings are invisible until realised | Per-workload savings estimates persisted in recommendation store |

### Guiding Principles

- **Safety first** — every execution path has a rollback. No destructive action proceeds without a valid `snapshot_id`, `analysis_version`, and `cluster_hash` triplet.
- **Operator in the loop** — the first optimisation cycle always requires human review before analysis continues. New workloads gate on the same review workflow.
- **Immutable snapshots** — assembled snapshots are never mutated after assembly; drift detection works by comparing a new current snapshot against the stored planned snapshot.
- **Event-driven pipeline** — phases communicate exclusively through domain events (`cluster.collected`, `cluster.analysed`), not direct function calls, enabling retry and replay.
- **Stable event contracts** — every domain event has a versioned payload schema and a standard envelope. Consumers use `schema_version` and tolerate unknown extra fields to support safe evolution.
- **Consistency through hashing** — `cluster_hash` is derived from the stable topology (node types, counts, AZ distribution) so any structural change invalidates stale recommendations automatically.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Customer AWS Account                                                    │
│                                                                          │
│  ┌────────────────────────────────────────────┐                         │
│  │  Kubernetes Cluster                         │                         │
│  │                                             │                         │
│  │  ┌─────────────────┐  ┌──────────────────┐ │                         │
│  │  │ Agent Controller │  │  Agent DaemonSet  │ │                         │
│  │  │ (1 replica)      │  │  (1 per node)     │ │                         │
│  │  └────────┬─────────┘  └────────┬─────────┘ │                         │
│  │           │                     │            │                         │
│  └───────────┼─────────────────────┼────────────┘                         │
│              │  Kubernetes API      │  Kubelet API                         │
│  ┌───────────▼─────────────────────▼────────────┐                         │
│  │  IAM Role (cross-account)  ←  CloudFormation  │                         │
│  └──────────────────────────────┬────────────────┘                         │
│                                 │ AssumeRole                               │
└─────────────────────────────────┼────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼────────────────────────────────────────┐
│  BalanceKube Platform (SaaS)                                              │
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                │
│  │ Backend  │  │ Workers  │  │ Frontend │  │  Agent   │                │
│  │  (API)   │  │ (Queue)  │  │  (UI)    │  │ Gateway  │                │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └────┬─────┘                │
│       │              │                            │                       │
│  ┌────▼──────────────▼────────────────────────────▼────┐                │
│  │                  Platform Database                    │                │
│  │  assembled_snapshots · recommendation_store           │                │
│  │  execution_history · workload_tags · audit_logs       │                │
│  └───────────────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack (Intended)

| Layer | Technology |
|---|---|
| Backend API | Node.js / TypeScript (Express or Fastify) |
| Workers | Node.js / TypeScript (BullMQ or similar queue) |
| Frontend | React / TypeScript (Vite) |
| Agent | Go (controller-runtime for Kubernetes operator pattern) |
| Database | PostgreSQL (primary), Redis (cache / queue broker) |
| Infrastructure | Terraform (AWS), Helm (Kubernetes agent deployment) |
| Events | Internal event bus (Redis Streams or PostgreSQL LISTEN/NOTIFY) |

---

## 3. End-to-End Data Flow

```
Customer Registration
       │
       ▼
Phase 0 — Onboarding
  Customer Registration → Create Org → Generate External ID →
  Generate CloudFormation Template → Deploy Stack (manual) →
  IAM Role Created → Copy Role ARN → Validate Access →
  Discover Clusters → Select Cluster → Generate Token →
  One-Click Agent Install → Agent Registration →
  Connectivity + K8s Validation → Cluster Active
       │
       ▼
Phase 1 — Data Collection  [repeating loop every N minutes]
  Agent collects: K8s API objects + Kubelet/Metrics Server metrics +
  AWS Pricing APIs + AWS Spot Advisor interruption rates →
  Snapshot Assembly → assembled_snapshots → cluster.collected event
       │
       ▼
Phase 2 — Workload Intelligence Engine
  Load snapshot → Review state check →
  [First cycle: Generate Initial Review → Operator Validation]
  [Subsequent: Check for new workloads → Partial review if needed]
  → E1A Metadata / Tag Generation / Workload Classification →
  E1B Resource Analysis (Java, Batch, CPU, Memory, Network, Storage) →
  Placement Eligibility Engine (Hard rules, Conditional rules, Overrides) →
  Savings Estimator → Recommendation Store → cluster.analysed event
       │
       ▼
Phase 3 — Drift Detection Engine
  Load recommendation → Load planned snapshot →
  Generate current snapshot → Snapshot Comparator →
  Node Diff + Pod Diff + Resource Diff + Configuration Diff →
  Impact Analysis →
  [Patchable?] → Yes: Generate Plan Delta → Update Plan → Execution Ready
               → No:  Invalidate Recommendation → Trigger Phase 2 Reanalysis
       │
       ▼
Phase 4 — Execution Engine
  Approved Recommendation → Acquire Cluster Lock →
  Load Recommendation → Execution Validation (snapshot_id + analysis_version + cluster_hash) →
  Create Rollback Snapshot → Generate Execution Plan →
  Provision Capacity → Drain Source Nodes → Migrate Workloads →
  Apply Spot Placement → Health Validation →
  [Pass] → Mark Success → Execution History → Metrics Feedback → Phase 1
  [Fail] → Rollback Engine → Restore Snapshot → Recovery Validation → Mark Rolled Back
```

### Key Data Artefacts and Their Lifecycle

| Artefact | Created In | Consumed In | Mutability |
|---|---|---|---|
| `assembled_snapshots` | Phase 1 | Phase 2, Phase 3 | Immutable after assembly |
| `workload_tags` | Phase 2 (E1A) | Phase 2 (E1B), Phase 3 | Versioned |
| `workload_analysis` | Phase 2 (E1B) | Eligibility Engine | Per analysis_version |
| `recommendation_store` | Phase 2 | Phase 3, Phase 4 | Versioned by analysis_version |
| `plan_delta` | Phase 3 | Phase 4 | Replaces prior plan if patchable |
| `rollback_snapshot` | Phase 4 | Phase 4 Rollback | Immutable; deleted after success |
| `execution_history` | Phase 4 | Phase 1 (feedback) | Append-only |

---

## 4. Repository Structure

```
balancekube/
├── backend/                  # REST API server — all business logic endpoints
│   ├── onboarding/           # Customer registration, org creation, CF template, IAM validation
│   ├── cluster_inventory/    # Cluster discovery, registration, metadata storage
│   │   ├── nodes/            # Node inventory CRUD and queries
│   │   ├── pods/             # Pod inventory CRUD and queries
│   │   ├── deployments/      # Deployment inventory
│   │   ├── statefulsets/     # StatefulSet inventory
│   │   ├── daemonsets/       # DaemonSet inventory
│   │   ├── pvc/              # PersistentVolumeClaim inventory
│   │   ├── pdb/              # PodDisruptionBudget inventory
│   │   ├── namespaces/       # Namespace inventory
│   │   ├── labels/           # Label index and search
│   │   ├── affinity/         # Affinity rule storage
│   │   └── taints/           # Taint and toleration storage
│   ├── metrics_collection/   # Metrics ingestion and storage
│   │   ├── kubelet_metrics/  # Kubelet Summary API data
│   │   ├── metrics_server/   # Metrics Server aggregated data
│   │   ├── cpu/              # CPU time-series storage
│   │   ├── memory/           # Memory time-series storage
│   │   ├── network/          # Network usage storage
│   │   ├── filesystem/       # Filesystem usage storage
│   │   └── normalization/    # Metric normalisation and unit conversion
│   ├── pricing_collection/   # AWS pricing data ingestion
│   │   ├── on_demand/        # On-demand price storage
│   │   ├── spot_price/       # Spot price history
│   │   ├── instance_catalog/ # Instance type catalogue (vCPU, RAM, network)
│   │   └── normalization/    # Price normalisation ($/hr → $/month, per vCPU)
│   ├── spot_risk_collection/ # Spot interruption risk data
│   │   ├── aws_spot_advisor/ # Spot Advisor API integration
│   │   ├── interruption_rates/ # Per-instance interruption rate storage
│   │   ├── historical_dataset/ # Historical risk dataset management
│   │   └── risk_normalization/ # Risk score normalisation (0–10 scale)
│   ├── snapshot_assembly/    # Phase 1 output: assembled_snapshots builder
│   ├── workload_review/      # Review state management (pending_review, operator validation)
│   ├── workload_classification/ # Phase 2 E1A — tag generation and workload classification
│   │   ├── tag_generation/   # Primary tag generation logic
│   │   ├── java_detection/   # JVM workload detection heuristics
│   │   ├── batch_detection/  # Batch / cron workload detection
│   │   ├── stateful_detection/ # Stateful workload detection (PVC attachment)
│   │   ├── database_detection/ # Database workload detection
│   │   ├── cache_detection/  # Cache workload detection (Redis, Memcached patterns)
│   │   ├── queue_detection/  # Queue consumer detection
│   │   ├── monitoring_detection/ # Observability workload detection
│   │   └── unknown_detection/ # Fallback classifier for unlabelled workloads
│   ├── resource_analysis/    # Phase 2 E1B — per-workload resource profiling
│   │   ├── cpu/              # CPU request/limit vs actual usage analysis
│   │   ├── memory/           # Memory request/limit vs actual, OOM risk
│   │   ├── network/          # Network bandwidth and latency profile
│   │   └── storage/          # PVC usage patterns, IOPS estimation
│   ├── eligibility_engine/   # Placement eligibility verdict engine
│   │   ├── hard_rules/       # Absolute blockers (e.g. stateful with no PDB)
│   │   ├── conditional_rules/ # Soft rules that produce warnings
│   │   └── operator_overrides/ # Manual overrides stored and applied here
│   ├── recommendations/      # Recommendation store management and savings estimation
│   ├── drift_detection/      # Phase 3 — snapshot comparison and plan invalidation
│   │   ├── snapshot_comparator/ # Core diff algorithm
│   │   ├── node_diff/        # Node-level change detection
│   │   ├── pod_diff/         # Pod-level change detection
│   │   ├── resource_diff/    # Resource profile change detection
│   │   ├── configuration_diff/ # Configuration change detection (PDB, HPA, criticality)
│   │   ├── impact_analysis/  # Determines patchability of detected changes
│   │   ├── plan_delta/       # Generates delta patches for patchable drift
│   │   └── reanalysis/       # Triggers Phase 2 reanalysis when plan is invalidated
│   ├── execution/            # Phase 4 — execution engine
│   │   ├── lock_manager/     # Cluster lock acquisition and release
│   │   ├── plan_validation/  # Validates snapshot_id, analysis_version, cluster_hash
│   │   ├── capacity_provisioning/ # New Spot node provisioning
│   │   ├── node_drain/       # Safe node drain orchestration
│   │   ├── workload_migration/ # Pod rescheduling and migration
│   │   ├── spot_placement/   # Spot placement configuration application
│   │   ├── health_validation/ # Post-migration health checks
│   │   └── execution_history/ # Execution record persistence
│   ├── rollback/             # Rollback snapshot creation and restoration
│   ├── agent_management/     # Agent token rotation, heartbeat tracking, upgrades
│   ├── users/                # User CRUD, authentication
│   ├── organizations/        # Organisation CRUD, multi-tenancy
│   ├── notifications/        # Notification delivery (email, Slack, webhook)
│   ├── audit_logs/           # Append-only audit log writer
│   ├── events/               # Domain event publisher and subscriber
│   ├── database/             # DB connection pool, migrations, query helpers
│   └── common/               # Shared backend utilities (error types, middleware, etc.)
│
├── frontend/                 # React SPA — operator UI
│   ├── onboarding/           # Registration wizard, CloudFormation download, ARN paste UI
│   ├── cluster_inventory/    # Cluster list, node/pod/workload inventory views
│   ├── metrics_collection/   # Metrics visualisation dashboards
│   ├── pricing_collection/   # Pricing data browser
│   ├── spot_risk_collection/ # Spot risk visualisation per instance type
│   ├── snapshot_assembly/    # Snapshot history browser
│   ├── workload_review/      # Review queue UI — operator validation workflow
│   ├── workload_classification/ # Workload tag and classification viewer
│   ├── resource_analysis/    # Per-workload resource profile viewer
│   ├── eligibility_engine/   # Eligibility verdict browser with decision reasons
│   ├── recommendations/      # Recommendation dashboard, savings summary
│   ├── drift_detection/      # Drift status panel, plan delta viewer
│   ├── execution/            # Execution approval, progress, history
│   ├── rollback/             # Rollback status and history
│   ├── agent_management/     # Agent status, token management
│   ├── clusters/             # Cluster settings and metadata
│   ├── settings/             # Organisation and user settings
│   ├── audit_logs/           # Audit log viewer
│   └── shared/               # Design system: components, hooks, API client, types
│
├── workers/                  # Background job processors
│   ├── onboarding/           # Async onboarding jobs (CF validation, cluster discovery)
│   ├── cluster_inventory/    # Periodic cluster inventory refresh
│   ├── metrics_collection/   # Metrics ingestion job
│   ├── pricing_collection/   # AWS pricing refresh job (daily)
│   ├── spot_risk_collection/ # Spot Advisor scrape job (hourly)
│   ├── snapshot_assembly/    # assembled_snapshots builder job
│   ├── workload_review/      # Review notification dispatch
│   ├── workload_classification/ # Tag generation and classification job
│   ├── resource_analysis/    # Resource analysis job
│   ├── eligibility_engine/   # Eligibility computation job
│   ├── recommendations/      # Recommendation generation and savings estimation job
│   ├── drift_detection/      # Drift detection scheduled job
│   ├── execution/            # Execution orchestration job
│   ├── rollback/             # Rollback execution job
│   ├── notifications/        # Notification dispatch job
│   └── common/               # Worker base classes, retry logic, dead-letter handling
│
├── agent/                    # In-cluster Go agent (DaemonSet + Controller)
│   ├── controller/           # Controller manager — reconciliation loops
│   ├── registration/         # Initial agent registration with platform
│   ├── heartbeat/            # Periodic heartbeat to confirm liveness
│   ├── upgrades/             # Agent self-upgrade mechanism
│   ├── token_rotation/       # Registration token rotation
│   ├── cluster_inventory/    # Kubernetes API collection (nodes, pods, etc.)
│   ├── metrics_collection/   # Kubelet Summary API + Metrics Server scraping
│   ├── event_stream/         # Pushes collected data to platform API
│   └── health_reporting/     # Reports own health and cluster health status
│
├── infrastructure/           # Terraform + Helm infrastructure definitions
│   ├── onboarding/           # CloudFormation template generation logic
│   ├── cluster_inventory/    # Infrastructure for inventory storage
│   ├── metrics_collection/   # Timeseries storage infrastructure
│   ├── pricing_collection/   # Pricing data storage
│   ├── spot_risk_collection/ # Risk data storage
│   ├── snapshot_assembly/    # Snapshot storage (S3 or DB blob)
│   ├── workload_review/      # Review queue infrastructure
│   ├── workload_classification/ # Classification job infrastructure
│   ├── resource_analysis/    # Analysis job infrastructure
│   ├── eligibility_engine/   # Eligibility engine infrastructure
│   ├── recommendations/      # Recommendation store infrastructure
│   ├── drift_detection/      # Drift detection scheduler infrastructure
│   ├── execution/            # Execution engine infrastructure
│   ├── rollback/             # Rollback snapshot storage infrastructure
│   ├── aws/                  # AWS provider config, IAM policies, VPC
│   ├── kubernetes/           # Helm chart for agent deployment
│   └── monitoring/           # Prometheus, Grafana, alerting rules
│
├── shared/                   # Cross-module shared libraries
│   ├── aws/                  # AWS SDK wrappers (STS, EC2, CloudFormation, Pricing)
│   ├── kubernetes/           # Kubernetes client wrappers
│   ├── pricing/              # Pricing calculation helpers
│   ├── events/               # Event type definitions and publisher interface
│   ├── logging/              # Structured logging configuration
│   ├── security/             # JWT, encryption, secrets management
│   ├── validation/           # Input validation schemas (Zod / Joi)
│   └── constants/            # System-wide constants and enums
│
├── docs/                     # Documentation (this file lives here conceptually)
├── scripts/                  # Developer scripts: seed, migrate, deploy, test
└── tests/                    # Integration and e2e test suites
```

---

## 5. Feature Domains

The repository is organised around **feature domains**, not pipeline phases. Each domain has a clear owner, a defined set of responsibilities, and maps to one or more folders across the monorepo. When a developer is assigned to a feature, this table tells them exactly where to work.

| Domain | Description | Primary Phase |
|---|---|---|
| **Onboarding** | Customer registration, org creation, CloudFormation template, IAM validation, cluster discovery, agent installation | Phase 0 |
| **Cluster Inventory** | Kubernetes resource collection, inventory storage, and serving (nodes, pods, deployments, etc.) | Phase 1 |
| **Metrics Collection** | Kubelet/Metrics Server scraping, ingestion, normalisation, and time-series storage | Phase 1 |
| **Pricing Collection** | AWS on-demand and Spot pricing ingestion, instance catalogue, normalisation | Phase 1 |
| **Spot Risk Collection** | Spot Advisor interruption rate scraping, risk scoring, historical dataset | Phase 1 |
| **Snapshot Assembly** | Combines all Phase 1 sources into a single immutable `assembled_snapshot` | Phase 1 |
| **Workload Review** | Operator review gate — pending_review state, review queue UI, completion workflow | Phase 2 |
| **Workload Classification** | Tag generation and workload type detection (Java, Batch, Stateful, Database, Cache, Queue, Monitoring) | Phase 2 |
| **Resource Analysis** | Per-workload CPU, memory, network, and storage profiling from metric history | Phase 2 |
| **Eligibility Engine** | Hard rules, conditional rules, operator overrides — produces per-workload Spot eligibility verdict | Phase 2 |
| **Recommendations** | Savings estimation, recommendation store lifecycle, approval workflow | Phase 2 |
| **Drift Detection** | Snapshot comparison, change classification, plan delta generation, reanalysis triggering | Phase 3 |
| **Execution** | Cluster lock, plan validation, capacity provisioning, node drain, workload migration, health validation | Phase 4 |
| **Rollback** | Rollback snapshot creation, restoration sequence, recovery validation | Phase 4 |
| **Agent Management** | Agent registration, heartbeat tracking, token rotation, upgrade orchestration | Cross-cutting |

---

## 6. Repository Ownership Map

This table shows which monorepo layer is responsible for each feature domain. A `✓` means that layer has material code for the domain. Use this as your starting point when locating where to make a change.

| Feature Domain | `backend/` | `frontend/` | `workers/` | `agent/` | `infrastructure/` | `shared/` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Onboarding | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Cluster Inventory | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Metrics Collection | ✓ | ✓ | ✓ | ✓ | ✓ | |
| Pricing Collection | ✓ | | ✓ | | ✓ | ✓ |
| Spot Risk Collection | ✓ | | ✓ | | ✓ | |
| Snapshot Assembly | ✓ | | ✓ | | ✓ | |
| Workload Review | ✓ | ✓ | ✓ | | | |
| Workload Classification | ✓ | ✓ | ✓ | | ✓ | |
| Resource Analysis | ✓ | ✓ | ✓ | | ✓ | |
| Eligibility Engine | ✓ | ✓ | ✓ | | ✓ | |
| Recommendations | ✓ | ✓ | ✓ | | ✓ | ✓ |
| Drift Detection | ✓ | ✓ | ✓ | | ✓ | |
| Execution | ✓ | ✓ | ✓ | | ✓ | ✓ |
| Rollback | ✓ | ✓ | ✓ | | ✓ | |
| Agent Management | ✓ | ✓ | | ✓ | ✓ | ✓ |

### Layer Responsibilities at a Glance

**`backend/`** — The authoritative source of business logic. Owns all database writes. Exposes the REST API. Every domain has a backend sub-module.

**`frontend/`** — Operator UI. Reads from backend API only. Contains no business logic; all decisions are delegated to backend. Owns the design system in `frontend/shared/`.

**`workers/`** — Background job processors. Consumes events and queues. Calls backend services or shared libraries. Never exposes HTTP. Owns retry logic and dead-letter handling.

**`agent/`** — In-cluster Go binary. Read-only access to the customer cluster. Pushes data to the platform API. Has no direct database access.

**`infrastructure/`** — Terraform + Helm definitions. One sub-folder per domain where infrastructure differs. Does not contain application logic.

**`shared/`** — Cross-layer libraries. No domain-specific business logic. Must be usable by backend, workers, and agent (Go: separate shared package in `agent/`).

---

## 7. Phase 0 — Onboarding

### Purpose

Establish a trusted cross-account IAM relationship between the customer's AWS account and the BalanceKube platform, deploy the in-cluster agent, and bring the first cluster to `Active` status.

### Step-by-Step Flow

#### Step 1 — Customer Registration
- Operator creates an account at the BalanceKube web UI.
- Backend creates a `User` record and a linked `Organization` record.
- An `external_id` is generated (UUID v4) — this is stored against the organisation and used as the `ExternalId` condition in the IAM trust policy to prevent confused deputy attacks.

#### Step 2 — CloudFormation Template Generation
- Backend generates a parameterised CloudFormation template containing:
  - An **IAM Role** with `sts:AssumeRole` trust to the BalanceKube platform account, locked to the `external_id` condition.
  - An **IAM Policy** granting read access to EC2, EKS, pricing APIs, and Spot Advisor endpoints.
  - A **cross-account access configuration** that restricts the role to the minimum required permissions.
- Template is made available for download in the UI.

#### Step 3 — Manual Deployment (Customer Action)
- Customer downloads the CloudFormation template.
- Customer deploys the stack in their AWS account via Console, CLI, or CI.
- CloudFormation creates the IAM Role and attaches the required policies.
- Customer copies the `Role ARN` output from the CloudFormation stack.
- Customer pastes the `Role ARN` into the BalanceKube UI.

#### Step 4 — AWS Access Validation
- Backend calls `sts:AssumeRole` using the provided ARN and the stored `external_id`.
- On success: proceeds to cluster discovery.
- On failure: returns structured validation errors (wrong account, missing ExternalId, insufficient permissions).

#### Step 5 — Cluster Discovery
- Backend calls the AWS EC2/EKS APIs (via the assumed role) to enumerate available EKS clusters in the customer's account.
- Cluster list is displayed in the UI with metadata (region, K8s version, node count estimate).

#### Step 6 — Cluster Selection & Agent Installation (Manual + Automated)
- Operator selects a cluster in the UI.
- Backend generates a short-lived **Cluster Registration Token** (signed JWT, 1-hour TTL).
- One-click agent installation: the UI presents a `kubectl apply` command that references the BalanceKube Helm chart, embedding the registration token as a Kubernetes Secret.
- Helm deploys:
  - `Agent Controller` (Deployment, 1 replica) — responsible for registration, heartbeat, inventory collection, and event streaming.
  - `Agent DaemonSet` — one pod per node, responsible for Kubelet API scraping.

#### Step 7 — Agent Registration & Validation
- Agent Controller calls the BalanceKube registration API with the token.
- Platform validates token, exchanges it for a long-lived `agent_credential` (client certificate or rotating API key).
- Platform runs:
  - **Connectivity Validation** — confirms agent is reachable and authenticated.
  - **Kubernetes Validation** — confirms agent has required RBAC permissions to read cluster resources.

#### Step 8 — Metadata Storage & Cluster Active
- Platform stores initial cluster metadata:
  - `cluster_inventory` — initial node list, AZ distribution, instance types.
  - `node_inventory` — per-node record.
  - `region_metadata` — region, availability zones.
  - `kubernetes_metadata` — K8s version, cluster name, provider.
- All records written to the Platform Database.
- Cluster status transitions to `Active`.
- Phase 1 metric collection begins immediately.

### Backend Modules Involved
`backend/onboarding` · `backend/organizations` · `backend/users` · `backend/cluster_inventory` · `backend/agent_management` · `backend/audit_logs`

### Workers Involved
`workers/onboarding` (async CloudFormation validation, cluster discovery polling)

### Infrastructure Involved
`infrastructure/onboarding` (CloudFormation template generation), `infrastructure/kubernetes` (Helm chart)

---

## 8. Phase 1 — Data Collection Pipeline

### Purpose

Continuously collect a complete, consistent snapshot of the cluster state, resource metrics, AWS pricing data, and Spot interruption risk data. Assemble them into an `assembled_snapshot` and emit a `cluster.collected` event to trigger Phase 2.

### Collection Sources

#### 6.1 Kubernetes API Collection (via Agent Controller)

The Agent Controller queries the Kubernetes API Server using `controller-runtime` informers (watch-based, efficient). The following resource types are collected on every snapshot cycle:

| Resource | Key Fields Collected |
|---|---|
| **Nodes** | Name, instance type, AZ, capacity (vCPU, RAM), allocatable, conditions, labels, taints |
| **Pods** | Name, namespace, owner reference, node assignment, phase, resource requests/limits, labels, annotations |
| **Deployments** | Name, namespace, replicas, selector, strategy, labels, annotations |
| **StatefulSets** | Name, namespace, replicas, volumeClaimTemplates, podManagementPolicy |
| **DaemonSets** | Name, namespace, updateStrategy, selector |
| **PersistentVolumeClaims** | Name, namespace, storageClass, accessModes, capacity, phase |
| **PodDisruptionBudgets** | Name, namespace, minAvailable / maxUnavailable, currentHealthy |
| **Namespaces** | Name, labels, annotations, phase |
| **Labels & Annotations** | Full label and annotation maps for all resources |
| **Affinity Rules** | nodeAffinity, podAffinity, podAntiAffinity for all pods |
| **Taints & Tolerations** | Node taints, pod tolerations |

#### 6.2 Metrics Collection

**Kubelet Summary API** (`/api/v1/nodes/{node}/proxy/stats/summary`) — collected per node by each DaemonSet pod:
- CPU usage (cores, nanoseconds)
- Memory usage (workingSetBytes, rssBytes)
- Network (rxBytes, txBytes per interface)
- Filesystem usage (usedBytes, capacityBytes)

**Metrics Server** (`metrics.k8s.io/v1beta1`) — collected by the Controller:
- Per-pod CPU and memory usage (aggregated over the scrape window)
- Used for cross-validation with Kubelet data

**Normalisation** (`backend/metrics_collection/normalization`):
- All CPU values normalised to millicores (m)
- All memory values normalised to mebibytes (Mi)
- Network values normalised to Kbps
- Filesystem to GiB
- Time-series stored with collection timestamp for trend analysis

#### 6.3 Pricing Collection (Platform Side, not Agent)

Collected by `workers/pricing_collection` on a scheduled basis (daily for on-demand, hourly for spot):

**AWS Pricing API** (`pricing.us-east-1.amazonaws.com`):
- On-demand prices per instance type per region ($/hr)
- Instance catalogue: vCPU count, memory (GiB), network performance, instance family

**AWS EC2 Spot Price History API**:
- Current spot prices per instance type per AZ ($/hr)
- 30-day rolling history stored for trend analysis

**Normalisation** (`backend/pricing_collection/normalization`):
- Prices normalised to $/hr and $/month equivalents
- Per-vCPU and per-GiB breakdowns computed for comparison

#### 6.4 Spot Risk Collection (Platform Side)

Collected by `workers/spot_risk_collection` hourly:

**AWS Spot Instance Advisor** (scraped from `https://spot-price.s3.amazonaws.com/spot.js` or equivalent):
- Interruption frequency band per instance type per region (< 5%, 5–10%, 10–15%, 15–20%, > 20%)
- Savings vs on-demand

**Historical Spot Risk Dataset** (`backend/spot_risk_collection/historical_dataset`):
- Rolling 90-day retention of interruption rate data
- Used by the Eligibility Engine to assign risk scores

**Risk Normalisation** (`backend/spot_risk_collection/risk_normalization`):
- AWS interruption bands mapped to a 0–10 internal risk score
- Score ≤ 3: low risk (< 5% interruption frequency)
- Score 4–6: medium risk (5–15%)
- Score ≥ 7: high risk (> 15%)

### Snapshot Assembly

The `backend/snapshot_assembly` module combines all four data sources into a single `assembled_snapshot` record:

```
assembled_snapshot {
  snapshot_id:       uuid (v4, immutable)
  cluster_id:        uuid
  collected_at:      timestamp
  schema_version:    integer
  kubernetes:        { nodes[], pods[], deployments[], statefulsets[],
                       daemonsets[], pvcs[], pdbs[], namespaces[],
                       labels{}, affinity_rules[], taints[] }
  metrics:           { cpu{}, memory{}, network{}, filesystem{} }
  pricing:           { on_demand{}, spot{}, instance_catalog{} }
  spot_risk:         { risk_scores{}, historical_dataset_ref }
  cluster_hash:      sha256(node_types + node_counts + az_distribution)
  assembly_version:  integer
}
```

- `snapshot_id` is the primary key linking all downstream phases.
- `cluster_hash` is computed from stable topology; changes in topology produce a new hash.
- `assembly_version` increments with schema changes; downstream consumers check compatibility.

### Event Emission

On successful assembly, `workers/snapshot_assembly` emits:

```
cluster.collected {
  cluster_id:    uuid
  snapshot_id:   uuid
  cluster_hash:  sha256
  collected_at:  timestamp
}
```

This event is consumed by `workers/workload_classification` to begin Phase 2.

### Backend Modules Involved
`backend/cluster_inventory/*` · `backend/metrics_collection/*` · `backend/pricing_collection/*` · `backend/spot_risk_collection/*` · `backend/snapshot_assembly` · `backend/events`

### Workers Involved
`workers/cluster_inventory` · `workers/metrics_collection` · `workers/pricing_collection` · `workers/spot_risk_collection` · `workers/snapshot_assembly`

---

## 9. Phase 2 — Workload Intelligence Engine

### Purpose

Transform a raw `assembled_snapshot` into a versioned recommendation with per-workload Spot eligibility verdicts and savings estimates. All output is stored in the `recommendation_store` and versioned by `analysis_version`.

### Review State Gate

Before analysis proceeds, a **Review State Check** determines whether operator validation is required:

**First Optimisation Cycle:**
- `review_state` = `pending_review`
- An `Initial Workload Review` is generated listing every workload discovered in the snapshot.
- A notification is dispatched to the operator.
- Analysis is blocked until the operator marks the review `complete` in the UI.
- `review_state` transitions to `reviewed`.

**Subsequent Cycles:**
- `backend/workload_review` checks whether any new workloads have appeared since the last reviewed cycle (by diffing the current workload set against the last `reviewed` snapshot).
- If new workloads are detected: generate a `Partial Review` (new workloads only) and block until reviewed.
- If no new workloads: proceed directly to analysis.

### E1A — Metadata Collection & Tag Generation

**Tag Generation** (`backend/workload_classification/tag_generation`):

Tags are key-value pairs attached to every workload (Deployment / StatefulSet / DaemonSet). They encode the workload's identity and purpose derived from multiple signals:

| Signal Source | Example Tags Produced |
|---|---|
| Pod labels | `app`, `component`, `tier`, `environment` |
| Container image names | `image:redis`, `image:postgres` |
| Container command/args | `cmd:java`, `cmd:python` |
| Resource patterns | `cpu-intensive`, `memory-intensive`, `low-resource` |
| PVC attachment | `stateful`, `pvc-attached` |
| PDB presence | `pdb-protected` |
| Namespace | `namespace:production`, `namespace:monitoring` |

**Workload Classification** (`backend/workload_classification/*`):

Each workload is run through a chain of specialised detectors. Each detector returns a confidence score (0.0–1.0) and a classification label. The highest-confidence classification wins, with ties resolved by priority order.

| Detector | Signals Used | Output Label |
|---|---|---|
| `java_detection` | image name contains `jdk`/`jre`/`openjdk`/`corretto`; JVM heap flags in args; high memory-to-CPU ratio | `java` |
| `batch_detection` | CronJob owner; `batch`/`job` in name; intermittent CPU spikes; restart policy `Never` or `OnFailure` | `batch` |
| `stateful_detection` | PVC attached; StatefulSet owner; `stateful` in labels | `stateful` |
| `database_detection` | image contains `postgres`/`mysql`/`mongo`/`mariadb`/`cassandra`; port 5432/3306/27017 | `database` |
| `cache_detection` | image contains `redis`/`memcached`/`valkey`; port 6379/11211 | `cache` |
| `queue_detection` | image contains `kafka`/`rabbitmq`/`nats`/`activemq`; consumer lag metrics present | `queue` |
| `monitoring_detection` | image contains `prometheus`/`grafana`/`alertmanager`/`loki`/`jaeger`; namespace `monitoring` | `monitoring` |
| `unknown_detection` | Fallback when no other detector exceeds threshold (0.6) | `unknown` |

Classification output is stored as `workload_tags` with `analysis_version` reference.

### E1B — Resource Analysis

**CPU Analysis** (`backend/resource_analysis/cpu`):
- Compares `requests.cpu` vs actual p95 CPU usage from metrics.
- Computes CPU utilisation ratio: `actual / request`.
- Flags over-provisioned (ratio < 0.3) and under-provisioned (ratio > 0.9) workloads.
- Computes CPU burstiness index: `p99 / p50` — high burstiness suggests batch-like behaviour.

**Memory Analysis** (`backend/resource_analysis/memory`):
- Compares `requests.memory` vs actual working set.
- Detects memory growth trends (linear regression on 7-day rolling window).
- Flags OOM risk: workloads where `actual / limit > 0.85`.
- Java workloads: cross-references JVM heap flags against container memory limit.

**Network Analysis** (`backend/resource_analysis/network`):
- Computes average and peak network throughput per workload.
- Flags network-intensive workloads (> 100 Mbps p95) as candidates for network-optimised instance types.

**Storage Analysis** (`backend/resource_analysis/storage`):
- For PVC-attached workloads: collects IOPS estimation, throughput, and capacity utilisation.
- Flags high-IOPS workloads as requiring local NVMe or io1/io2 EBS on target nodes.

**Data Maturity Analysis**:
- Assesses whether sufficient metric history exists for reliable analysis (minimum: 7 days of data).
- Workloads with insufficient history are flagged `data_immature` and given conservative estimates.

All E1B outputs are stored in `workload_analysis` table, keyed by `(cluster_id, workload_id, analysis_version)`.

### Placement Eligibility Engine

The eligibility engine takes `workload_analysis` + `workload_tags` and produces a per-workload **eligibility verdict** with structured decision reasons.

#### Hard Block Rules (`backend/eligibility_engine/hard_rules`)

These rules unconditionally block Spot placement:

| Rule ID | Condition | Decision Reason |
|---|---|---|
| `HARD-001` | Workload classification = `database` | Databases require persistent, guaranteed compute |
| `HARD-002` | PVC attached + no PDB | Stateful workload without disruption budget |
| `HARD-003` | Single replica + no HPA | Cannot tolerate interruption, no scale-out path |
| `HARD-004` | `pdb.minAvailable` = total replicas | PDB allows zero disruptions |
| `HARD-005` | `spot_risk_score` ≥ 8 AND classification = `stateful` | Too high risk for stateful workloads |
| `HARD-006` | Operator has set `spot_eligible: false` override | Manual block by operator |

#### Conditional Rules (`backend/eligibility_engine/conditional_rules`)

These rules produce warnings but do not block:

| Rule ID | Condition | Warning |
|---|---|---|
| `COND-001` | `spot_risk_score` ≥ 6 | High interruption rate — consider fallback instance types |
| `COND-002` | Memory-intensive (actual > 80% of limit) | Memory pressure may cause issues after Spot interruption |
| `COND-003` | Classification = `java` AND heap flags set tightly | JVM heap may not re-initialise within Spot reclaim window |
| `COND-004` | HPA `minReplicas` = 1 | During interruption, workload may briefly have 0 replicas |
| `COND-005` | Network-intensive > 500 Mbps p95 | Target instance type must support enhanced networking |

#### Operator Overrides (`backend/eligibility_engine/operator_overrides`)

Operators can set per-workload overrides that take precedence over all computed rules:
- `spot_eligible: true` — force eligible even if hard rules would block.
- `spot_eligible: false` — force blocked even if eligible.
- `target_instance_family: [c5, c5n, m5]` — restrict instance type options.
- `max_spot_risk_score: 5` — override the system-default risk threshold for this workload.

Overrides are stored in the `operator_overrides` table and versioned.

### Savings Estimator

For each eligible workload, the Savings Estimator (`backend/recommendations`) computes:

```
savings_estimate {
  workload_id:              uuid
  current_instance_type:    string           // e.g. "m5.large"
  current_cost_monthly:     decimal(10,4)    // based on on_demand price × hours
  recommended_instance_type: string          // e.g. "m5.large" (spot)
  spot_cost_monthly:        decimal(10,4)    // based on current spot price
  savings_monthly:          decimal(10,4)    // current - spot
  savings_pct:              decimal(5,2)     // (savings / current) × 100
  spot_risk_score:          integer          // 0–10
  pricing_freshness_at:     timestamp        // age of spot price data used
}
```

**Pricing Freshness Validation**: If spot prices are older than 2 hours, the estimator flags the estimate as `stale` and skips savings calculation until fresh prices are available.

### Recommendation Store

Final output written to `recommendation_store`:

```
recommendation_store {
  recommendation_id:  uuid
  cluster_id:         uuid
  snapshot_id:        uuid           // links to assembled_snapshot
  analysis_version:   integer        // monotonically increasing per cluster
  cluster_hash:       sha256         // topology fingerprint
  created_at:         timestamp
  status:             enum(pending_approval, approved, executing, executed, invalidated)
  workload_verdicts:  workload_verdict[]
  decision_reasons:   decision_reason[]
  savings_estimate:   savings_summary
  total_savings_monthly: decimal(10,4)
}
```

### Event Emission

```
cluster.analysed {
  cluster_id:         uuid
  recommendation_id:  uuid
  snapshot_id:        uuid
  analysis_version:   integer
  cluster_hash:       sha256
  analysed_at:        timestamp
}
```

Consumed by `workers/drift_detection` to begin Phase 3.

### Backend Modules Involved
`backend/workload_review` · `backend/workload_classification/*` · `backend/resource_analysis/*` · `backend/eligibility_engine/*` · `backend/recommendations` · `backend/events`

### Workers Involved
`workers/workload_review` · `workers/workload_classification` · `workers/resource_analysis` · `workers/eligibility_engine` · `workers/recommendations`

---

## 10. Phase 3 — Drift Detection Engine

### Purpose

Between when a recommendation is generated (Phase 2) and when it is approved and executed (Phase 4), cluster state may have changed. Phase 3 continuously monitors for drift by comparing the current live state against the planned snapshot. If drift is detected, the engine determines whether the existing plan can be patched (patchable drift) or must be fully reanalysed (invalidating drift).

### Trigger

Phase 3 runs:
- Once immediately after `cluster.analysed` is emitted.
- On a recurring schedule (e.g. every 5 minutes) while a recommendation is in `pending_approval` status.
- On-demand when an operator triggers a manual re-check in the UI.

### Snapshot Comparator (`backend/drift_detection/snapshot_comparator`)

The comparator loads:
- **Planned Snapshot**: the `assembled_snapshot` referenced by `recommendation.snapshot_id`.
- **Current Snapshot**: a fresh snapshot assembled from the live cluster state (same pipeline as Phase 1, but on-demand rather than scheduled).

The comparison is keyed on the three-part plan identity:
- `snapshot_id` — the base snapshot the recommendation was built on.
- `analysis_version` — the version of the analysis logic that produced the recommendation.
- `cluster_hash` — the topology fingerprint at analysis time.

If the current cluster's `cluster_hash` differs from the planned `cluster_hash`, all subsequent diff categories are marked `hash_mismatch` and the recommendation is immediately invalidated.

### Diff Categories

#### Node-Level Diff (`backend/drift_detection/node_diff`)

| Change Type | Patchable? | Notes |
|---|---|---|
| Node Added | Yes | New node can be incorporated into the plan |
| Node Removed | Conditional | If removed node is not in execution plan: patchable. If it is: invalidate |
| Node Type Changed | No | Changes cluster_hash → always invalidates |

#### Pod-Level Diff (`backend/drift_detection/pod_diff`)

| Change Type | Patchable? | Notes |
|---|---|---|
| New Workload | Conditional | Triggers partial review gate (Phase 2 sub-flow) |
| Workload Removed | Yes | Remove from execution plan |
| Replica Count Changed | Conditional | If within ±20% of planned: patchable. Beyond: invalidate |
| PVC Attached (new) | No | Changes eligibility — requires full reanalysis |

#### Resource Diff (`backend/drift_detection/resource_diff`)

| Change Type | Patchable? | Notes |
|---|---|---|
| CPU Profile Changed | Conditional | If within configured tolerance (default ±15%): patchable |
| Memory Profile Changed | Conditional | Same tolerance logic |
| Storage Profile Changed | No | May change IOPS requirements |

#### Configuration Diff (`backend/drift_detection/configuration_diff`)

| Change Type | Patchable? | Notes |
|---|---|---|
| PDB Changed | No | Hard eligibility rules may flip |
| HPA Changed | Conditional | minReplicas change may affect single-replica rules |
| Criticality Label Changed | No | Requires re-evaluation of operator overrides |
| Purpose Label Changed | No | May change workload classification |

### Impact Analysis (`backend/drift_detection/impact_analysis`)

For each detected change, the impact analyser assigns:
- `severity`: low / medium / high
- `affected_workloads`: list of workload IDs affected
- `patchable`: boolean
- `reason`: human-readable explanation

The overall recommendation is `patchable` only if **all** detected changes are individually patchable.

### Plan Delta (`backend/drift_detection/plan_delta`)

If patchable:
- A `plan_delta` record is generated documenting the specific changes.
- The existing recommendation is updated in-place (new `analysis_version` minor bump).
- Status transitions to `execution_ready`.

If not patchable:
- The recommendation status is set to `invalidated`.
- `workers/drift_detection` emits a `Phase 2 reanalysis` trigger.
- `backend/drift_detection/reanalysis` orchestrates a full Phase 2 cycle using the current snapshot.

### Backend Modules Involved
`backend/drift_detection/*` · `backend/snapshot_assembly` · `backend/recommendations` · `backend/events`

### Workers Involved
`workers/drift_detection`

---

## 11. Phase 4 — Execution Engine

### Purpose

Execute an approved recommendation against the live cluster: provision new Spot capacity, drain source nodes, migrate workloads, apply Spot placement configuration, validate health, and record the outcome. Full rollback capability is maintained throughout.

### Pre-Conditions

A recommendation must be in `approved` status before Phase 4 begins. Approval is an explicit operator action in the UI (or via API with appropriate RBAC permission).

### Step-by-Step Execution Flow

#### Step 1 — Acquire Cluster Lock (`backend/execution/lock_manager`)

- Attempt to acquire an exclusive advisory lock for `cluster_id`.
- Lock is stored in the database with a TTL (e.g. 30 minutes, renewable).
- If lock cannot be acquired (another execution is in progress): the job is queued and retried.
- Lock prevents concurrent executions against the same cluster.

#### Step 2 — Load Recommendation & Execution Validation (`backend/execution/plan_validation`)

The three-part identity is validated:

```
validate(
  current.snapshot_id    == recommendation.snapshot_id,    // same base snapshot
  current.analysis_version == recommendation.analysis_version, // same analysis
  current.cluster_hash   == recommendation.cluster_hash    // same topology
)
```

If any check fails → execution is aborted and control returns to Phase 3 for reanalysis.

#### Step 3 — Create Rollback Snapshot (`backend/rollback`)

- A complete point-in-time snapshot of the current cluster state is captured and stored as `rollback_snapshot`.
- The rollback snapshot records:
  - Current node pool composition (instance types, counts, AZ distribution)
  - All workload placements (which pod is on which node)
  - All active PVC bindings
  - All HPA configurations
- The rollback snapshot is immutable and retained until execution is confirmed successful.

#### Step 4 — Generate Execution Plan (`backend/execution`)

An ordered execution plan is produced:
1. List of Spot nodes to provision (instance type, AZ, count)
2. List of source nodes to drain (in safe order: respect PDB limits, don't drain multiple replicas of same deployment simultaneously)
3. Workload migration sequence (move workloads from on-demand nodes to Spot nodes)
4. Spot placement configuration (node labels, tolerations, affinity rules to apply)

#### Step 5 — Provision Capacity (`backend/execution/capacity_provisioning`)

- AWS Auto Scaling Group or EC2 Fleet API calls to provision Spot instances of the target type in target AZ.
- Waits for nodes to join the cluster and become `Ready`.
- Validates node labels and taints match the execution plan.
- Timeout: 10 minutes. On timeout: rollback triggered.

#### Step 6 — Drain Source Nodes (`backend/execution/node_drain`)

- For each source node in execution order:
  - Set node `unschedulable` (cordon).
  - Evict pods respecting PDB constraints (uses the Eviction API, not force delete).
  - Wait for all pods to be rescheduled on new nodes.
  - Confirm node is empty.
- Between drains: re-check workload health before proceeding to the next node.

#### Step 7 — Migrate Workloads (`backend/execution/workload_migration`)

- Validates that rescheduled pods have been placed on the target Spot nodes (via node affinity or taint toleration).
- For any pods not automatically placed correctly: applies manual scheduling hints.

#### Step 8 — Apply Spot Placement (`backend/execution/spot_placement`)

- Applies the final Spot placement configuration to the workloads:
  - Node affinity rules updated in Deployment / StatefulSet specs.
  - Tolerations updated to match Spot node taints.
  - Pod topology spread constraints updated if required.

#### Step 9 — Health Validation (`backend/execution/health_validation`)

Post-migration checks:
- All target pods are `Running` and `Ready`.
- No pods in `CrashLoopBackOff` or `OOMKilled`.
- PDB `currentHealthy` meets `minAvailable` for all protected workloads.
- Metrics server reports CPU and memory within expected ranges (compared against pre-execution baseline from rollback snapshot).
- Wait period: configurable (default: 5 minutes of healthy state).

#### Step 10 — Success or Rollback

**Success path:**
- Execution status set to `success`.
- Source (on-demand) nodes terminated or returned to the node pool.
- Rollback snapshot marked `retired`.
- Execution record written to `execution_history`.
- `cluster_hash` and `analysis_version` updated to reflect the new post-execution state.
- Metrics feedback loop triggered: updated cluster state feeds into the next Phase 1 cycle.

**Failure path (Rollback Engine):**
- `backend/rollback` loads the rollback snapshot.
- Restoration sequence:
  1. Reprovision the original on-demand nodes (or un-terminate if within reclaim window).
  2. Drain the new Spot nodes.
  3. Wait for workloads to reschedule back onto on-demand nodes.
  4. Validate health using the same health validation checks.
- Status set to `rolled_back`.
- Execution record written to `execution_history` with failure reason.
- Alert dispatched to operator.

### Execution History

```
execution_history {
  execution_id:       uuid
  cluster_id:         uuid
  recommendation_id:  uuid
  status:             enum(success, rolled_back, aborted)
  started_at:         timestamp
  completed_at:       timestamp
  duration_seconds:   integer
  nodes_provisioned:  integer
  nodes_drained:      integer
  workloads_migrated: integer
  savings_realised_monthly: decimal(10,4)
  failure_reason:     text (nullable)
  rollback_reason:    text (nullable)
}
```

### Metrics Feedback

On completion (success or rollback), an event is emitted that triggers the next Phase 1 cycle immediately, ensuring the platform's view of the cluster is updated to reflect post-execution reality rather than waiting for the next scheduled collection.

### Backend Modules Involved
`backend/execution/*` · `backend/rollback` · `backend/recommendations` · `backend/events` · `backend/audit_logs`

### Workers Involved
`workers/execution` · `workers/rollback` · `workers/notifications`

---

## 12. Core Engines

BalanceKube's intelligence is concentrated in eight named engines. Each engine is a logical unit with a defined input contract, processing responsibility, and output contract. They are not necessarily single files — each maps to one or more backend sub-modules and a corresponding worker.

### Review Engine
- **Location:** `backend/workload_review`, `workers/workload_review`
- **Input:** `assembled_snapshot` (via `cluster.collected` event)
- **Responsibility:** Determines whether the pipeline may proceed to analysis or must wait for operator sign-off. Manages `pending_review` state, generates review items, dispatches notifications, and transitions to `reviewed` on operator completion.
- **Output:** `review_state = reviewed` — gates Phase 2 analysis start
- **Key Rule:** First cycle always blocks. Subsequent cycles block only if new workloads are detected.

### Tag Generation Engine
- **Location:** `backend/workload_classification/tag_generation`, `workers/workload_classification`
- **Input:** `assembled_snapshot` — pod specs, labels, annotations, image names, resource requests
- **Responsibility:** Extracts structured tags from all available signals. Tags encode identity (`app`, `tier`, `env`), behaviour (`cpu-intensive`, `stateful`), and protection (`pdb-protected`).
- **Output:** `workload_tags` table rows keyed by `(cluster_id, workload_id, analysis_version)`

### Workload Classification Engine
- **Location:** `backend/workload_classification/*` (all detector sub-modules)
- **Input:** `workload_tags` + raw pod specs
- **Responsibility:** Runs a chain of specialised detectors (Java, Batch, Stateful, Database, Cache, Queue, Monitoring, Unknown). Each detector returns a confidence score. Highest-confidence classification wins.
- **Output:** `workload_classifications` — one row per workload with `classification` label and `confidence` score

### Resource Analysis Engine
- **Location:** `backend/resource_analysis/*`, `workers/resource_analysis`
- **Input:** `workload_classifications` + metric time-series from `cpu_metrics`, `memory_metrics`, `network_metrics`, `filesystem_metrics`
- **Responsibility:** Profiles each workload's actual resource usage against its requests/limits. Detects over-provisioning, under-provisioning, OOM risk, burstiness, and storage I/O patterns. Assesses data maturity (minimum 7-day history).
- **Output:** `workload_analysis` table rows

### Eligibility Engine
- **Location:** `backend/eligibility_engine/*`, `workers/eligibility_engine`
- **Input:** `workload_analysis` + `workload_classifications` + `operator_overrides` + `risk_scores`
- **Responsibility:** Evaluates every workload against the hard block rule set, then conditional rules, then operator overrides. Produces a binary `eligible`/`blocked` verdict with structured `decision_reasons`.
- **Output:** `eligibility_verdicts` table rows — one per `(cluster_id, workload_id, analysis_version)`

### Savings Estimation Engine
- **Location:** `backend/recommendations`, `workers/recommendations`
- **Input:** `eligibility_verdicts` (eligible workloads only) + `on_demand_prices` + `spot_prices` + `risk_scores`
- **Responsibility:** Computes per-workload monthly savings (current on-demand cost minus projected Spot cost). Validates pricing freshness (rejects data older than 2 hours). Aggregates cluster-level total savings estimate.
- **Output:** `savings_estimates` rows + `recommendation_store` record with status `pending_approval`

### Drift Detection Engine
- **Location:** `backend/drift_detection/*`, `workers/drift_detection`
- **Input:** Planned `assembled_snapshot` (via `recommendation.snapshot_id`) + fresh current snapshot + `cluster_hash`
- **Responsibility:** Compares planned state vs live state across four diff dimensions (node, pod, resource, configuration). Classifies each detected change as patchable or invalidating. For patchable drift: generates a `plan_delta` and updates the recommendation. For invalidating drift: marks recommendation as `invalidated` and triggers Phase 2 reanalysis.
- **Output:** `drift_events` + `plan_deltas` OR recommendation `status = invalidated`

### Execution Planning & Rollback Engine
- **Location:** `backend/execution/*`, `backend/rollback`, `workers/execution`, `workers/rollback`
- **Input:** Approved `recommendation_store` record with valid three-part identity
- **Responsibility:** Acquires cluster lock → validates three-part identity → captures rollback snapshot → generates ordered execution plan → provisions Spot capacity → drains source nodes → migrates workloads → validates health. On failure at any step: triggers rollback sequence to restore prior state.
- **Output:** `execution_history` record with `status = success` or `status = rolled_back`

---

## 13. Backend Module Reference

Each sub-folder under `backend/` contains a module-level `.md` file (auto-created by the folder structure script) that should document: purpose, exposed API routes, database tables owned, events published, events consumed, and external dependencies.

### `backend/onboarding`
- **Purpose:** Customer registration flow through to cluster Active status.
- **Routes:** `POST /orgs`, `POST /orgs/:id/cloudformation`, `POST /orgs/:id/validate-role`, `GET /orgs/:id/clusters/discover`, `POST /clusters/register`
- **Tables:** `organizations`, `cloudformation_stacks`, `cluster_registrations`
- **Events Published:** `org.created`, `cluster.registered`

### `backend/cluster_inventory`
- **Purpose:** Store and serve the Kubernetes resource inventory collected by the agent.
- **Routes:** `GET /clusters/:id/nodes`, `GET /clusters/:id/pods`, `GET /clusters/:id/deployments` (and equivalents for all resource types)
- **Tables:** `nodes`, `pods`, `deployments`, `statefulsets`, `daemonsets`, `pvcs`, `pdbs`, `namespaces`
- **Events Consumed:** `cluster.collected`

### `backend/metrics_collection`
- **Purpose:** Ingest and store time-series metric data from the agent.
- **Routes:** `POST /clusters/:id/metrics` (agent push endpoint), `GET /clusters/:id/metrics/:workload_id`
- **Tables:** `cpu_metrics`, `memory_metrics`, `network_metrics`, `filesystem_metrics`
- **Notes:** Metrics older than 90 days are pruned by a scheduled worker.

### `backend/pricing_collection`
- **Purpose:** Store AWS pricing data and serve it to the analysis pipeline.
- **Tables:** `on_demand_prices`, `spot_prices`, `instance_catalog`
- **External:** AWS Pricing API, EC2 Spot Price History API

### `backend/spot_risk_collection`
- **Purpose:** Store Spot interruption risk data.
- **Tables:** `interruption_rates`, `risk_scores`, `spot_risk_history`
- **External:** AWS Spot Instance Advisor (scraped)

### `backend/snapshot_assembly`
- **Purpose:** Assembles all data sources into an immutable `assembled_snapshot`.
- **Tables:** `assembled_snapshots`
- **Events Published:** `cluster.collected`

### `backend/workload_review`
- **Purpose:** Manages the review state gate between snapshot collection and analysis.
- **Routes:** `GET /clusters/:id/reviews`, `POST /clusters/:id/reviews/:review_id/complete`
- **Tables:** `workload_reviews`, `review_items`
- **Events Published:** `review.completed`

### `backend/workload_classification`
- **Purpose:** Tag generation and workload type classification.
- **Tables:** `workload_tags`, `workload_classifications`
- **Notes:** Each detector sub-module is independently testable and configurable.

### `backend/resource_analysis`
- **Purpose:** Per-workload resource profile analysis (CPU, memory, network, storage).
- **Tables:** `workload_analysis`

### `backend/eligibility_engine`
- **Purpose:** Computes per-workload Spot eligibility verdicts.
- **Tables:** `eligibility_verdicts`, `operator_overrides`, `decision_reasons`

### `backend/recommendations`
- **Purpose:** Stores and manages the recommendation lifecycle.
- **Routes:** `GET /clusters/:id/recommendations`, `POST /clusters/:id/recommendations/:id/approve`
- **Tables:** `recommendation_store`, `savings_estimates`
- **Events Published:** `cluster.analysed`, `recommendation.approved`

### `backend/drift_detection`
- **Purpose:** Detects and classifies drift between planned and live state.
- **Tables:** `drift_events`, `plan_deltas`
- **Events Published:** `drift.detected`, `drift.patchable`, `drift.invalidated`

### `backend/execution`
- **Purpose:** Orchestrates safe, rollback-capable cluster migrations.
- **Routes:** `POST /clusters/:id/executions`, `GET /clusters/:id/executions/:exec_id`
- **Tables:** `execution_history`, `execution_locks`
- **Events Published:** `execution.started`, `execution.completed`, `execution.rolled_back`

### `backend/rollback`
- **Purpose:** Creates rollback snapshots pre-execution and restores them on failure.
- **Tables:** `rollback_snapshots`

### `backend/agent_management`
- **Purpose:** Manages agent credentials, heartbeat, and upgrades.
- **Routes:** `POST /api/v1/agents/register`, `POST /api/v1/agents/:id/heartbeat`, `GET /api/v1/agents/:id/upgrade`
- **Tables:** `agents`, `agent_tokens`

### `backend/users` / `backend/organizations`
- **Purpose:** Multi-tenant identity and access management.
- **Tables:** `users`, `organizations`, `memberships`, `api_keys`

### `backend/audit_logs`
- **Purpose:** Append-only audit trail for all mutation operations.
- **Tables:** `audit_logs`
- **Notes:** All writes include `actor_id`, `action`, `resource_type`, `resource_id`, `before`, `after`, `ip_address`, `timestamp`.

### `backend/events`
- **Purpose:** Domain event publisher using Redis Streams (or PostgreSQL LISTEN/NOTIFY as fallback).
- **Notes:** All events are persisted to `event_store` table before publishing to ensure at-least-once delivery.

---

## 14. Frontend Module Reference

The frontend is a single-page React application. Each module under `frontend/` maps to a distinct UI feature area.

### `frontend/onboarding`
Multi-step wizard: account creation → CloudFormation download → ARN paste → validation result → cluster discovery → cluster selection → agent installation instructions → cluster active confirmation.

### `frontend/cluster_inventory`
Tabbed inventory view: Cluster list → Node details (instance type, AZ, status, resource usage) → Pod list (filterable by namespace, owner, status) → Deployment/StatefulSet/DaemonSet browser.

### `frontend/workload_review`
Review queue: lists workloads pending operator validation. Per-workload view shows classification tags, resource profile, and proposed eligibility verdict. Operators can accept, reject, or add notes. Bulk actions supported.

### `frontend/recommendations`
Recommendation dashboard: total cluster savings estimate, per-workload breakdown, eligibility summary (eligible / blocked / overridden). Savings charts. Approve button with confirmation modal.

### `frontend/drift_detection`
Live drift status panel: shows current plan state (valid / drifted / invalidated). Diff viewer for patchable drift (node changes, pod changes). Reanalysis trigger button.

### `frontend/execution`
Execution approval flow → real-time progress view (current step, elapsed time, affected workloads) → execution history table with success/rollback status and savings realised.

### `frontend/shared`
Design system, shared API client (`/shared/api`), TypeScript type definitions mirroring backend schemas, authentication context, notification toasts, data tables, charts, and loading states.

---

## 15. Workers Module Reference

Workers are background job processors. Each worker module subscribes to a queue/event and executes a well-defined unit of work.

Workers use idempotent handlers where possible. Each background job has a documented retry strategy, and failures after full retries are persisted to the `dead_letter_jobs` table with full context for manual investigation. Persisted events may be replayed from `event_store` to recover failed pipeline stages.

| Worker | Trigger | Work Unit | Retry Strategy |
|---|---|---|---|
| `workers/onboarding` | `org.created` event | Async CF validation, cluster discovery | 3× with exponential backoff |
| `workers/cluster_inventory` | Cron (every 5 min) | Trigger agent inventory push | N/A |
| `workers/metrics_collection` | Agent push (HTTP) | Ingest and store metrics | 2× immediate |
| `workers/pricing_collection` | Cron (daily / hourly) | Fetch AWS pricing and spot prices | 5× with jitter |
| `workers/spot_risk_collection` | Cron (hourly) | Scrape Spot Advisor | 3× |
| `workers/snapshot_assembly` | `cluster.collected` (agent event) | Assemble snapshot | 3× |
| `workers/workload_review` | `review.pending` event | Dispatch notification | 2× |
| `workers/workload_classification` | `cluster.collected` event | Run all detectors | 3× |
| `workers/resource_analysis` | After classification complete | CPU/mem/network/storage analysis | 3× |
| `workers/eligibility_engine` | After resource analysis complete | Compute verdicts | 3× |
| `workers/recommendations` | After eligibility complete | Compute savings, write to store | 3× |
| `workers/drift_detection` | `cluster.analysed` + cron | Compare snapshots, generate delta | 3× |
| `workers/execution` | `recommendation.approved` event | Orchestrate execution steps | No auto-retry (human approval required) |
| `workers/rollback` | `execution.failed` event | Execute rollback sequence | 2× |
| `workers/notifications` | Any notification event | Send email/Slack/webhook | 5× |

All workers use a dead-letter queue. Failed jobs after all retries are persisted to `dead_letter_jobs` table with full context for manual investigation.

---

## 16. Agent Module Reference

The agent is a Go binary deployed into the customer cluster. It runs as two Kubernetes workloads:

### Agent Controller (Deployment, 1 replica)

| Module | Responsibility |
|---|---|
| `agent/controller` | controller-runtime manager; owns all reconciliation loops |
| `agent/registration` | One-time registration on startup using the registration token |
| `agent/heartbeat` | Sends heartbeat every 30 seconds with health summary |
| `agent/upgrades` | Watches for upgrade instructions from platform; applies rolling update |
| `agent/token_rotation` | Rotates the long-lived agent credential on a 7-day schedule |
| `agent/cluster_inventory` | Queries Kubernetes API for all resource types; serialises to protobuf / JSON |
| `agent/event_stream` | Batches collected data and pushes to platform API over mTLS |

### Agent DaemonSet (1 pod per node)

| Module | Responsibility |
|---|---|
| `agent/metrics_collection` | Scrapes Kubelet Summary API (`/stats/summary`) on the local node every 60 seconds |
| `agent/health_reporting` | Reports node-level health signals to the Controller |

### Agent Communication Protocol

- Agent → Platform: HTTPS with client certificate authentication (mTLS). Certificate issued during registration, rotated by `token_rotation`.
- Platform → Agent: Platform does not push to agent directly. The agent polls for instructions (upgrade, configuration changes) during each heartbeat response.
- Data format: JSON over HTTP/2.

---

## 17. Infrastructure Module Reference

### `infrastructure/aws`
- Terraform modules for the BalanceKube platform AWS infrastructure.
- VPC, subnets, security groups.
- RDS PostgreSQL instance.
- ElastiCache Redis cluster.
- ECS or EKS for platform services.
- IAM roles for platform services.
- S3 bucket for snapshot storage (if snapshots exceed DB blob size threshold).

### `infrastructure/kubernetes`
- Helm chart (`charts/balancekube-agent`) for agent deployment.
- Values: `registrationToken`, `platformEndpoint`, `logLevel`, `resources`, `tolerations`, `nodeSelector`.
- RBAC: ClusterRole granting `list`, `watch`, `get` on all collected resource types. No write permissions.

### `infrastructure/monitoring`
- Prometheus scrape configs for platform services.
- Grafana dashboards: pipeline throughput, phase latencies, recommendation quality metrics, execution success rate.
- Alerting rules: agent heartbeat missing, Phase 2 analysis taking > 30 minutes, execution failure, drift invalidation rate spike.
- Observability also tracks worker retry rate, dead-letter queue depth, event publish latency, and partition retention health.

---

## 18. Shared Module Reference

### `shared/aws`
AWS SDK v3 wrappers with standardised error handling, retries, and credential injection from the organisation's assumed-role session.

Key exports: `assumeRole(arn, externalId)`, `describeInstances()`, `getSpotPriceHistory()`, `callCloudFormation()`, `getPricingData()`

### `shared/kubernetes`
Kubernetes client-go wrappers for platform-side Kubernetes calls (e.g. to the customer cluster via the agent proxy).

### `shared/pricing`
Pricing calculation helpers: `computeMonthlyCost(instanceType, region, pricingType)`, `computeSavings(current, target)`, `getPriceFreshness(priceRecord)`.

### `shared/events`
Event type definitions (TypeScript discriminated unions), publisher interface, and consumer base class. All event payloads include `event_id` (UUID), `emitted_at` (timestamp), `schema_version`.

### `shared/logging`
Structured JSON logger (pino / zap). Standard fields: `service`, `phase`, `cluster_id`, `snapshot_id`, `analysis_version`, `trace_id`. Log levels: `trace`, `debug`, `info`, `warn`, `error`.

### `shared/security`
- JWT signing/verification (RS256, keys managed in AWS Secrets Manager).
- Encryption helpers for sensitive fields (agent credentials, IAM role ARNs) at rest using AES-256-GCM.
- Secrets management client (AWS Secrets Manager).

### `shared/validation`
Zod schemas for all API request/response types and event payloads. Used both in backend (request validation) and frontend (form validation and API response parsing).

### `shared/constants`
System-wide enumerations: `ClusterStatus`, `RecommendationStatus`, `ExecutionStatus`, `WorkloadClassification`, `EligibilityVerdict`, `DriftType`, `SpotRiskLevel`, `AnalysisVersion`.

---

## 19. Database Schema Overview

### Core Tables

```sql
-- Organisations and Users
organizations        (id, name, external_id, aws_role_arn, created_at)
users                (id, org_id, email, role, created_at)
memberships          (id, user_id, org_id, role)

-- Cluster Registry
clusters             (id, org_id, name, region, k8s_version, status, cluster_hash, created_at)
agents               (id, cluster_id, version, last_heartbeat_at, status)
agent_tokens         (id, agent_id, token_hash, expires_at, rotated_at)

-- Inventory (Phase 1 output)
nodes                (id, cluster_id, snapshot_id, name, instance_type, az, capacity_cpu_m, capacity_memory_mi, allocatable_cpu_m, allocatable_memory_mi, labels, taints, conditions, collected_at)
pods                 (id, cluster_id, snapshot_id, name, namespace, owner_kind, owner_name, node_id, phase, req_cpu_m, req_memory_mi, lim_cpu_m, lim_memory_mi, labels, annotations, collected_at)
deployments          (id, cluster_id, snapshot_id, name, namespace, replicas, selector, labels, annotations, collected_at)
statefulsets         (id, cluster_id, snapshot_id, name, namespace, replicas, volume_claim_templates, collected_at)
daemonsets           (id, cluster_id, snapshot_id, name, namespace, update_strategy, collected_at)
pvcs                 (id, cluster_id, snapshot_id, name, namespace, storage_class, access_modes, capacity_gi, phase, pod_id, collected_at)
pdbs                 (id, cluster_id, snapshot_id, name, namespace, min_available, max_unavailable, current_healthy, desired_healthy, collected_at)

-- Metrics (Phase 1 output, time-series)
cpu_metrics          (id, cluster_id, pod_id, node_id, value_m, collected_at)
memory_metrics       (id, cluster_id, pod_id, node_id, value_mi, collected_at)
network_metrics      (id, cluster_id, node_id, rx_kbps, tx_kbps, collected_at)
filesystem_metrics   (id, cluster_id, node_id, pvc_id, used_gi, capacity_gi, collected_at)

-- Pricing (Phase 1, platform-managed)
on_demand_prices     (id, instance_type, region, price_usd_hr, updated_at)
spot_prices          (id, instance_type, region, az, price_usd_hr, collected_at)
instance_catalog     (id, instance_type, vcpu, memory_gi, network_perf, family, updated_at)
risk_scores          (id, instance_type, region, risk_score, interruption_band, updated_at)

-- Snapshots (Phase 1 → Phase 2)
assembled_snapshots  (id, cluster_id, cluster_hash, assembly_version, schema_version, payload_ref, collected_at)

-- Workload Intelligence (Phase 2)
workload_reviews     (id, cluster_id, snapshot_id, status, created_at, completed_at, completed_by)
workload_tags        (id, cluster_id, workload_id, analysis_version, tags jsonb, classification, confidence, created_at)
workload_analysis    (id, cluster_id, workload_id, analysis_version, cpu_analysis jsonb, memory_analysis jsonb, network_analysis jsonb, storage_analysis jsonb, data_maturity, created_at)
eligibility_verdicts (id, cluster_id, workload_id, analysis_version, verdict, decision_reasons jsonb, operator_override_id, created_at)
operator_overrides   (id, cluster_id, workload_id, spot_eligible, target_instance_families, max_risk_score, set_by, set_at, note)
recommendation_store (id, cluster_id, snapshot_id, analysis_version, cluster_hash, status, total_savings_monthly, created_at, approved_at, approved_by)
savings_estimates    (id, recommendation_id, workload_id, current_instance_type, current_cost_monthly, recommended_instance_type, spot_cost_monthly, savings_monthly, savings_pct, spot_risk_score, pricing_freshness_at)

-- Drift Detection (Phase 3)
drift_events         (id, cluster_id, recommendation_id, drift_type, severity, patchable, affected_workloads jsonb, detected_at)
plan_deltas          (id, recommendation_id, delta_payload jsonb, created_at)

-- Execution (Phase 4)
execution_history    (id, cluster_id, recommendation_id, status, started_at, completed_at, nodes_provisioned, nodes_drained, workloads_migrated, savings_realised_monthly, failure_reason, rollback_reason)
execution_locks      (id, cluster_id, acquired_at, expires_at, execution_id)
rollback_snapshots   (id, execution_id, cluster_id, payload_ref, created_at, status)

-- Platform
audit_logs           (id, org_id, actor_id, action, resource_type, resource_id, before jsonb, after jsonb, ip_address, created_at)
event_store          (id, event_type, payload jsonb, schema_version, published, emitted_at, published_at)
dead_letter_jobs     (id, worker, job_payload jsonb, error, attempts, created_at)
notifications        (id, org_id, type, recipient, payload jsonb, sent_at, status)
```

---

---

## 20. Database Ownership

Every table in the platform database has a single owning feature domain. Only the owning domain's backend module may write to that table. Other domains must read via the owning module's API or service layer — never via direct cross-domain queries.

| Table | Owner Domain | Owner Module |
|---|---|---|
| `organizations` | Onboarding | `backend/organizations` |
| `users` | Onboarding | `backend/users` |
| `memberships` | Onboarding | `backend/users` |
| `api_keys` | Onboarding | `backend/users` |
| `clusters` | Onboarding | `backend/onboarding` |
| `cloudformation_stacks` | Onboarding | `backend/onboarding` |
| `agents` | Agent Management | `backend/agent_management` |
| `agent_tokens` | Agent Management | `backend/agent_management` |
| `nodes` | Cluster Inventory | `backend/cluster_inventory/nodes` |
| `pods` | Cluster Inventory | `backend/cluster_inventory/pods` |
| `deployments` | Cluster Inventory | `backend/cluster_inventory/deployments` |
| `statefulsets` | Cluster Inventory | `backend/cluster_inventory/statefulsets` |
| `daemonsets` | Cluster Inventory | `backend/cluster_inventory/daemonsets` |
| `pvcs` | Cluster Inventory | `backend/cluster_inventory/pvc` |
| `pdbs` | Cluster Inventory | `backend/cluster_inventory/pdb` |
| `namespaces` | Cluster Inventory | `backend/cluster_inventory/namespaces` |
| `cpu_metrics` | Metrics Collection | `backend/metrics_collection/cpu` |
| `memory_metrics` | Metrics Collection | `backend/metrics_collection/memory` |
| `network_metrics` | Metrics Collection | `backend/metrics_collection/network` |
| `filesystem_metrics` | Metrics Collection | `backend/metrics_collection/filesystem` |
| `on_demand_prices` | Pricing Collection | `backend/pricing_collection/on_demand` |
| `spot_prices` | Pricing Collection | `backend/pricing_collection/spot_price` |
| `instance_catalog` | Pricing Collection | `backend/pricing_collection/instance_catalog` |
| `interruption_rates` | Spot Risk Collection | `backend/spot_risk_collection/interruption_rates` |
| `risk_scores` | Spot Risk Collection | `backend/spot_risk_collection/risk_normalization` |
| `spot_risk_history` | Spot Risk Collection | `backend/spot_risk_collection/historical_dataset` |
| `assembled_snapshots` | Snapshot Assembly | `backend/snapshot_assembly` |
| `workload_reviews` | Workload Review | `backend/workload_review` |
| `review_items` | Workload Review | `backend/workload_review` |
| `workload_tags` | Workload Classification | `backend/workload_classification/tag_generation` |
| `workload_classifications` | Workload Classification | `backend/workload_classification` |
| `workload_analysis` | Resource Analysis | `backend/resource_analysis` |
| `eligibility_verdicts` | Eligibility Engine | `backend/eligibility_engine` |
| `operator_overrides` | Eligibility Engine | `backend/eligibility_engine/operator_overrides` |
| `decision_reasons` | Eligibility Engine | `backend/eligibility_engine` |
| `recommendation_store` | Recommendations | `backend/recommendations` |
| `savings_estimates` | Recommendations | `backend/recommendations` |
| `drift_events` | Drift Detection | `backend/drift_detection/snapshot_comparator` |
| `plan_deltas` | Drift Detection | `backend/drift_detection/plan_delta` |
| `execution_history` | Execution | `backend/execution/execution_history` |
| `execution_locks` | Execution | `backend/execution/lock_manager` |
| `rollback_snapshots` | Rollback | `backend/rollback` |
| `audit_logs` | Audit | `backend/audit_logs` |
| `event_store` | Events | `backend/events` |
| `dead_letter_jobs` | Workers | `workers/common` |
| `notifications` | Notifications | `backend/notifications` |

### Ownership Rules

- A module that needs data from another domain's table must call that domain's **service layer function**, not issue a raw SQL query against the table.
- Migrations for a table must be authored by the owning domain's team.
- Cross-domain `JOIN`s are permitted in **read-only** analytical queries (e.g. dashboard aggregations) but must be clearly marked with a `-- cross-domain read` comment and reviewed carefully.

---

## 21. Event Catalog

All inter-domain communication uses domain events persisted to `event_store` before publishing (outbox pattern) to guarantee at-least-once delivery. Every event includes a standard envelope: `event_id` (UUID v4), `event_type` (string), `schema_version` (integer), `emitted_at` (timestamp), `cluster_id` (where applicable).

### `org.created`
```
Producer:  backend/organizations
Consumers: workers/onboarding

Payload:
  org_id        uuid
  name          string
  external_id   uuid

Purpose:
  Triggers async onboarding jobs — CloudFormation template pre-generation
  and initial AWS access validation.
```

### `cluster.registered`
```
Producer:  backend/onboarding
Consumers: workers/cluster_inventory

Payload:
  cluster_id    uuid
  org_id        uuid
  region        string
  k8s_version   string

Purpose:
  Triggers initial inventory collection and schedules the recurring
  metrics collection job for the new cluster.
```

### `cluster.collected`
```
Producer:  workers/snapshot_assembly
Consumers: workers/workload_classification
           workers/workload_review (review gate check)

Payload:
  cluster_id      uuid
  snapshot_id     uuid
  cluster_hash    sha256
  collected_at    timestamp
  assembly_version integer

Purpose:
  Signals that a complete assembled_snapshot is available.
  Workload review checks the gate; classification begins if gate is open.
```

### `review.pending`
```
Producer:  workers/workload_review
Consumers: workers/notifications

Payload:
  cluster_id    uuid
  review_id     uuid
  review_type   enum(initial, partial)
  workload_count integer

Purpose:
  Triggers operator notification that a review is waiting for their action.
```

### `review.completed`
```
Producer:  backend/workload_review
Consumers: workers/workload_classification

Payload:
  cluster_id    uuid
  review_id     uuid
  snapshot_id   uuid
  completed_by  uuid (user_id)

Purpose:
  Unblocks the Phase 2 analysis pipeline after operator sign-off.
```

### `cluster.analysed`
```
Producer:  workers/recommendations
Consumers: workers/drift_detection

Payload:
  cluster_id          uuid
  recommendation_id   uuid
  snapshot_id         uuid
  analysis_version    integer
  cluster_hash        sha256
  analysed_at         timestamp
  total_savings_monthly decimal

Purpose:
  Signals a complete recommendation is stored and ready for drift
  monitoring. Drift detection begins immediately and runs on schedule.
```

### `drift.detected`
```
Producer:  workers/drift_detection
Consumers: workers/notifications

Payload:
  cluster_id          uuid
  recommendation_id   uuid
  drift_types         string[]    // e.g. ["node_removed", "replica_count_changed"]
  patchable           boolean
  severity            enum(low, medium, high)
  affected_workloads  uuid[]

Purpose:
  Informs the operator that the cluster state has diverged from the plan.
  Sent for both patchable and invalidating drift.
```

### `drift.patchable`
```
Producer:  workers/drift_detection
Consumers: (internal — updates recommendation record directly; no async consumer)

Payload:
  cluster_id          uuid
  recommendation_id   uuid
  plan_delta_id       uuid
  new_analysis_version integer

Purpose:
  Recorded in event_store for audit. The plan_delta is applied synchronously
  within the drift detection worker.
```

### `drift.invalidated`
```
Producer:  workers/drift_detection
Consumers: workers/workload_classification  (triggers Phase 2 reanalysis)
           workers/notifications

Payload:
  cluster_id          uuid
  recommendation_id   uuid
  invalidation_reason string
  new_snapshot_id     uuid        // current snapshot to reanalyse from

Purpose:
  Discards the stale recommendation and restarts the full analysis pipeline
  from the current live state.
```

### `recommendation.approved`
```
Producer:  backend/recommendations
Consumers: workers/execution

Payload:
  cluster_id          uuid
  recommendation_id   uuid
  snapshot_id         uuid
  analysis_version    integer
  cluster_hash        sha256
  approved_by         uuid (user_id)
  approved_at         timestamp

Purpose:
  Triggers Phase 4 execution. The three-part identity is embedded in the
  payload so the execution worker can validate without an extra DB round-trip.
```

### `execution.started`
```
Producer:  workers/execution
Consumers: workers/notifications

Payload:
  cluster_id      uuid
  execution_id    uuid
  recommendation_id uuid
  plan_summary    object    // node count, workload count

Purpose:
  Notifies the operator that execution has begun.
```

### `execution.completed`
```
Producer:  workers/execution (success) / workers/rollback (rollback)
Consumers: workers/cluster_inventory   (triggers immediate Phase 1 refresh)
           workers/notifications

Payload:
  cluster_id              uuid
  execution_id            uuid
  status                  enum(success, rolled_back)
  nodes_provisioned       integer
  nodes_drained           integer
  workloads_migrated      integer
  savings_realised_monthly decimal
  failure_reason          string (nullable)

Purpose:
  Closes the execution loop. Triggers an immediate Phase 1 data collection
  cycle so the platform's view of the cluster reflects post-execution reality.
```

### `execution.rolled_back`
```
Producer:  workers/rollback
Consumers: workers/notifications

Payload:
  cluster_id      uuid
  execution_id    uuid
  rollback_reason string
  restored_at     timestamp

Purpose:
  Confirms the cluster has been restored to its pre-execution state.
  Sent in addition to execution.completed (status=rolled_back) for
  targeted alerting rules.
```

### `agent.heartbeat_missed`
```
Producer:  backend/agent_management  (scheduled check)
Consumers: workers/notifications

Payload:
  cluster_id    uuid
  agent_id      uuid
  last_seen_at  timestamp
  missed_count  integer

Purpose:
  Alerts the operator that an agent has gone silent. Triggered when
  no heartbeat is received within 3× the expected interval (default: 90s).
```

### `agent.token_rotated`
```
Producer:  agent/token_rotation (agent-initiated) or backend/agent_management (platform-initiated)
Consumers: workers/notifications (optional audit notification)

Payload:
  cluster_id    uuid
  agent_id      uuid
  rotated_at    timestamp

Purpose:
  Records successful token/certificate rotation for audit and compliance.
```

### Event Delivery Guarantees

| Guarantee | Mechanism |
|---|---|
| At-least-once delivery | Events written to `event_store` before publish; unpublished events are retried by a sweeper job |
| Ordering | Per-cluster ordering guaranteed within a single domain. Cross-domain ordering is not guaranteed — consumers must be idempotent |
| Dead-lettering | Workers that fail to process an event after all retries write to `dead_letter_jobs` |
| Schema evolution | `schema_version` field allows consumers to handle multiple versions during rolling deployments |

---

## 22. Security Model

### Cross-Account Access
- IAM Role with `sts:AssumeRole` trust locked to `ExternalId` (per-organisation UUID).
- Minimum-privilege IAM policy: read-only EC2/EKS/Pricing/SpotAdvisor access. No write permissions to customer account.
- Role ARN stored encrypted at rest using AES-256-GCM.

### Agent Authentication
- Agent authenticates to the platform using a client certificate (mTLS).
- Certificate issued during registration (signed by platform CA), valid for 30 days.
- `agent/token_rotation` rotates certificate 7 days before expiry.
- All agent → platform traffic over HTTPS/TLS 1.3.

### API Authentication
- Frontend and API consumers authenticate via JWT (RS256, 1-hour TTL, refresh token 30 days).
- API keys available for programmatic access (hashed in DB, never stored in plaintext).

### Agent RBAC (In-Cluster)
- `ClusterRole` grants: `list`, `watch`, `get` on `nodes`, `pods`, `deployments`, `statefulsets`, `daemonsets`, `persistentvolumeclaims`, `poddisruptionbudgets`, `namespaces`.
- No `create`, `update`, `delete`, `patch` permissions.
- Execution-phase Kubernetes writes (drain, apply affinity) are performed via the platform's assumed IAM role through the EKS API, not through the agent.

### Multi-Tenancy
- All database queries include `org_id` or `cluster_id` scoped to the authenticated user's organisation.
- Row-level security is enabled for all org-scoped tables; the platform sets `app.current_org_id` on every DB session so policies automatically filter access.
- No cross-organisation data leakage possible at the query layer.

---

## 23. API Surface

### REST API Base Path: `/api/v1`

| Method | Path | Description |
|---|---|---|
| `POST` | `/orgs` | Create organisation |
| `GET` | `/orgs/:id` | Get organisation |
| `POST` | `/orgs/:id/cloudformation` | Generate CloudFormation template |
| `POST` | `/orgs/:id/validate-role` | Validate AWS IAM role |
| `GET` | `/orgs/:id/clusters/discover` | Discover EKS clusters |
| `POST` | `/clusters` | Register cluster |
| `GET` | `/clusters/:id` | Get cluster details |
| `GET` | `/clusters/:id/nodes` | List nodes |
| `GET` | `/clusters/:id/pods` | List pods |
| `GET` | `/clusters/:id/deployments` | List deployments |
| `GET` | `/clusters/:id/reviews` | List workload reviews |
| `POST` | `/clusters/:id/reviews/:review_id/complete` | Complete review |
| `GET` | `/clusters/:id/recommendations` | List recommendations |
| `GET` | `/clusters/:id/recommendations/:rec_id` | Get recommendation detail |
| `POST` | `/clusters/:id/recommendations/:rec_id/approve` | Approve recommendation |
| `GET` | `/clusters/:id/drift` | Get current drift status |
| `POST` | `/clusters/:id/executions` | Trigger execution (approved rec required) |
| `GET` | `/clusters/:id/executions` | List execution history |
| `GET` | `/clusters/:id/executions/:exec_id` | Get execution detail |
| `POST` | `/clusters/:id/overrides` | Set operator override |
| `GET` | `/clusters/:id/overrides` | List operator overrides |
| `POST` | `/api/v1/agents/register` | Agent registration |
| `POST` | `/api/v1/agents/:id/heartbeat` | Agent heartbeat |
| `POST` | `/api/v1/agents/:id/metrics` | Agent metrics push |
| `POST` | `/api/v1/agents/:id/inventory` | Agent inventory push |

The frontend contract is aligned with backend schemas via shared TypeScript types and API models in `frontend/shared` and `shared/validation`. API endpoints are the single source of truth for UI workflows and are versioned consistently with the backend service.

---

## 24. Testing Strategy

### Unit Tests (`tests/unit/`)
- Every detector in `workload_classification` has unit tests with fixture snapshots covering positive, negative, and edge cases.
- Eligibility engine rules each have dedicated unit tests.
- Snapshot comparator has tests for all diff types (patchable and invalidating).
- Savings estimator has tests for freshness validation and calculation correctness.

### Integration Tests (`tests/integration/`)
- Phase 1 → Phase 2 pipeline: uses a pre-built test snapshot and validates classification and eligibility outputs.
- Phase 3 drift detection: test fixtures for each drift type, validating patchable vs invalidating outcomes.
- Phase 4 execution: uses a mock Kubernetes API and mock AWS API to simulate full execution including rollback.

### End-to-End Tests (`tests/e2e/`)
- Onboarding flow: spins up a local mock AWS API and Kubernetes cluster (kind), runs the full onboarding pipeline.
- Full pipeline test: ingests a fixture snapshot, runs all phases, validates that an execution record is written.

### Agent Tests (`agent/*_test.go`)
- Go unit tests for all agent modules.
- Integration tests against a real `kind` cluster verifying inventory collection accuracy.

---

## 25. Deployment & Scripts

### `scripts/`

| Script | Purpose |
|---|---|
| `scripts/migrate.sh` | Run database migrations (uses `golang-migrate` or `node-pg-migrate`) |
| `scripts/seed.sh` | Seed development database with fixture data (test org, cluster, snapshots) |
| `scripts/deploy-platform.sh` | Deploy platform services to ECS/EKS (calls Terraform + Docker build) |
| `scripts/deploy-agent.sh` | Publish Helm chart to chart registry and tag new agent version |
| `scripts/build-cloudformation.sh` | Generate and validate CloudFormation template from template source |
| `scripts/rotate-keys.sh` | Rotate JWT signing keys and agent CA certificate |
| `scripts/backfill-pricing.sh` | Backfill historical AWS pricing data for a given region |
| `scripts/debug-snapshot.sh` | CLI tool to inspect an `assembled_snapshot` by ID |

---

## 26. Cross-Cutting Concerns

### Idempotency
- All workers are designed to be idempotent. Re-running a worker with the same inputs produces the same output without side effects.
- Snapshot assembly is idempotent: if a snapshot for `(cluster_id, collected_at_window)` already exists, the job is a no-op.
- Execution jobs are not idempotent by nature — the cluster lock prevents duplicate execution.

### Observability
- All phases emit structured logs with `cluster_id`, `snapshot_id`, `analysis_version`, `trace_id`.
- Phase latency metrics: time from `cluster.collected` to `cluster.analysed` (Phase 2 duration), time from `cluster.analysed` to `execution_ready` (Phase 3 duration).
- Business metrics: recommendations generated per day, savings estimated vs savings realised, rollback rate, drift invalidation rate.

### Error Handling
- All external API calls (AWS, Kubernetes) use exponential backoff with jitter.
- Worker failures are captured in `dead_letter_jobs` with full context.
- Phase 4 execution failures always trigger the rollback engine — there is no failure mode that leaves the cluster in an intermediate state without attempting recovery.

### Versioning
- `analysis_version` is a monotonically increasing integer per cluster. Major bumps occur when the eligibility rule set changes. Minor bumps occur when plan deltas are applied.
- `assembly_version` is a global version counter for the snapshot schema.
- `schema_version` in events ensures consumers can detect and handle schema evolution.

---

## 27. Folder Documentation Standard

Every folder in the repository was created with a corresponding `.md` file by the project initialisation script. These files are not optional — they are the primary documentation artefact for that module. The root `balancekube.md` (this file) is the navigation hub; each folder `.md` is the deep-dive.

### Required Structure for Every Folder `.md`

Every folder `.md` file **must** contain the following sections. Sections that do not apply should be included with the value `N/A` rather than omitted — this makes it immediately clear the author considered them.

```markdown
# <folder-name>

## Purpose
One or two sentences. What problem does this module solve?
Why does it exist as a separate module rather than being part of another?

## Responsibilities
Bullet list. What this module does.
Be specific — avoid "handles X" without explaining how.

## Inputs
What data or events does this module receive?
- Source: (event name, API call, database table read, function argument)
- Format: (JSON schema ref, TypeScript type, protobuf message)

## Outputs
What does this module produce?
- Destination: (event name, database table written, API response, return value)
- Format: (schema ref or type)

## Events Produced
List each event emitted, with a one-line description.
N/A if none.

## Events Consumed
List each event this module subscribes to, and what it does in response.
N/A if none.

## Database Tables
Tables this module owns (writes to).
Tables this module reads (read-only cross-domain access clearly marked).

## APIs
REST endpoints exposed by this module (backend modules only).
Method, path, brief description.
N/A for workers, agent, shared.

## Dependencies
Other modules or external services this module depends on.
Be explicit about shared library usage.

## Configuration
Environment variables or config keys that affect this module's behaviour.
Include defaults and valid ranges where applicable.

## Error Handling
How does this module handle failures?
What are the retry strategies? What goes to dead-letter?

## Future Enhancements
Known limitations or planned improvements.
Reference any GitHub issues or design docs if available.
```

### Enforcement

- PR reviews for any module must check that the folder `.md` is updated if the module's interface, tables, events, or behaviour changed.
- New sub-folders must include a `.md` before the PR is merged.
- The `docs/` folder contains a linting script (`docs/lint-folder-docs.sh`) that checks for presence and required section headings.

---

## 28. Agent Lifecycle Management

The agent is a long-lived process running inside customer infrastructure. Unlike platform services that can be redeployed at will, agent upgrades and lifecycle operations require careful coordination to avoid disrupting cluster data collection.

### Agent States

```
unregistered  →  registered  →  active  →  degraded  →  unreachable
                                   ↑                          |
                                   └──────── recovered ────────┘
                                   
active → upgrading → active (on success)
active → upgrading → rollback → active (on failure)
```

### Registration (`agent/registration`)
- Triggered once on first startup using the short-lived `registration_token` (1-hour TTL).
- Platform validates token, creates `agents` record, issues long-lived client certificate.
- Agent stores certificate in a Kubernetes Secret in its own namespace.
- Registration is idempotent: if the agent restarts and finds a valid certificate, it skips registration.

### Heartbeat (`agent/heartbeat`)
- Agent sends a `POST /api/v1/agents/:id/heartbeat` every 30 seconds.
- Payload includes: `agent_version`, `cluster_id`, `collection_cycle_count`, `last_error` (if any), node count seen.
- Platform updates `agents.last_heartbeat_at`.
- If no heartbeat is received for 90 seconds (3× interval), platform emits `agent.heartbeat_missed` event.
- If no heartbeat for 10 minutes: cluster status transitions to `degraded`. Operator is alerted.
- If no heartbeat for 30 minutes: cluster status transitions to `unreachable`.

### Token / Certificate Rotation (`agent/token_rotation`)
- Agent certificate is valid for 30 days.
- `agent/token_rotation` initiates rotation 7 days before expiry.
- Rotation sequence:
  1. Agent requests a new certificate from `POST /api/v1/agents/:id/rotate-token`.
  2. Platform issues new certificate signed by platform CA.
  3. Agent stores new certificate, continues using old certificate until new one is confirmed accepted.
  4. Agent sends one heartbeat using new certificate.
  5. Platform marks old certificate as retired.
- If rotation fails (platform unreachable): agent retries every 5 minutes for the remaining validity window.
- If certificate expires before rotation succeeds: agent re-registers using a new operator-issued token.

### Upgrades (`agent/upgrades`)
- Platform operators publish new agent versions to the agent upgrade registry.
- During each heartbeat response, platform includes `available_upgrade` field if a newer version exists.
- Agent checks `available_upgrade` and initiates a rolling upgrade of itself:
  1. Downloads new agent binary from platform-signed URL.
  2. Verifies binary checksum (SHA-256, signed by platform key).
  3. Restarts the Controller Deployment with the new image — Kubernetes rolling update handles continuity.
  4. DaemonSet pods are updated node by node.
- Upgrade is confirmed when all pods report the new `agent_version` in their next heartbeat.
- On upgrade failure (new version crashes on startup): Kubernetes rolling update rollback kicks in automatically. Platform is notified via heartbeat version mismatch.

### Permission Revalidation
- On each agent startup (including after upgrade), the agent validates that its RBAC permissions match the required permission set defined in `infrastructure/kubernetes/rbac.yaml`.
- If permissions are missing: agent logs a `permission_drift` error and reports it in the heartbeat payload.
- Platform surfaces a `permission_drift` alert in the UI, prompting the operator to re-apply the Helm chart.

### Agent Uninstall
- Operator initiates uninstall from the UI: `DELETE /clusters/:id/agent`.
- Platform marks the cluster as `uninstalling` and sends an uninstall instruction in the next heartbeat response.
- Agent gracefully terminates collection cycles, flushes any pending data, and deletes its Kubernetes Secret (certificate).
- Helm release is deleted by the operator: `helm uninstall balancekube-agent`.
- Platform transitions cluster to `inactive` after receiving the final heartbeat with `shutdown: true` flag.
- All cluster data is retained in the platform database until the operator explicitly deletes the cluster record.

### Operational Runbook Summary

| Situation | Resolution |
|---|---|
| Agent `unreachable` | Check Kubernetes pod status in customer cluster. Re-apply Helm chart if pods are missing. |
| Certificate expired | Operator generates new registration token in UI. Agent re-registers. |
| Permission drift alert | Operator runs `helm upgrade balancekube-agent` with latest chart to restore RBAC. |
| Upgrade stuck | Check Kubernetes rollout status. If new pods crash, old pods remain serving — no data gap. |
| Agent shows old version after upgrade | Verify Deployment image tag. Force rollout restart if needed. |

---

## 29. Decision Log & Design Rationale

### Why immutable snapshots?
Drift detection requires comparing a fixed "what we planned" state against a live "what exists now" state. Mutating the snapshot would destroy the ability to detect drift accurately. Immutability also enables replay: any past recommendation can be reconstructed by replaying Phase 2 against the original snapshot.

### Why a three-part plan identity (`snapshot_id` + `analysis_version` + `cluster_hash`)?
Each component guards against a different class of stale execution:
- `snapshot_id` prevents using a recommendation built on old data if the snapshot has been superseded.
- `analysis_version` prevents using a recommendation if the analysis logic has been updated (e.g. a new hard rule was added that would now block a workload).
- `cluster_hash` prevents executing a plan if the cluster topology has changed (e.g. a node type was replaced), which would invalidate all node-level placement decisions.

### Why operator review gates?
The first cycle introduces BalanceKube to a cluster the operator may not have fully mapped. Requiring human validation before executing any changes builds trust and catches misclassifications early. The partial review gate for new workloads maintains the same safety guarantee on an ongoing basis.

### Why an event-driven architecture between phases?
Phases have very different latency characteristics: Phase 1 runs every few minutes, Phase 2 may take several minutes for large clusters, Phase 3 runs continuously, Phase 4 is triggered by human action. An event-driven model decouples these rates and allows each phase to scale independently. It also provides natural retry points: if Phase 2 fails, re-emitting `cluster.collected` is sufficient to restart it.

### Why Go for the agent?
The agent runs inside customer infrastructure and must have a minimal footprint. Go produces a single static binary with no runtime dependencies, which simplifies deployment, upgrade, and security hardening. The `controller-runtime` library provides battle-tested Kubernetes informer patterns that would require significant custom work in Node.js.

### Why no write permissions for the agent?
The agent runs inside the customer cluster with broad read access to cluster state. Granting it write permissions would expand the blast radius if the agent were compromised. All cluster mutations (drain, placement configuration) are performed from the platform side using the customer's assumed IAM role through the EKS API, which provides a separate, auditable access path.

---

*This document is the authoritative root-level reference for the BalanceKube project. It is repository-driven: every section maps to a folder, a domain, or a cross-cutting concern that a developer will actually work in. Each sub-folder's `.md` file must follow the structure defined in Section 27 and must stay consistent with the flows, table names, event names, and design decisions documented here. When in doubt, defer to this document for naming conventions, data contracts, phase boundaries, and database ownership.*