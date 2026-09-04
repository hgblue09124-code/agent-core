# Architecture Decision Record: Personal Agent Beta v0.1 Composition

**Status**: **ACCEPTED**
**Date**: 2026-09-04
**Context**: Personal Agent Beta v0.1 Composition Architecture
**Target Repository**: `Agent-Core` (`hgblue09124-code/agent-core`)

---

## 1. Context & Principles

The Personal Agent ecosystem comprises three distinct, modular repositories:
1. **`agent-core`**: The authoritative kernel responsible for agent identity, cognition, policy authorization, orchestration, experience recording, strategy learning, and state continuity.
2. **`agent-personal-vault`**: The persistent personal data and memory storage layer.
3. **`agent-capabilities`**: Pluggable external capabilities framework (e.g. GitHub API, shell tools).

### Core Invariant
**Agent-Core is the Kernel. Vault and Capabilities are replaceable modules.**
Core must remain a stable, lightweight kernel. It must NOT become a monolith, embed capability-specific business logic, or couple directly to concrete external cloud/storage services.

---

## 2. Architectural Decisions

### ADR-01: Core Composition Authority Boundary
- **Decision**: Core communicates with Vault via `PersonalVaultAdapter` (`core/vault/adapter.py`) and with external capabilities via `CapabilityRegistry` / `ExternalCapabilityBridge` (`core/capabilities/bridge.py`).
- **Rationale**: Keeps Core isolated from concrete third-party package dependencies while providing immediate local fallback resilience if external modules are absent.

### ADR-02: Policy & Permission Authorization
- **Decision**: `PolicyEngine` (`core/kernel/policy.py`) owns the authorization boundary (`authorize_capability`).
- **Enforcement Rules**:
  - Mutating/write actions (e.g. `create_issue_comment`) or capabilities marked `requires_user_approval` require explicit user authorization (`user_approved=True`).
  - Read-only actions remain approval-free unless restricted by policy.
  - Denied requests return `status="DENIED"` and never execute downstream capabilities.
  - `CapabilityRegistry.invoke()` is documented as a low-level internal primitive; all public agent invocations MUST route through `Agent.execute_capability()`.

### ADR-03: Honest Failure Semantics & External Error Propagation
- **Decision**: `SUCCESS` must strictly mean the requested action succeeded. External API HTTP errors (401, 403, 404, 503) or network failures return `status="FAILED"`.
- **Rationale**: Prevents external API failures from being masqueraded as fake successes or polluting persistent memory/experience logs.
- **Offline Mock Execution**: Mock/simulated responses are restricted to explicit mock flags (`mock_offline=True` or `AGENTCORE_PLANNER_PROVIDER=mock`) and clearly flagged in metadata (`simulated_mock=True`).

### ADR-04: Process-Restart State Continuity
- **Decision**: State persistence is file-backed (`MemoryStore`, `ExperienceStore`, `CheckpointStore`) using atomic file writes (`.tmp` -> `fsync` -> `os.replace`).
- **Rationale**: Ensures that instantiating a new `Agent` instance reloads run checkpoints, memory entries, and strategy records from disk cleanly, proving true process-restart continuity.

### ADR-05: Evidence Classification
- **Decision**: All test and benchmark evidence must be classified strictly as:
  - **`STATIC`**: Code/schema structure inspection.
  - **`MOCK/LOCAL`**: Local unit/integration tests running with mock planners or local disk storage.
  - **`REAL_EXTERNAL`**: Live HTTP network calls to external APIs. Unauthenticated calls without live API tokens MUST be recorded as `NOT EXECUTED`.

---

## 3. Deferred Infrastructure (Explicit Scope Boundaries)

The following speculative features are explicitly deferred until real Beta usage demonstrates the need:
- Vector databases / embedding-based RAG.
- Native iCloud synchronization.
- Multi-agent swarm architectures.
- Autonomous 24/7 background loops.
- Fine-tuning and complex cloud infrastructure.

---

## 4. Consequences

- **Positive**: Core remains lightweight, verifiable, and deterministically testable. External failure propagation and permission boundaries are explicit.
- **Verification**: All 15 Beta missions and regression suites pass cleanly locally (`MOCK/LOCAL`). Live external calls require explicitly provided API tokens (`GITHUB_TOKEN`).
