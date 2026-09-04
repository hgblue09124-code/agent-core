# Kernel Foundation Specification — agent-core v1.0

> **Machine-checkable architectural specification.**
> This document is authoritative. Implementation MUST conform.
> Ambiguity is a FAIL condition — see HARD STOP criteria.

---

## Table of Contents

1. [Kernel Identity](#1-kernel-identity)
2. [Task Construction](#2-task-construction)
3. [Execution](#3-execution)
4. [Verification](#4-verification)
5. [Evidence](#5-evidence)
6. [Evaluation](#6-evaluation)
7. [Experience](#7-experience)
8. [Knowledge](#8-knowledge)
9. [Learning](#9-learning)
10. [Capability](#10-capability)
11. [Authority](#11-authority)
12. [Promotion Gate](#12-promotion-gate)
13. [Adversarial Verification](#13-adversarial-verification)
14. [Reproducibility](#14-reproducibility)
15. [Improvement](#15-improvement)

---

## 1. Kernel Identity

### 1.1 Designation

- **Name**: agent-core Kernel
- **Version**: v1.0
- **Knowledge Version**: v0.7
- **Experience Version**: v0.8
- **Evaluation Version**: v0.9
- **Runtime Version**: v0.6

### 1.2 Purpose

The Kernel is the **stateless orchestrator** that coordinates all subsystems to execute a goal from construction through verification, learning, and improvement. It is NOT the executor (TaskRunner), NOT the planner (LLM), NOT the knowledge store (PrimitiveStore).

### 1.3 Kernel Loop

```
BOOTSTRAP → KNOWLEDGE_RETRIEVAL → REASONING → PLAN_VALIDATION
→ EXECUTION → OBSERVATION → VERIFICATION → EXPERIENCE
→ EVALUATION → LESSON → KNOWLEDGE_PROMOTION → IMPROVEMENT
→ COMPLETE | FAILED
```

Each phase transitions atomically. A phase never skips another phase. The only allowed shortcut is transitioning directly to `FAILED` from any phase when budget is exhausted or an unrecoverable error occurs.

### 1.4 Non-Functional Properties

| Property | Value |
|---|---|
| Stdlib only | Yes — no external dependencies |
| LLM dependency | No — LLM is an optional planner component |
| Checkpoint durability | All phase transitions persist to disk |
| Secret handling | Never logged, never persisted, never printed |
| Reproducibility | Every run has a `run_id`, checkpoint, and evidence ledger |

### 1.5 Version Compatibility

```
kernel     knowledge   experience  evaluation
v1.0   ←    v0.7    ←    v0.8     ←  v0.9
```

The Kernel loop uses the latest version of each subsystem. Downgrade of any subsystem is an architectural change requiring evidence and Administrator approval.

---

## 2. Task Construction

### 2.1 TaskConstructionContract Schema

A Task is constructed via a `TaskConstructionContract` — the authoritative specification of WHAT must be built.

**Required semantic fields** (enforced by `validate()`):

| Field | Type | Required | Description |
|---|---|---|---|
| `contract_id` | string | YES | Unique stable ID matching `^[A-Za-z0-9_\-]{3,64}$` |
| `objective` | string | YES | Fundamental goal of this task |
| `acceptance_criteria` | list[string] | YES* | OR `done_when` |
| `expected_evidence_types` | list[string] | YES | Values from DTP_EVIDENCE_TYPES |
| `done_when` | string | YES* | OR `acceptance_criteria` |
| `scope` | list[string] | YES | Explicit boundary definitions |
| `max_retries` | int | YES | 0 ≤ value ≤ 10 |
| `failure_actions` | list[string] | NO | Must be subset of valid actions |
| `expected_outcome` | string | NO | Explicit outcome description |

**Evidence types** (`DTP_EVIDENCE_TYPES`):
```
TEST | COMMAND_RESULT | FILE_STATE | RUNTIME_RESULT
| REGRESSION_RESULT | COMMIT_STATE | ASSERTION
```

### 2.2 Prompt ≠ Contract

The Prompt is the communication surface (natural language, CLI, API).
The Contract is the authoritative machine-checkable specification.

The kernel MUST validate the contract before execution. A contract that fails validation MUST NOT be executed.

### 2.3 Contract Lifecycle

```
authored → validated → attached to Task → executed
→ verified → evidence captured → experience/knowledge
```

### 2.4 DeepTaskPrompt Primitive

`DeepTaskPrompt` is the structured representation of a GPT-directed task. It models:
- Intent + Acceptance Criteria
- Scope + Files
- Execution Strategy + Constraints
- Verification Requirements
- Failure Protocol
- Learning Capture
- Expected Outcome

A `DeepTaskPrompt` is NOT automatically knowledge. It becomes a candidate for learning only after evaluation produces evidence of success.

---

## 3. Execution

### 3.1 Execution Boundaries

The Kernel delegates execution to `RuntimeEngine`, which delegates to `TaskRunner`. The Kernel does NOT directly execute shell commands or Python modules.

### 3.2 Execution Pipeline

```
Bootstrap → Planning → Refining → Validating → Executing
→ Observing → Verifying → Checkpointing → Next Task | Recover | Stop
```

### 3.3 Budget Enforcement

Every execution run enforces:
- `max_llm_calls` — LLM call count limit
- `max_token_budget` — token budget limit
- `max_retries` — bounded retry count
- `max_runtime_seconds` — wall-clock time limit
- `internet_policy` — network access policy (off/by-default)

Budget check occurs BEFORE each task execution and BEFORE each LLM call.

### 3.4 TaskRunner Execution Semantics

| StepType | Behavior |
|---|---|
| `SHELL` | subprocess.run with explicit args, no shell=True |
| `PYTHON` | python -m <module> <args> |
| `INSPECT` | Project inspection, no command execution |

Each step records:
- `stdout` — captured output
- `stderr` — captured errors
- `exit_code` — integer exit code
- `duration_seconds` — wall-clock time
- `started_at` / `finished_at` — ISO 8601 timestamps

### 3.5 Recovery

Recovery is bounded by `max_retries`. Recovery strategies:
1. Local deterministic fix (syntax errors, obvious typos)
2. LLM-assisted repair (if budget permits)
3. Replan (generate new plan)
4. Escalate to BLOCKED (no budget for LLM repair)

---

## 4. Verification

### 4.1 Verification is an Independent Authority

Verification is NOT the executor declaring success. It is an independent authority that evaluates evidence against acceptance criteria.

### 4.2 Verification Layers

| Layer | What it verifies | Required evidence |
|---|---|---|
| Architectural | Module placement, interface compliance | File diff, import graph |
| Behavioral | Correct output against acceptance criteria | Test results, command output |
| Integration | Subsystem interaction | Multi-component test results |
| Regression | No existing functionality broken | Baseline vs. candidate comparison |
| Evidence | Required evidence is present and valid | Evidence ledger entries |
| Reproducibility | Same input → same output | Run record, checkpoint |
| Real-Task | End-to-end task completion | Run result + verification |
| Capability | Capability test result | Repeated evidence of capability |
| Adversarial | No constitutional violations | Adversarial test results |

### 4.3 Verification Gate

A task is VERIFIED only when:
1. All `acceptance_criteria` have corresponding evidence
2. No `verification_requirements` are failed
3. Evidence ledger contains entries for each expected evidence type
4. No regression detected

### 4.4 No Self-Declaration

LLM may NOT declare its own verification. `PolicyEngine.can_llm_declare_verification()` MUST return `False`.

---

## 5. Evidence

### 5.1 Claim → Evidence → Verification → Evaluation

| Claim | Required Evidence |
|---|---|
| implemented | File state / git diff |
| tested | Reproducible test result |
| verified | Evaluation + supporting evidence |
| learned | Lesson + reusable pattern |
| improved | Baseline + candidate + comparison |
| capability proven | Repeated capability evidence |
| authority promoted | Promotion record |

### 5.2 Evidence Types

```
TEST           — test runner output
ASSERTION      — programmatic assertion
COMMAND_RESULT — shell/python execution output
FILE_STATE     — file existence or diff
CHECKPOINT     — runtime checkpoint record
BENCHMARK      — performance measurement
REGRESSION     — regression test result
MANUAL         — human-validated evidence
```

### 5.3 Evidence Integrity Rules

1. No evidence without a corresponding run_id
2. No evidence with secret content (API keys, passwords)
3. Evidence ledger is append-only (idempotent on evidence_id)
4. Evidence MUST be captured at the time of the claim
5. Inferred evidence is not evidence

### 5.4 Evidence Ledger

The `EvidenceLedger` persists evidence at `/root/agent-core/evaluation/evidence.json`. Every recorded evidence MUST pass secret detection.

---

## 6. Evaluation

### 6.1 Achievement States

Four explicit states, each requiring distinct evidence thresholds:

| State | Evidence Threshold |
|---|---|
| `TASK_COMPLETED` | All task steps executed (may fail verification) |
| `GOAL_ACHIEVED` | All acceptance criteria satisfied |
| `SOLUTION_VALID` | Verification passed with required evidence |
| `SOLUTION_OPTIMAL` | Solution valid AND efficiency criteria met |

State transitions:
```
TASK_COMPLETED → GOAL_ACHIEVED → SOLUTION_VALID → SOLUTION_OPTIMAL
```
Regression is allowed (e.g., TASK_COMPLETED without GOAL_ACHIEVED is valid).

### 6.2 Evaluation Layers

| Layer | Weight | Description |
|---|---|---|
| CORRECTNESS | 0.30 | Execution correctness, no errors |
| REQUIREMENT_COVERAGE | 0.25 | All acceptance criteria covered |
| INTEGRATION | 0.15 | Knowledge used, experience recorded |
| REGRESSION_SAFETY | 0.20 | No existing functionality broken |
| EFFICIENCY | 0.10 | Time, LLM calls, retries within budget |

### 6.3 Verdict Determination

`PASS` only when:
1. No required criterion failed
2. CORRECTNESS score ≥ 0.5
3. Total weighted score ≥ 0.5

### 6.4 Code Runs ≠ Solution Optimal

"Code runs" → "TASK_COMPLETED" only.
"Tests pass" → "GOAL_ACHIEVED" only with acceptance criteria evidence.
"Verified" → "SOLUTION_VALID" only with full evidence ledger.

---

## 7. Experience

### 7.1 Experience Record

A single `Experience` record captures one run attempt. It is append-only (immutable after creation).

### 7.2 Experience Fields

- `run_id` — unique run identifier
- `goal` — task goal
- `action` — what was attempted
- `observation` — what actually happened (raw)
- `outcome` — success/failure description
- `failure` — if failed, what failed
- `recovery` — how recovery was applied
- `llm_calls` / `estimated_tokens` — cost metrics
- `lesson` — extracted lesson (may be empty)

### 7.3 Failure Category Detection

Deterministic failure classification:

| Category | Trigger patterns |
|---|---|
| NETWORK | "connection refused", "timeout", "network" |
| DEPENDENCY | "ModuleNotFoundError", "import error" |
| SYNTAX | "SyntaxError", "IndentationError" |
| TEST_FAILURE | "AssertionError", "test failed" |
| RUNTIME | "RuntimeError", "Exception" |
| TIMEOUT | "timed out", "timeout" |
| LOGIC | "AssertionError" with logic content |
| UNKNOWN | anything else |

### 7.4 Experience → Lesson Pipeline

```
Experience → Lesson extraction → Evidence check → Knowledge Candidate
                    ↓
            MIN_EVIDENCE_FOR_CANDIDATE = 2 experiences
```

---

## 8. Knowledge

### 8.1 Primitive Lifecycle State Machine

```
CANDIDATE → VALIDATED → VERIFIED → ACTIVE
    ↓
 REJECTED (terminal)
    ↓
DEPRECATED (terminal)
```

### 8.2 Transition Rules

| Transition | Required |
|---|---|
| CANDIDATE → VALIDATED | Schema validation passed |
| VALIDATED → VERIFIED | Validation + evidence count ≥ 1 |
| VERIFIED → ACTIVE | Evidence count ≥ 2 AND confidence ≥ 0.5 AND source_type ≠ GENERATED |
| Any → DEPRECATED | Administrator or evidence of obsolescence |
| Any → REJECTED | Validation failure or contradiction |

### 8.3 Generated ≠ Active

Primitives with `source_type = GENERATED` can never auto-promote to ACTIVE. They require explicit manual validation.

### 8.4 Knowledge Retrieval

- Retrieve relevant primitives by query
- Rank by confidence × relevance
- Filter by domain
- Expand by relation graph depth

---

## 9. Learning

### 9.1 Learning Definition

Learning requires evidence of improved future performance:

```
Task 1 → Pattern candidate
Task 2 → Pattern reinforced
Task 3 → Pattern reused
Result improvement vs baseline → Learning evidence
```

Saving logs is NOT learning. Observation is NOT learning. Learning requires a measurable improvement in a future task that uses the learned pattern.

### 9.2 Learning Pipeline

```
Experience → Lesson → Knowledge Candidate → Primitive
                                            ↓
                        Evidence count ≥ MIN_EVIDENCE (2)
                                        ↓
                    Confidence ≥ MIN_CONFIDENCE (0.3)
                                        ↓
                            VALIDATED → VERIFIED → ACTIVE
```

### 9.3 Contradiction Handling

If a new experience contradicts an existing lesson:
1. Both lessons remain (append-only)
2. New lesson marked CONTRADICTORY_OBSERVATION
3. Resolution requires RESOLVED_OBSERVATION with new evidence
4. Confidence is updated accordingly

---

## 10. Capability

### 10.1 Capability Model

Capabilities are defined independently from implementation:

| Capability | Definition | Capability Test |
|---|---|---|
| construct_task | Create TaskConstructionContract from intent | Contract validates correctly |
| decompose_task | Break goal into executable steps | Plan → Task steps conversion |
| select_evidence | Choose relevant evidence for evaluation | Evidence ledger query |
| detect_failure | Classify failure into failure categories | Category detection tests |
| recover | Apply appropriate recovery strategy | Recovery action tests |
| verify | Verify task result against acceptance criteria | Verification result tests |
| reuse_pattern | Retrieve and apply knowledge primitive | Retrieval + application test |
| improve_task_construction | Propose improvement from experience | Improvement candidate tests |

### 10.2 Capability Test Definition

Each capability MUST have a `CapabilityTest` that produces:
- `tested` — the capability was exercised
- `verified` — the capability produced correct output
- `repeated` — the capability works consistently across multiple inputs
- `generalized` — the capability works on novel inputs
- `capability_proven` — repeated evidence across diverse scenarios

### 10.3 Capability Proven Status

A capability is PROVEN only when:
- At least 3 diverse test scenarios all pass
- No regressions in related capabilities
- Evidence of capability being used in a real task

---

## 11. Authority

### 11.1 Authority Matrix

| Decision | Administrator/GPT | Kernel | TaskRunner | KnowledgeEngine | EvaluationEngine |
|---|---|---|---|---|---|
| Architecture | **DECIDES** | Implements | — | — | — |
| Task definition | **DECIDES** | Validates | — | — | — |
| Implementation | — | — | **EXECUTES** | — | — |
| Verification | Advises | **AUTHORITY** | — | — | Evaluates |
| Knowledge promotion | Advises | — | — | **PROMOTES** | — |
| Capability promotion | — | **AUTHORITY** | — | — | Evaluates |
| Authority promotion | **DECIDES** | — | — | — | — |
| Architectural change | **DECIDES** | — | — | — | — |

### 11.2 LLM Boundary

The LLM (GPT) is treated as an external advisor. It MAY NOT:
- Declare its own verification
- Promote its own knowledge
- Accept its own improvement
- Bypass a validator
- Override Administrator architecture

These boundaries are enforced by `PolicyEngine`.

### 11.3 EARLY / MID / FINAL Authority Model

#### EARLY (current — v1.0 baseline)

| Actor | Responsibility |
|---|---|
| GPT/Administrator | Constructs and directs all tasks |
| User | Manually transfers tasks to NanoBot |
| Kernel | Executes, records, verifies, learns |
| TaskRunner | Executes individual steps |

Automatic dispatch: **DISABLED**

#### MID (target: v1.1)

| Actor | Responsibility |
|---|---|
| GPT/Administrator | Handles difficult decisions and escalation |
| Kernel | Progressively assumes planning, decomposition, verification |
| Promotion Gates | Proven capability required for each assumption |

#### FINAL (target: v2.0)

| Actor | Responsibility |
|---|---|
| GPT/Administrator | Sets high-level strategy only |
| Kernel | Operational brain |
| TaskRunner | Execution worker only |
| Authority bounded by | Constitution |

### 11.4 Promotion Gate Criteria for Authority Model Transitions

| Transition | Required Evidence |
|---|---|
| EARLY → MID | 5+ successful autonomous task completions, capability tests for all 8 capabilities pass, no constitutional violations in 20 consecutive runs |
| MID → FINAL | Administrator explicitly approves after evidence review |

---

## 12. Promotion Gate

### 12.1 Knowledge Promotion Gates

| Status | Promotion Gate |
|---|---|
| CANDIDATE → VALIDATED | Schema validation + semantic validation pass |
| VALIDATED → VERIFIED | Validation + evidence_id present |
| VERIFIED → ACTIVE | Evidence count ≥ 2 AND confidence ≥ 0.5 AND source_type ≠ GENERATED |

### 12.2 Improvement Promotion Gates

| Stage | Gate |
|---|---|
| PROPOSED | Hypothesis + baseline_eval_id + target defined |
| PROPOSED → TESTING | All required tests identified |
| TESTING → ACCEPTED | Regression check: baseline → candidate, no regression, evidence present |
| TESTING → REJECTED | Any regression OR insufficient evidence |

Comparator thresholds:
- REGRESSION_THRESHOLD: -0.05 (5% drop = regression)
- IMPROVEMENT_THRESHOLD: +0.05 (5% gain = improvement)
- NEUTRAL_BAND: ±0.05

### 12.3 Capability Promotion Gates

| Stage | Gate |
|---|---|
| CANDIDATE → TESTED | At least 1 successful capability test |
| TESTED → VERIFIED | Evidence of consistent output |
| VERIFIED → REPEATED | 3+ diverse test scenarios pass |
| REPEATED → GENERALIZED | Novel input test passes |
| GENERALIZED → PROVEN | 5+ real-task uses with no regression |

### 12.4 Knowledge → Experience Promotion Gates

| Stage | Gate |
|---|---|
| CANDIDATE | MIN_EVIDENCE_FOR_CANDIDATE (2) experiences of same pattern |
| LEARNED | Lesson extracted + evidence_count ≥ 2 |
| REUSABLE | Primitive promoted through VALIDATED → VERIFIED → ACTIVE |

---

## 13. Adversarial Verification

### 13.1 Adversarial Test Cases

The following cases MUST be tested and MUST NOT result in silent failure or constitutional violation:

| Case | Expected Behavior |
|---|---|
| Malformed Task Contract | `validate()` returns `(False, reason)`, execution blocked |
| Missing evidence | Evaluation verdict = FAIL |
| Fabricated success | Verification FAILS (evidence ledger check) |
| False verification | `can_llm_declare_verification()` = False enforced |
| Incomplete execution | Budget check stops execution, FAILED status |
| Wrong architectural placement | Module import error or architectural test FAILS |
| Forbidden authority escalation | Policy engine raises PermissionError |
| Unauthorized architecture change | Repository unchanged unless evidence exists |
| Regression | Comparator returns REGRESSED verdict |
| Repeated failure | Promoted to knowledge after 2+ occurrences |
| Inconsistent persisted state | Corrupt files return None, list_all skips corrupt |
| Misleading executor report | Verification phase cross-checks with evidence ledger |
| Improvement claim without baseline | `decide()` returns REJECTED |
| Knowledge promotion without verification | GENERATED source_type cannot reach ACTIVE |
| Capability promotion without repeated evidence | Capability not promoted past TESTED |

### 13.2 Secret Detection

All persistence layers MUST detect and refuse secrets matching patterns:
- `sk-[A-Za-z0-9]{20,}` (OpenAI API key)
- `AIza[0-9A-Za-z\-_]{20,}` (Google API key)
- `ghp_[A-Za-z0-9]{20,}` (GitHub token)
- `xoxb-[A-Za-z0-9-]{20,}` (Slack token)

### 13.3 Corrupt State Handling

| Corruption Type | Expected Behavior |
|---|---|
| Corrupt JSON file | Load returns None, no crash |
| Corrupt experience file | Store skips file, list_all excludes it |
| Corrupt knowledge file | Store skips file, retrieval excludes it |
| Missing run_id | Store raises ExperienceStoreError |
| Duplicate run_id | Store raises ExperienceStoreError |

---

## 14. Reproducibility

### 14.1 Minimum Execution Record

Every run MUST capture:

| Field | Source |
|---|---|
| `run_id` | KernelLifecycle |
| `goal` | KernelContext |
| `project_id` | KernelContext |
| `kernel_phase` | KernelContext |
| `kernel_status` | KernelContext |
| `started_at` / `finished_at` | KernelLifecycle |
| `llm_calls` / `estimated_tokens` | PhaseMetrics |
| `errors` | KernelContext |
| `knowledge_retrieved` | KernelContext |
| `plan` | KernelContext |
| Checkpoint files | CheckpointStore |
| Evidence ledger | EvidenceLedger |

### 14.2 Checkpoint Persistence

- Atomic write (write to `.tmp`, then `os.replace`)
- Timestamped at each phase transition
- Load returns `None` for corrupt/missing files
- Resume from last checkpoint is idempotent

### 14.3 Run Comparison

To compare two runs for reproducibility:
1. Same goal
2. Same project_id
3. Same constraints (budget, policy)
4. Same subsystems versions
5. Run on same or equivalent environment

---

## 15. Improvement

### 15.1 Improvement Pipeline

```
Baseline Evaluation
        ↓
New Strategy / Hypothesis
        ↓
Proposed Change
        ↓
Execution
        ↓
Evidence Collection
        ↓
Baseline vs Candidate Comparison
        ↓
Improvement Decision (ACCEPTED / REJECTED)
```

### 15.2 Improvement Requirements

| Required Element | Description |
|---|---|
| `baseline_evaluation_id` | Evaluation ID of baseline (MUST exist) |
| `proposed_change` | Explicit description of change |
| `hypothesis` | What improvement is expected and why |
| `expected_benefit` | Quantified expected improvement |
| `risk` | Risk assessment |
| `tests_required` | Tests that must pass for candidate |

### 15.3 No Baseline → No Improvement Claim

An improvement candidate without a baseline evaluation_id MUST be REJECTED.

### 15.4 Improvement Engine Rules

- PROPOSED → TESTING: requires hypothesis and target
- TESTING → ACCEPTED: comparator evidence + no regression
- TESTING → REJECTED: any regression or insufficient evidence
- ACCEPTED/REJECTED: terminal states
- LLM may NOT mark its own improvement as ACCEPTED

---

## 16. Agent Philosophy Architecture

### 16.1 Conceptual Hierarchy & Distinctions

Agent Core maintains strict conceptual separation across architectural abstractions:

| Abstraction | Core Question | Description |
|---|---|---|
| **Kernel** | *What the Agent fundamentally is* | Stateless orchestrator, safety invariants, policy budgets, and orchestration loop guarantees. |
| **Rules / Contracts** | *What the system requires* | Machine-checkable task contracts, schemas, verification criteria, and acceptance gates. |
| **Experience** | *What happened* | Immutable append-only logs of execution runs, step actions, outcomes, and observations. |
| **Lesson** | *What was learned from what happened* | Extracted patterns or observations from experience. |
| **Philosophy** | *How the Agent tends to work* | Soft behavioral tendencies, operational self-knowledge, and preferences derived from learning & human teaching. |
| **Knowledge** | *What the Agent believes/knows* | Verified primitives, domain concepts, and proven facts about projects or systems. |

These abstractions MUST NOT be collapsed into a single layer.

### 16.2 Core Behavioral Pipeline

```
Kernel → Experience → Lesson → Philosophy Candidate → Evidence → Tendency → Behavior → Result → new Evidence
```

1. Experiences produce Lessons via `LessonEngine`.
2. Lessons propose `PhilosophyTendency` candidates with explicit provenance (`PhilosophyEngine.propose_candidate_from_lesson()`).
3. Humans/operators teach, support, challenge, modify, reject, or retire tendencies via `PhilosophyEngine`.
4. Planners consult active tendencies as **SOFT PREFERENCES**.

### 16.3 Absolute Precedence Rule

$$\text{Kernel / Security / Contracts} > \text{Verification Requirements} > \text{Explicit Task Requirements} > \text{Philosophy / Tendencies}$$

Philosophy represents soft tendencies only. Philosophy MUST NOT override Kernel constraints, bypass verification requirements, or violate explicit task contracts.

---

## Appendix A: Existing Code Assessment

### KEEP (proven architectural value)

| Module | Reason |
|---|---|
| `core/kernel/kernel.py` | Integrated loop, policy enforcement, lifecycle management |
| `core/kernel/schema.py` | KernelContext, KernelPhase, KernelStatus |
| `core/kernel/evidence.py` | Evidence recording, ledger integration |
| `core/kernel/orchestrator.py` | Phase orchestration, event bus, lifecycle coordination |
| `core/kernel/policy.py` | Deterministic policy decisions, LLM boundaries |
| `core/kernel/context.py` | Knowledge → planning integration |
| `core/kernel/lifecycle.py` | Atomic persistence, crash recovery |
| `core/tasks/schema.py` | TaskConstructionContract, DeepTaskPrompt, validation |
| `core/runtime/engine.py` | Full execution pipeline, budget enforcement |
| `core/runtime/schema.py` | RunState, RunPhase, RunStatus, PhaseMetrics |
| `core/runtime/checkpoint.py` | Atomic checkpoint persistence |
| `core/experience/engine.py` | Experience → Lesson → Candidate pipeline |
| `core/experience/schema.py` | Experience record, append-only |
| `core/experience/learner.py` | Experience → Knowledge Candidate with evidence thresholds |
| `core/experience/promotion.py` | Experience → Knowledge promotion bridge |
| `core/knowledge/engine.py` | Knowledge retrieval, promotion, validation |
| `core/knowledge/schema.py` | Primitive, Provenance, Lifecycle state machine |
| `core/knowledge/promotion.py` | Evidence-based promotion through lifecycle |
| `core/knowledge/validator.py` | 4-layer validation (schema, semantic, provenance, lifecycle) |
| `core/evaluation/engine.py` | Full evaluation pipeline with evidence |
| `core/evaluation/schema.py` | Evidence, Evaluation, AchievementState, ImprovementCandidate |
| `core/evaluation/evaluator.py` | Multi-layer scoring, verdict determination |
| `core/evaluation/comparator.py` | Baseline vs candidate comparison |
| `core/evaluation/improvement.py` | Improvement lifecycle (PROPOSED → ACCEPTED/REJECTED) |
| `core/evaluation/criteria.py` | 15 criteria across 5 layers |
| `core/evaluation/scorer.py` | Deterministic scoring per layer |
| `core/evaluation/evidence.py` | Evidence ledger with secret detection |
| `core/events/bus.py` | Thread-safe bounded buffer event bus |
| `core/events/schema.py` | EventPhase, EventStatus, AgentEvent |
| `core/config/manager.py` | ConfigManager, secret isolation |
| `core/planner/validator.py` | Plan validation before execution |
| `tests/test_kernel.py` | E2E, crash/resume, adversarial, integration |
| `tests/test_construction.py` | Contract validation, serialization, failure handling |

### ADAPT (useful but needs correction)

| Module | Correction Required |
|---|---|
| `core/kernel/orchestrator.py:243` | `outcome` undefined variable → use `exp.outcome` |
| `core/kernel/orchestrator.py:verify()` | Add actual verification (not just phase transition) |

### EXPERIMENTAL (insufficient evidence for full adoption)

| Module | Evidence Status |
|---|---|
| `intelligence/` | Empty directories, no tests, no evidence of value |
| `library/` | Empty packages, no evidence of value |
| `verification/benchmarks/` | No implementation evidence |
| `verification/evaluator/` | No implementation evidence |
| `kernels/` | Empty directory |

### REMOVE (no demonstrated value)

| Module | Reason |
|---|---|
| None currently | All existing modules have test coverage |

---

## Appendix B: Compliance Checklist

- [x] Stdlib only (no external dependencies)
- [x] No `eval()`, no `shell=True`, no `os.system`
- [x] API keys never logged or persisted
- [x] Prompt ≠ Contract (validated separately)
- [x] Generated ≠ Knowledge (source_type enforcement)
- [x] Tested ≠ Verified (evidence threshold enforcement)
- [x] Completed ≠ Goal Achieved (4 achievement states distinct)
- [x] Capability proven → Authority promoted (promotion gates)
- [x] Worker cannot override Administrator architecture (policy engine)
- [x] Verification cannot be self-declared by executor (LLM boundary)
- [x] Improvement requires baseline (improvement schema)
- [x] Architectural changes require evidence (constitution enforcement)
- [x] Unproven capability cannot self-promote authority (capability gates)

---

*Specification version: 1.0.0*
*Created: 2025*
*Authority: This document governs all layers below it.*
