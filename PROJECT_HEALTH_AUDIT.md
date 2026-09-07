# PROJECT HEALTH AUDIT — REPORT ONLY

**Audit Date:** September 7, 2026
**Audited Commit SHA:** `fcdd9e564b94ba1a6c8eeec806550ac2147734cb`
**Repository Baseline:** `master`

---

## Executive Summary

This Project Health Audit presents a factual baseline evaluation of the Agent-Core repository as it exists on `master`.

Agent-Core contains a rich and highly structured set of architectural components in both Python (`core/`) and Swift (`ios/`). However, there is a distinct gap between the **structural/contract layer** and the **default real-world execution path**.

While the repository features extensive FSM closed-loop controllers (`AgentLoopController`), policy engines, learning pipelines, memory consolidation modules, and native SwiftUI frontends, **the default runtime mode across both Python and iOS defaults to deterministic keyword classification and mock tool echo execution**. Real LLM providers (`OpenAIChatProvider`, `OpenAIPlannerProvider`, `LocalPlannerProvider`, `GGUFChatProvider`) are fully implemented and test-verified, but are not wired as the default active inference engine in the standard agent loop unless specific environment variables or custom providers are injected.

Overall, the repository represents a **Functional Prototype / Early Alpha** system with high code quality, robust unit/contract test coverage (892 passing tests), and clear architectural boundaries, but requires consolidation of dual runtimes and default wiring of real LLM inference before reaching production readiness.

---

## 1. Current Architecture

### Top-Level Modules & Responsibilities

| Module | Location | Primary Responsibility |
| :--- | :--- | :--- |
| **`core/`** | `core/` | **Python Core Kernel & Subsystems**. Contains agent runtime loop, planner, memory, vault adapter, policy, learning, experience, capabilities, kernel, philosophy, and knowledge graph. |
| **`ios/`** | `ios/AgentCoreIOS/` | **Native iOS Local Agent Application & Runtime**. Implements SwiftUI app, native `AgentRuntime`, local storage adapters (`LocalMemoryStore`, `LocalVaultStore`, `LocalExperienceStore`, `LocalCheckpointStore`), and data update manager. |
| **`console/`** | `console/`, `core/console/` | **Web UI & REST API Gateway**. Python HTTP server (`core/console/api.py`) exposing `/api/agent/submit` and `/api/agent/objectives`, backed by static HTML/JS frontend in `console/`. |
| **`agent_core/`** | `agent_core/` | **Top-Level Python Package Initializer**. Package metadata and exports. |
| **`config/`** | `config/` | Root-level configuration directory. |
| **`projects/`** | `projects/` | Local workspace directory for registered project context definitions. |
| **`workspace/`** | `workspace/` | Local working files directory for agent execution. |
| **`scripts/`** | `scripts/` | Packaging and validation utilities (`validate_ipa.py`, `validate_ios_release_zip.py`, `package_ios_source_zip.py`, `run_real_task.py`). |
| **`tests/`** | `tests/` | Comprehensive test suite (892 test cases covering core, iOS contracts, API endpoints, and capability bugs). |
| **`verification/`** | `verification/` | Benchmark specs, E2E benchmarks, and release validation checklists. |
| **`constitution/`** | `constitution/` | Architectural Decision Records (ADRs) defining core boundaries and composition contracts. |

### Module Dependency Graph

```
[ iOS App / UI (SwiftUI) ] ──> [ LocalAgentService ] ──> [ iOS AgentRuntime (Swift) ]
                                                              │
                                            ┌─────────────────┴─────────────────┐
                                            ▼                                   ▼
                                [ Local Storage Adapters ]            [ LanguageModelProvider ]
                                (Vault/Memory/Checkpoint)            (Mock / Local / OpenAI)

[ Web / Console (JS) ] ─────> [ Console API (Python) ] ──> [ Agent (core/agent.py) ]
                                                              │
                                                              ▼
                                                   [ AgentLoopController ]
                                                              │
           ┌────────────────┬────────────────┬────────────────┼────────────────┬────────────────┐
           ▼                ▼                ▼                ▼                ▼                ▼
     [ PolicyEngine ] [ CapabilityReg ] [ MemoryMgr ]  [ VaultAdapter ] [ ExpEngine ]    [ LearningPipe ]
           │                │
           ▼                ▼
       [ Kernel ]     [ GitHub / Mock ]
```

### Duplicate & Overlapping Layers

