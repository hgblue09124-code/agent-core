# Changelog — Agent-Core

All notable changes to Agent-Core will be documented in this file.

---

## [Unreleased]

### Summary
AgentLoop is the Personal Agent orchestrator. Cheap classification skips the planner. Retrieve is relevance-gated. Swift runtime executes real steps and remember/forget intents. Dual-stack (Python kernel vs Swift local runtime) is unchanged.

### Agent loop
- Cheap path: remember / forget / short status goals skip planner and capability keyword matching.
- Retrieve uses `needed_layers` — identity, vault, and strategies are not fetched for unrelated goals.
- Successful runs no longer dump "Successfully executed goal …" into prompt memory.
- REPLAN produces a different action set (excludes the failed capability) or fails closed.
- Planner is called only when classification is complex **and** `AGENTCORE_PLANNER_PROVIDER` is not `mock`.
- In-process `core.memory` actions for remember/forget; write GitHub still requires approval.
- GitHub keyword plan mocks only when `GITHUB_TOKEN` is absent.

### Token / context
- Preference/UI goals pull persistent + retrieved layers.
- Observation evidence compacted after verification.
- `AgentRunResult.observations` no longer prepends retrieved pack text.

### Swift runtime
- Remember/forget goals write the real memory store (no five fake PASS steps).
- Other goals execute `mock.echo` per plan step; verify FAIL if a step fails.
- `LanguageModelProvider` is used for planning when injected; otherwise `LocalDeterministicPlanner`.
- Store adopts the runtime `runId` (no dual IDs). Idle cancel is a no-op.

### CLI
- Inspect prints loop `status`/`phase`. Run no longer claims TaskRunner.

### Previously in this cycle
- Empty placeholder packages and duplicate iOS zips / pbxproj blobs removed.
- ContextPack layered budgets + hash dedup.
- Tag-driven unsigned IPA pipeline.

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
