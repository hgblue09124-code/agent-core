# Agent Core

Personal Agent development substrate.

## Architecture Status

Agent-Core provides a **hardened foundational substrate** for Personal Agent development.

It implements clean core boundaries, deterministic persistence, experience-based strategy learning, and pluggable capability adapters while strictly keeping external domain logic outside the kernel.

### Implemented Core Subsystems
- **Core Architecture & Kernel Loop**: Bounded orchestration pipeline (`Observe -> Retrieve -> Reason -> Plan -> Policy -> Execute -> Verify -> Record Experience -> Extract Lesson -> Strategy -> Consolidate Memory -> Continue`).
- **Persistent Memory Subsystem**: Atomic filesystem storage for `SHORT_TERM`, `LONG_TERM`, `USER_CONTEXT`, and `IDENTITY` memory (`core/memory/`) preserving learned state across process restarts.
- **First-Class Strategy Subsystem**: Persistent Strategy schema (`core/learning/strategy.py`) with explicit lifecycle states (`CANDIDATE`, `VALIDATED`, `SUPPORTED`, `WEAKENED`, `RETIRED`, `SUPERSEDED`), versioning, supersession, and deterministic confidence updates (+0.15 on PASS, -0.25 on FAIL).
- **Capability Adapter Contracts**: Abstract capability specification contract (`core/capabilities/`) insulating Core from concrete external capability implementations.
- **Autonomous Task Queue & Scheduler**: Priority queue and deterministic bounded scheduler (`core/tasks/queue.py`, `core/tasks/scheduler.py`) with state machine transitions, dependency checks, and bounded retries.
- **Constitutional Precedence**: Strict hierarchy (`Kernel/Security/Contracts > Verification > Task Requirements > Learned Strategies > Philosophy`).

### Intentionally Deferred Capabilities (Future Milestones)
- Vector database / embedding-based semantic retrieval.
- Autonomous web browser agents or unrestricted internet execution.
- Autonomous self-modifying code generation.
- Production external API integrations.

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