1. **Dual Parallel Runtimes (Python vs. Swift):**
   - **Python Runtime:** `Agent` (`core/agent.py`) + `AgentLoopController` (`core/runtime/loop.py`) + `RuntimeEngine` (`core/runtime/engine.py`) + `AgentRuntime` (`core/runtime/agent_runtime.py`).
   - **Swift Runtime:** `AgentRuntime` (`ios/AgentCoreIOS/Runtime/AgentRuntime.swift`).
   - *Impact:* The iOS application executes tasks entirely within its own Swift `AgentRuntime` reimplementation without calling into Python `core/`. Business logic (goal classification, memory routing, policy rules) is duplicated across both stacks.

2. **Multiple Orchestrators in Python Core:**
   - `AgentLoopController` (`core/runtime/loop.py`): FSM-based runtime controller (Primary active loop in `Agent.run()`).
   - `AgentRuntime` (`core/runtime/agent_runtime.py`): Alternate multi-phase cycle runtime engine.
   - `RuntimeEngine` (`core/runtime/engine.py`): Higher-level task loop engine wrapper.
   - `KernelOrchestrator` (`core/kernel/orchestrator.py`): Lower-level task execution loop.
   - *Impact:* Multiple orchestration layers exist simultaneously, creating potential confusion over which engine governs task execution.

3. **Multiple LLM / Provider Wrappers:**
   - `core/llm/provider.py`: `OpenAIChatProvider`, `GGUFChatProvider`, `create_chat_provider`.
   - `core/planner/planner.py`: `OpenAIPlannerProvider`, `OpenRouterPlannerProvider`, `LocalPlannerProvider`, `MockPlannerProvider`, `create_provider`.
   - `ios/.../Providers/`: `LanguageModelProvider`, `RoutingLanguageModelProvider`, `MockLanguageModelProvider`, `OpenAICompatibleProvider`, `LocalDeterministicPlanner`.

---

## 2. Actual Agent Execution Path

### Stage-by-Stage Trace & Classification

| Stage | Path Component | Classification | Justification / Detail |
| :--- | :--- | :--- | :--- |
| **1. User Input** | iOS UI / Web Console | **REAL** | Text input received via `ExecuteView` / `HomeView` in SwiftUI or `#task-input` in Web Console. |
| **2. Entry Point** | `LocalAgentService` (iOS) / `POST /api/agent/submit` (Web) | **REAL** | Cleanly forwards user goal and parameters to the runtime layer. |
| **3. Runtime** | `AgentRuntime.swift` (iOS) / `Agent.run()` (Python) | **REAL** | Executes goal lifecycle, creates run IDs, logs events, enforces policies, and manages checkpoints. |
| **4. LLM** | `LanguageModelProvider` / `create_chat_provider` | **PARTIAL / MOCK** | **Default is Mock/Deterministic.** Real OpenAI/Ollama/OpenRouter providers are implemented and test-verified, but by default `AGENTCORE_PLANNER_PROVIDER` defaults to `"mock"` in Python, and iOS defaults to `LocalDeterministicPlanner`. |
| **5. Planning/Reasoning** | `classifyGoal` / `AgentLoopController._plan_actions_for_intent` | **PARTIAL** | Fast-path intent classifier checks for `"remember"`, `"forget"`, or `"status"`. Generic goals generate fallback step lists (`mock.echo.echo` or deterministic step strings). |
| **6. Actions/Tools** | `CapabilityRegistry` / `executeCapability` | **PARTIAL** | `mock.echo` works locally. `GitHubCapabilityAdapter` works when `GITHUB_TOKEN` is present, but defaults to mock offline mode when unconfigured. |
| **7. Memory** | `LocalMemoryStore` / `MemoryManager` + `PersonalVaultAdapter` | **REAL** | Context and preferences are read/written to file-backed JSON stores during execution. |
| **8. Result** | `AgentRunResult` / Checkpoint Store | **REAL** | Execution outputs, duration, and verification verdicts (`PASS`/`FAIL`/`DENIED`) are constructed and saved. |
| **9. UI Output** | SwiftUI `AgentRuntimeStore` / Web Console Logs | **REAL** | UI subscribes to streaming events and updates status pills, progress bars, and activity logs. |

---

## 3. LLM Status

* **Is an LLM actually loaded by default?**
  **NO.** Neither Python `Agent` nor iOS `AgentRuntime` loads or initializes a remote/local LLM binary by default.
* **Which provider/model paths exist?**
  - **Python (`core/llm/provider.py` & `core/planner/planner.py`):** `OpenAIChatProvider`, `GGUFChatProvider` (via `llama-cpp-python`), `OpenAIPlannerProvider`, `OpenRouterPlannerProvider`, `LocalPlannerProvider` (Ollama/LM Studio).
  - **Swift (`ios/.../Providers/`):** `OpenAICompatibleProvider`, `RoutingLanguageModelProvider`, `MockLanguageModelProvider`, `LocalDeterministicPlanner`.
