# Changelog — Agent-Core

All notable changes to Agent-Core will be documented in this file.

---

## [Unreleased]

### Summary
Source simplification, token/context packing, and a tag-driven unsigned IPA release pipeline. Behavior of the Personal Agent loop is unchanged (keyword plan + capability dispatch).

### Removed
- Empty placeholder packages: `intelligence/`, `library/`, `core/skills`, `core/execution`, `core/tools`.
- Duplicate / generated artifacts: root and verification iOS zips, `project.pbxproj.ready`, `scripts/pbxproj.b64.*`, deprecated pbxproj repair scripts.
- Historical build reports: `PLANNER_REPORT.md`, `TASK_ENGINE_REPORT.md`, `PROJECT_INTEGRATION_REPORT.md`.
- Unused `TaskManager` import on `Agent`; unused `KernelContextBuilder` attribute on `Kernel`.

### Simplified
- Planner prompt: compact output schema; constraints live in the static system prefix.
- `ContextBuilder` truncates oversized docs (relevance-sliced when a query is present) instead of dropping them, and records `documents_excluded`.
- Agent run results no longer re-fetch identity/vault to decorate every observation list.

### Token / context
- New `core/context/pack.py`: layered `ContextPack` (current_task / persistent / session / retrieved / tool_output) with per-layer budgets, relevance gating, and hash-based prompt dedup.
- Agent loop persists the pack on `AgentLoopState` after RETRIEVE and truncates tool output **after** verification.
- Planner accepts `extra_context`; Kernel retrieve → pack → `RuntimeEngine.run(..., extra_context=)`.
- Kernel no longer fake-increments `llm_calls` in `reason()`.

### Release
- CI generates the iOS source zip from live `ios/` (no zip-in-git).
- IPA job runs on `master`/`main`/tags/`workflow_dispatch`; GitHub Release attach is **tags only**.
- Version/build from git tag + `GITHUB_RUN_NUMBER`; IPA named `AgentCore-iOS-vVERSION-bBUILD-unsigned.ipa`.
- Info.plist reads `$(MARKETING_VERSION)` / `$(CURRENT_PROJECT_VERSION)`.
- Shared Xcode scheme committed. Archive-first unsigned packaging with build fallback. IPA job uploads logs on failure.
- Default `contents: read`; write permission only on the IPA job.

---

## [0.1.0-beta] - 2026-09-03

### Summary
Initial Developer Preview Release of **Agent-Core** (`v0.1.0-beta`), establishing a project-aware reference Agent runtime, CLI inspection tools, deterministic benchmarking, and Agent Philosophy foundation.

### Added
- **First-Class Strategy Subsystem (`core/learning/`)**: Persistent Strategy schema (`Strategy`), atomic store (`StrategyStore`), Experience -> Lesson -> Candidate Strategy pipeline (`LearningPipeline`), multi-factor strategy ranking (`StrategyRanker`), and deterministic evaluator (`StrategyEvaluator`).
- **Memory Consolidation & Conflict Resolution (`core/memory/consolidation.py`)**: Promotes short-term experience observations to long-term memory and resolves knowledge/strategy conflicts via versioning and supersession without deleting evidence history.
- **Cross-Session Process Restart Continuity**: Learned strategies, memory items, agent identity, and strategy confidence survive process restarts and continuously influence future reasoning.
- **Personal Agent Runtime Loop**: Integrated orchestration loop (`Observe -> Retrieve -> Reason -> Plan -> Policy Check -> Execute -> Verify -> Record Experience -> Extract Lesson -> Form Strategy -> Evaluate Outcome -> Consolidate Memory -> Continue`).
- **Agent Philosophy Foundation (`core/philosophy`)**: Soft behavioral tendencies derived from experience and human teaching, obeying strict precedence (`Kernel/Security/Contracts > Verification > Task > Philosophy`).
- **Cửu Giới Benchmark Suite (`verification/benchmarks/benchmark_cuu_gioi.py`)**: Real-time performance measurements for context loading, task engine execution, knowledge retrieval, and kernel loop.
- **Public API Exports (`agent_core`)**: Developer package exports for embedding Agent-Core in Python applications.

### Fixed
- Fixed default storage directory resolution with `AGENTCORE_STORAGE_DIR` fallback and relative path safety boundaries (`core/config/storage.py`).
- Fixed workspace path resolution and working-directory independence (`core/projects/manager.py`).
- Fixed task loop progression index bug in execution engine (`core/runtime/engine.py`).

### Verification & Test Suite
- 100% test pass rate across 661+ unit, constitutional, adversarial, and integration tests.
