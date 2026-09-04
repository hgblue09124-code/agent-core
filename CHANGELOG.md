# Changelog — Agent-Core

All notable changes to Agent-Core will be documented in this file.

---

## [0.1.0-beta] - 2026-09-03

### Summary
Initial Developer Preview Release of **Agent-Core** (`v0.1.0-beta`), establishing a project-aware reference Agent runtime, CLI inspection tools, deterministic benchmarking, and Agent Philosophy foundation.

### Added
- **Reference Agent (`Agent`)**: Developer-facing preview runtime (`core/agent.py`) orchestrating Task $\rightarrow$ Plan $\rightarrow$ Authority $\rightarrow$ Execution $\rightarrow$ Observation $\rightarrow$ Verification $\rightarrow$ Result $\rightarrow$ Experience.
- **CLI Beta Entrypoint (`agent-core`)**: CLI tool with commands:
  - `agent-core run "<goal>"`
  - `agent-core inspect <run_id>`
  - `agent-core history`
  - `agent-core benchmark`
  - `agent-core version`
- **Agent Philosophy Foundation (`core/philosophy`)**: Soft behavioral tendencies derived from experience and human teaching, obeying strict precedence (`Kernel/Security/Contracts > Verification > Task > Philosophy`).
- **Cửu Giới Benchmark Suite (`verification/benchmarks/benchmark_cuu_gioi.py`)**: Real-time performance measurements for context loading, task engine execution, knowledge retrieval, and kernel loop.
- **Public API Exports (`agent_core`)**: Developer package exports for embedding Agent-Core in Python applications.

### Fixed
- Fixed default storage directory resolution with `AGENTCORE_STORAGE_DIR` fallback and relative path safety boundaries (`core/config/storage.py`).
- Fixed workspace path resolution and working-directory independence (`core/projects/manager.py`).
- Fixed task loop progression index bug in execution engine (`core/runtime/engine.py`).

### Verification & Test Suite
- 100% test pass rate across 661+ unit, constitutional, adversarial, and integration tests.