* **Is inference actually invoked by chat/run?**
  **ONLY IF CONFIGURED.** In standard default execution, goals bypass LLM generation because `AGENTCORE_PLANNER_PROVIDER` defaults to `"mock"`. In iOS, `generatePlanSteps` calls `languageModelProvider` if injected, but falls back to `LocalDeterministicPlanner` when omitted.
* **Where does the response currently come from?**
  Responses come from template strings formatted by `MockPlannerProvider` or deterministic string generators in `LocalDeterministicPlanner`.
* **Fallback / Demo response identification:**
  - Python: `"Auto-generated mock plan for: <objective>"` or `"ECHO: <goal>"`.
  - Swift: `"Successfully executed goal '<goal>' through local agent runtime pipeline."` via `mock.echo`.

---

## 4. Runtime Status

* **Status:** **REAL (EXECUTING & PERSISTING)**.
* **Details:** `AgentLoopController` (Python) and `AgentRuntime` (Swift) do not merely expose structural state. They actively maintain Finite State Machine transitions (`BOOTSTRAP` → `OBSERVE` → `RETRIEVE` → `REASON` → `PLAN` → `DECIDE` → `AUTHORIZE` → `EXECUTE` → `OBSERVE_RESULT` → `VERIFY` → `LEARN` → `COMPLETE`), record telemetry, enforce time budgets, handle step cancellation, save atomic state checkpoints to disk (`runs/<run_id>_loop.json`), and publish events to `EventBus`.

---

## 5. Memory Status

* **Status:** **REAL (READ & WRITTEN)**.
* **Details:** Memory operations are actively executed during agent runs.
  - Commands starting with `"remember"` invoke `MemoryManager.remember()` / `LocalMemoryStore.remember()`, persisting facts to file storage (`user_preference` in Vault).
  - Commands starting with `"forget"` invoke `MemoryManager.forget()`, deleting context from Vault.
  - Goal execution retrieves identity and relevant memories (`retrieve(MemoryQuery)`) to construct context packs before plan generation.

---

## 6. Action / Tool Status

* **Status:** **PARTIAL (EXECUTABLE WITH MOCK / LIMITED EXTERNAL TOOLING)**.
* **Details:**
  - `mock.echo`: Fully executable in both Python and Swift, returning local echo output.
  - `github_integration` / `GitHubCapabilityAdapter`: Fully implemented with status code validation and error handling. When `GITHUB_TOKEN` is present, real HTTP requests are issued to GitHub API. When unconfigured, it runs in `mock_offline=True` mode.
  - Policy enforcement correctly intercepts mutating actions (`create_issue`, `update_issue`, `delete`) and returns `DENIED` / `WAITING_FOR_USER` unless `user_approved=True`.

---

## 7. iOS Status

### Implementation vs. Scaffolding

* **Genuinely Implemented:**
  - Full SwiftUI navigation across 7 tabs: `Home`, `Execute`, `Activity`, `Vault`, `Connections`, `Settings`, `Review`.
  - Reactive state management using `@MainActor AgentRuntimeStore` and `AgentRuntimeReducer`.
  - Full local storage stack (`LocalMemoryStore`, `LocalVaultStore`, `LocalExperienceStore`, `LocalCheckpointStore`) saved in `Application Support/AgentCore/`.
  - `GitHubDataUpdateManager` with SHA-256 integrity checks, relative path safety validation, and rollback capability.
  - Complete XCTest suite in `ios/Tests/`.
* **Presentation / Scaffolding:**
  - Local LLM model downloading (`ModelDownloadManager` / `ModelCatalog`) is UI scaffolding and does not load GGUF models directly into iOS memory (uses `OpenAICompatibleProvider` or mock).
  - `ConnectionsView` displays capability connection status, but configuration edits are in-memory.
* **Working User Flows:**
  - Memory facts input (`"remember that my preferred language is Swift"`).
  - Goal submission with streaming event steps (`TaskStarted` → `PlanCreated` → `Execute` → `ObserveResult` → `Verify` → `TaskCompleted`).
  - Mutating action policy denial and approval request prompting.
  - Activity history filtering (`All`, `Success`, `Failed`).
* **Missing Items for Real Personal Agent UX:**
  - Direct integration with background iOS system tasks / notifications.
  - On-device local GGUF LLM inference engine (e.g. via `llama.cpp` Swift bindings).
  - Native cross-process communication bridging Swift runtime to Python Core.

