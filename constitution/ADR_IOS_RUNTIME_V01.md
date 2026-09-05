# Architecture Decision Record: Native iOS Local Runtime Contract v0.1

**Status**: **ACCEPTED**
**Date**: 2026-09-04
**Target Architecture**: Native Full-Local Personal Agent on iOS / iPhone
**Target Repository**: `Agent-Core` (`hgblue09124-code/agent-core`)

---

## 1. Context & Architectural Boundary

The Personal Agent target architecture on iOS consists of two strictly separated layers:

```
┌─────────────────────────────────────────────────────────┐
│              NATIVE iOS APPLICATION (UI / OS)           │
│ SwiftUI | UIKit | Keychain | EventKit | BGTaskScheduler │
└────────────────────────────┬────────────────────────────┘
                             │
                             │ Local Native Service Contract
                             ▼
┌─────────────────────────────────────────────────────────┐
│                 AGENT-CORE KERNEL (Authority)           │
│ Identity | Cognition | Memory Model | Policy | Learning │
│ Orchestration | Experience | Continuity | Capabilities  │
└─────────────────────────────────────────────────────────┘
```

### Responsibility Delineation

#### Agent-Core Kernel Responsibilities
- **Identity & Persona**: Definition and preservation of primary agent identity.
- **Cognition & Reasoning**: Planning, step decomposition, and strategy selection.
- **Memory Model**: Semantic structure for short-term, long-term, user context, and identity memories.
- **Experience & Strategy Learning**: Structured experience persistence, lesson extraction, and strategy ranking.
- **Policy & Authorization**: Deterministic authorization (`authorize_capability`) enforcing read-only constraints, domain boundaries, and write user approvals.
- **Kernel Orchestration**: The bounded orchestration pipeline (`Observe → Retrieve → Reason → Plan → Policy → Capability Dispatch → Execute → Verify → Experience → Lesson → Memory → Resume`).
- **Continuity & Resumption**: Checkpointpersistence and run state resumption (`resume(run_id)`).
- **Capability Abstraction**: Specification contracts (`CapabilitySpec`, `CapabilityConstraint`, `BaseCapabilityAdapter`).

#### iOS Runtime Responsibilities
- **OS & App Lifecycle**: Application lifecycle events, background task scheduling (`BGTaskScheduler`), app suspension, and memory warnings.
- **Native User Interface**: SwiftUI / UIKit rendering, user prompts, and explicit write-approval dialogs.
- **Secure Local Storage**: Keychain and Secure Enclave integration for private keys and credentials.
- **Device-Native Capabilities**: Accessing device hardware and frameworks (Contacts, EventKit, CoreLocation, Photos) via concrete `BaseCapabilityAdapter` implementations.
- **App Permissions**: iOS privacy permission prompts (`NSContactsUsageDescription`, etc.).
- **Local Model Execution**: On-device LLM runtime (e.g. CoreML, llama.cpp, Metal) bound via model adapter contracts.

#### Invariant Boundary Constraint
**Agent-Core Kernel MUST NOT import or depend directly on `UIKit`, `SwiftUI`, `CloudKit`, `CoreData`, or concrete Apple frameworks.**

---

## 2. Local-First Operation & Resilience Requirements

1. **Offline-First Default**: All core operations (reasoning with local provider, vault access, memory retrieval, policy authorization) must function completely without an Internet connection.
2. **Local Personal Data**: User personal data and memory store remain strictly in the local iOS App Sandbox by default.
3. **App Restart Continuity**: Memory items, experiences, and run state checkpoints must survive process termination and app restarts.
4. **Stable Run Identifiers**: Every run ID (e.g. `RUN-12345`) must remain deterministic, durable, and resumable after process restart.
5. **Honest Failure Semantics**: Capability or service failures must return `status="FAILED"`. External failures must NEVER be masqueraded as `SUCCESS`.
6. **Authoritative Policy**: Policy authorization cannot be bypassed. Unapproved write actions return `status="DENIED"`.
7. **Optional External Capabilities**: Network capabilities (e.g. GitHub API) are strictly optional and flag `NOT_EXECUTED` or `FAILED` when network is unavailable.

### Behavior Under Environmental Conditions

| Condition | System Behavior |
|-----------|-----------------|
| **Network Unavailable** | Core operates in offline mode. Local capabilities succeed; external network capabilities return `status="FAILED"` with offline reason. |
| **App Suspended / Terminated** | Current task step completes atomic checkpoint save (`.tmp` -> `fsync` -> `os.replace`). State is reloaded on next app launch via `agent.resume(run_id)`. |
| **Storage Unavailable** | Storage errors are caught safely. `PersonalVaultAdapter` uses in-memory fallback buffer; Core integrity is preserved. |
| **Local Model Runtime Unavailable** | Planner falls back to deterministic mock provider (`AGENTCORE_PLANNER_PROVIDER=mock`). |

---

## 3. Local Native Service API Contract

The native iOS application communicates with Agent-Core via a local service contract API.

### Service Methods

```python
class LocalAgentServiceContract:
    def run(goal: str, project_id: str = "default", user_approved: bool = False) -> AgentRunResult: ...
    def resume(run_id: str) -> AgentRunResult: ...
    def remember(content: str, memory_type: str = "short_term", importance: float = 0.5) -> MemoryItem: ...
    def retrieve(query: str, limit: int = 5) -> list[MemoryItem]: ...
    def update_memory(memory_id: str, new_content: str) -> MemoryItem: ...
    def list_capabilities() -> list[CapabilitySpec]: ...
    def execute_capability(capability_id: str, inputs: dict, user_approved: bool = False) -> CapabilityResult: ...
    def get_run(run_id: str) -> Optional[dict]: ...
    def get_experience(run_id: str) -> Optional[Experience]: ...
    def health() -> dict: ...
```

### Result Status Semantics

- **`SUCCESS`**: The operation completed and passed verification successfully.
- **`FAILED`**: The operation encountered an execution error, network failure, or step verification failure.
- **`DENIED`**: The policy engine rejected the operation due to read-only constraints or missing user approval (`user_approved=False`).
- **`NOT_EXECUTED`**: The capability required live external credentials/network which were absent.

---

## 4. iOS Local Storage Abstraction Mapping

Agent-Core depends exclusively on abstract store interfaces. An iOS runtime maps these contracts to iOS sandbox locations or native SQLite:

| Core Abstraction | Default Python Storage | iOS Sandbox Target Location |
|------------------|------------------------|-----------------------------|
| **`MemoryStore`** | `AGENTCORE_STORAGE_DIR/memories/*.json` | `<App_Sandbox>/Library/Application Support/AgentCore/memories/` |
| **`ExperienceStore`** | `AGENTCORE_STORAGE_DIR/experiences/*.json` | `<App_Sandbox>/Library/Application Support/AgentCore/experiences/` |
| **`CheckpointStore`** | `AGENTCORE_STORAGE_DIR/runs/*.json` | `<App_Sandbox>/Library/Application Support/AgentCore/runs/` |
| **`PersonalVaultAdapter`** | `AGENTCORE_STORAGE_DIR/vault/fallback_vault.json` | iOS Keychain / Secure Enclave (for tokens) + SQLite (for context) |

---

## 5. Consequences

- **Positive**: Clean separation ensures Agent-Core can be compiled and embedded inside an iOS app container without architectural drift or cloud lock-in.
- **Verification**: `tests/test_ios_portability_and_boundaries.py` automates dependency boundary checks and local-first behavior verification.
