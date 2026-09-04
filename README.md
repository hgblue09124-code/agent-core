# Agent Core

Personal Agent development substrate.

## Key Features

- **Centralized Storage & Path Resolution**: Deterministic storage hierarchy (`AGENTCORE_STORAGE_DIR`) and workspace root isolation.
- **Constitutional Execution**: Enforces invariants INV-1 through INV-10 with separation of executor and verifier authority.
- **Agent Philosophy Layer**: Soft behavioral preferences (`CANDIDATE`, `SUPPORTED`, `WEAKENED`, `REJECTED`, `RETIRED`) with strict precedence hierarchy (`Kernel/Security/Contracts > Verification > Task Requirements > Philosophy`).
- **Unified Developer Beta API**: High-level `Agent` orchestration class in `agent_core`.
- **Command-Line Interface**: `agent-core` CLI for running tasks, inspecting history, and running performance benchmarks.

## Principles

- Build from small verified primitives.
- Separate knowledge, memory, skills, tools and execution.
- Every important capability should be testable.
- Successful experience should become reusable knowledge.
- Prefer measurable improvement over complexity.

## Architecture

Runtime → Context → Intelligence → Skills → Tools → Execution → Verification → Experience → Philosophy

The system is designed to grow over time rather than being completed all at once.

## CLI Usage

```bash
# Run a task
agent-core run "Calculate prime factors" --workspace workspace/Cuu-Gioi

# Run benchmarks
agent-core benchmark

# Inspect system status
agent-core inspect
```