---

## 8. Test Status

* **Total Test Count:** 892 unit and integration tests.
* **Execution Result:** All 892 tests **PASSING** cleanly in 13.3 seconds (`python3 -m unittest discover -s tests`).
* **Test Classification:**
  - **Structural / Contract Tests:** Verifying FSM phase transitions (`test_agent_loop.py`), API JSON model contracts (`test_ios_native_api_contract.py`), project registry schemas, and IPA package structure (`test_ipa_validation.py`).
  - **Real Behavior Tests:** Testing end-to-end memory operations, policy authorization enforcement (`test_personal_agent_beta_real_use.py`), HTTP error handling for GitHub capabilities (`test_github_capability_bugs.py`), state resumption across restarts, and atomic file saving.

---

## 9. Architecture Risks

1. **Competing Sources of Truth (Dual Python / Swift Runtimes):**
   Business logic, policy enforcement, memory classification, and experience recording are implemented independently in both Python (`core/`) and Swift (`ios/`). Features added to Python core do not automatically propagate to iOS.
2. **Multiple Parallel Python Orchestrators:**
   `AgentLoopController`, `AgentRuntime`, `RuntimeEngine`, and `KernelOrchestrator` overlap in responsibility. This abstraction overhead complicates maintenance and debugging.
3. **Mock Default Trap:**
   Because both runtimes quietly fall back to mock step execution when LLM credentials or local servers are missing, a user or developer might believe a task was executed by an intelligent agent when it was handled by deterministic keyword branching.
4. **Unclosed Socket Warnings in API Tests:**
   Console API tests generate `ResourceWarning: unclosed socket` during teardown in `core/console/api.py`, indicating thread/socket cleanup debt.
5. **Memory Consolidation vs. Prompt Budgeting:**
   As activity history and experience store grow, unstructured context retrieval could overflow context windows if uncompacted.

---

## 10. Project Maturity Rating

**Rating:** **FUNCTIONAL PROTOTYPE / EARLY ALPHA**

* **Justification:**
  The project is significantly more advanced than a basic scaffold—it possesses robust state machines, atomic persistence, high test coverage, clean UI components, and complete policy enforcement. However, because real LLM inference is not enabled by default, tools are primarily mock/stub implementations, and dual parallel runtimes exist, it cannot be classified as Beta or Production Candidate.

---

## 11. Next Milestone: Top 3 Highest-Value Actions

To establish a single, real, end-to-end agent execution flow without adding further architectural abstractions:

1. **Wire Real LLM Inference by Default in Python Core:**
   - Connect `OpenAIChatProvider` / `LocalPlannerProvider` directly into `AgentLoopController` so that user goals generate dynamic LLM plans by default when an API key or local Ollama endpoint is present, explicitly surfacing an error when unconfigured rather than falling back to `mock.echo`.
2. **Consolidate Python Orchestration Layers:**
   - Standardize on `AgentLoopController` as the sole canonical execution engine in `core/` and deprecate redundant orchestrator classes (`RuntimeEngine`, `KernelOrchestrator`).
3. **Bridge iOS Application to Canonical Backend Execution:**
   - Establish a single communication mechanism (e.g., embedding the Python runtime or using the REST Console API) so the iOS UI executes tasks through Python `core/` rather than a duplicate Swift runtime.

---

## Explicit List of What MUST NOT Be Changed Yet

To maintain baseline stability, the following components must remain untouched until the next implementation cycle:

1. **Core Runtime & FSM State Machine Contracts:**
   - `core/runtime/state.py` (`AgentLoopState`, `VALID_PHASE_TRANSITIONS`).
   - `core/runtime/loop.py` (`AgentLoopController`).
2. **Kernel Policy & Authority Rules:**
   - `core/kernel/policy.py` (`PolicyEngine`, mutating action authorization requirements).
3. **Native iOS Storage & API Contracts:**
   - `ios/AgentCoreIOS/API/` (`LocalAgentServiceProtocol`, `AgentAPIModels.swift`).
   - `ios/AgentCoreIOS/Storage/` (`LocalMemoryStore`, `LocalVaultStore`, `LocalCheckpointStore`).
4. **Database & Memory Serialization Schemas:**
   - Vault JSON format (`fallback_vault.json`).
   - Run state checkpoint JSON format (`<run_id>_loop.json`).
5. **CI / Release Workflows:**
   - `.github/workflows/ci.yml` (iOS test & IPA build pipelines).
