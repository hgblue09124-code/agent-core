# Agent Core

Personal Agent development substrate.

## Key Features

- **Personal Agent Runtime Foundation**: Coherent runtime loop (`Observe -> Understand -> Retrieve Memory -> Reason -> Plan -> Policy Check -> Capability Execution -> Verify -> Record Experience -> Update Memory -> Continue`).
- **Persistent Memory & Identity Subsystem**: Short-term, long-term, user context, and cross-session identity memory model (`core/memory/`).
- **Autonomous Task Queue & Scheduler**: Priority-based task queue and deterministic bounded scheduler supporting dependencies, state machine transitions, bounded retries, pause/resume, and cancellation (`core/tasks/queue.py`, `core/tasks/scheduler.py`).
- **Pluggable Capability Adapters**: Strict capability specification contract (`core/capabilities/`) insulating Core from external implementations.
- **Constitutional Execution & Independent Verifier**: Enforces invariants INV-1 through INV-10 with strict separation of executor and verifier authority.
- **Agent Philosophy Layer**: Soft behavioral preferences obeying strict precedence (`Kernel/Security/Contracts > Verification > Task Requirements > Philosophy`).
- **Command-Line Interface & Subsystems**: `agent-core` CLI supporting `run`, `queue`, `schedule`, `inspect`, `history`, and `benchmark`.

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
