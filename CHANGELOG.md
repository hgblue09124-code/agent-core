# Changelog — Agent-Core

All notable changes to Agent-Core will be documented in this file.

---

## [0.1.0-beta] - 2026-09-03

### Summary
Initial Developer Preview Release of **Agent-Core** (`v0.1.0-beta`), establishing a project-aware reference Agent runtime, CLI inspection tools, deterministic benchmarking, and Agent Philosophy foundation.

### Added
- **Personal Agent Runtime Foundation**: Coherent runtime loop (`Observe -> Understand -> Retrieve Memory -> Reason -> Plan -> Policy Check -> Capability Execution -> Verify -> Record Experience -> Update Memory -> Continue`).
- **Persistent Memory & Identity Subsystem (`core/memory/`)**: Persistent short-term, long-term, user context, and identity memory with atomic filesystem storage.
- **Autonomous Task Queue & Scheduler (`core/tasks/queue.py`, `core/tasks/scheduler.py`)**: Priority-based task queue, explicit state machine (`PENDING`, `PLANNING`, `RUNNING`, `VERIFYING`, `COMPLETED`, `FAILED`, `RETRY`, `PAUSED`, `CANCELLED`), task dependencies, bounded autonomous scheduler, and retry limit handling.
- **Capability Adapter Interface (`core/capabilities/`)**: Formal capability contract specification, registry, and mock adapter insulating Core from external capability implementations.
- **CLI Subcommands (`agent-core queue`, `agent-core schedule`)**: Command-line support for autonomous task enqueueing and bounded scheduling.
- **Agent Philosophy Foundation (`core/philosophy`)**: Soft behavioral tendencies derived from experience and human teaching, obeying strict precedence (`Kernel/Security/Contracts > Verification > Task > Philosophy`).
- **Cửu Giới Benchmark Suite (`verification/benchmarks/benchmark_cuu_gioi.py`)**: Real-time performance measurements for context loading, task engine execution, knowledge retrieval, and kernel loop.
- **Public API Exports (`agent_core`)**: Developer package exports for embedding Agent-Core in Python applications.

### Fixed
- Fixed default storage directory resolution with `AGENTCORE_STORAGE_DIR` fallback and relative path safety boundaries (`core/config/storage.py`).
- Fixed workspace path resolution and working-directory independence (`core/projects/manager.py`).
- Fixed task loop progression index bug in execution engine (`core/runtime/engine.py`).

### Verification & Test Suite
- 100% test pass rate across 661+ unit, constitutional, adversarial, and integration tests.
