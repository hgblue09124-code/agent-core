# Agent Core

Personal Agent development substrate.

## Key Features

- **Core/Kernel Foundation**: Strong foundational substrate managing identity, memory, experience, philosophy, continuity, and constitutional execution. External capabilities (e.g., Cửu Giới domain) remain pluggable, replaceable target consumers interacting via contracts/adapters.
- **Centralized Storage & Path Resolution**: Deterministic storage hierarchy (`AGENTCORE_STORAGE_DIR`) and workspace root isolation.
- **Constitutional Execution & Independent Verifier**: Enforces invariants INV-1 through INV-10 with strict separation of executor and verifier authority.
- **Agent Philosophy Layer**: Soft behavioral preferences (`CANDIDATE`, `SUPPORTED`, `WEAKENED`, `REJECTED`, `RETIRED`) obeying strict precedence (`Kernel/Security/Contracts > Verification > Task Requirements > Philosophy`).
- **Unified Developer Beta API**: High-level `Agent` orchestration class in `agent_core`.
- **Command-Line Interface**: `agent-core` CLI for running tasks, inspecting history, and running performance benchmarks.

## Principles

- Build from small verified primitives.
- Separate knowledge, memory, skills, tools, and execution.
- Every important capability should be testable.
- Successful experience should become reusable knowledge.
- Prefer measurable improvement over complexity.

## Architecture

Runtime → Context → Intelligence → Skills → Tools → Execution → Verification → Experience → Philosophy

The system is designed as a foundational Core. External applications and domain capabilities integrate as replaceable consumers via stable contracts.

## CLI Usage

```bash
# Run a task
agent-core run "Inspect system architecture"

# Run Cửu Giới benchmark suite (external target)
agent-core benchmark

# Inspect run lifecycle
agent-core inspect KRUN-12345
```
