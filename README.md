# Agent Core

Personal Agent development substrate.

## Key Features

- **True Personal Agent Foundation (100% Core Architecture)**: Complete learning-and-continuity loop (`Observe -> Understand -> Retrieve Memory -> Retrieve Strategies -> Reason -> Plan -> Policy -> Capability Execution -> Verify -> Record Experience -> Extract Lesson -> Form Candidate Strategy -> Evaluate Outcome -> Consolidate Memory -> Continue`).
- **First-Class Strategy Memory & Evaluator**: Persistent Strategy model (`core/learning/strategy.py`) with explicit lifecycle states (`CANDIDATE`, `VALIDATED`, `SUPPORTED`, `WEAKENED`, `RETIRED`, `SUPERSEDED`), versioning, supersession, and deterministic confidence updates.
- **Persistent Memory & Cross-Session Continuity**: Short-term, long-term, user context, and identity memory (`core/memory/`) preserving learned state across process restarts.
- **Autonomous Task Queue & Scheduler**: Priority-based task queue and deterministic bounded scheduler supporting dependencies, state machine transitions, bounded retries, pause/resume, and cancellation (`core/tasks/queue.py`, `core/tasks/scheduler.py`).
- **Pluggable Capability Adapters**: Abstract capability contract (`core/capabilities/`) insulating Core from external capability implementations.
- **Constitutional Precedence & Safety**: Strict hierarchy (`Kernel/Security/Contracts > Verification > Task Requirements > Learned Strategies > Philosophy`).
- **Command-Line Subsystems**: `agent-core` CLI supporting `run`, `queue`, `schedule`, `inspect`, `history`, and `benchmark`.

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
