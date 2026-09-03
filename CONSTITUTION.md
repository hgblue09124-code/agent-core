# Kernel Constitution — agent-core v1.0

> **This document is the supreme law of agent-core.**
> All code, architecture, and policy MUST conform.
> Violation of any rule is a constitutional breach.
> A breach MUST be reported and MUST be fixed before continuing.

---

## Preamble

The Kernel Constitution establishes the authoritative rule system for agent-core. It defines who may decide, what may never be violated, where architectural boundaries lie, and how authority may be promoted.

This constitution is machine-checkable where possible (see `constitution/schemas/`). The existence of a test does not make a rule constitutional — a rule is constitutional when it is defined here and enforced by the implementation.

---

## Article I: Authority

### Section 1.1 — Architecture

**Who may decide architecture:** Administrator / GPT (external)

The Administrator MAY:
- Define the overall system architecture
- Approve architectural changes
- Define the authority model transitions
- Set policy defaults

The Administrator MAY NOT:
- Override kernel-level safety invariants
- Bypass the policy engine at runtime
- Silently modify constitutional modules without evidence

**Kernel MAY:**
- Implement architecture as defined by Administrator
- Enforce architectural boundaries
- Report architectural violations

**Kernel MAY NOT:**
- Define its own architecture
- Change its own authority boundaries
- Self-modify without Administrator approval

### Section 1.2 — Task Definition

**Who may decide:** Administrator / GPT (external)

The Administrator MAY:
- Author TaskConstructionContracts
- Define acceptance criteria
- Define evidence requirements
- Define failure protocols

**Kernel MAY:**
- Validate task contracts
- Refuse execution of invalid contracts
- Augment task context with knowledge

**Kernel MAY NOT:**
- Modify the objective of a task
- Change acceptance criteria mid-execution
- Skip verification of a completed task

### Section 1.3 — Implementation

**Who may decide:** TaskRunner (execution layer)

**TaskRunner MAY:**
- Execute shell commands as defined by task steps
- Execute Python modules as defined by task steps
- Report execution results

**TaskRunner MAY NOT:**
- Execute commands not defined in the task contract
- Access API keys or secrets
- Modify files outside the task scope
- Skip verification after execution

### Section 1.4 — Verification

**Who may decide:** EvaluationEngine (independent authority)

**EvaluationEngine MAY:**
- Evaluate evidence and produce verdicts
- Score performance across evaluation layers
- Compare baseline vs candidate for improvement decisions

**EvaluationEngine MAY NOT:**
- Self-declare verification (executor is separate from evaluator)
- Override the policy engine's LLM boundary decisions
- Accept improvement without evidence

### Section 1.5 — Knowledge Promotion

**Who may decide:** KnowledgeEngine (with evidence gate)

**KnowledgeEngine MAY:**
- Promote primitives through the lifecycle (CANDIDATE → VALIDATED → VERIFIED → ACTIVE)
- Reject primitives that fail validation
- Deprecate primitives that are obsolete

**KnowledgeEngine MAY NOT:**
- Auto-promote GENERATED primitives to ACTIVE
- Skip validation before VERIFIED
- Skip evidence count check before ACTIVE

### Section 1.6 — Capability Promotion

**Who may decide:** Kernel (with capability test gate)

**Kernel MAY:**
- Promote capabilities through capability stages
- Test capabilities independently
- Record capability evidence

**Kernel MAY NOT:**
- Promote capability without repeated evidence
- Self-certify its own capability without independent tests

### Section 1.7 — Authority Promotion

**Who may decide:** Administrator / GPT (external)

**Authority promotion** means the transition from EARLY → MID → FINAL authority model.

**Administrator MAY:**
- Approve authority model transitions
- Set new capability thresholds for promotion

**Kernel MAY:**
- Request authority promotion (submit evidence)
- Operate within current authority model

**Kernel MAY NOT:**
- Assume additional authority without Administrator approval
- Modify the authority model autonomously

### Section 1.8 — Architectural Replacement

**Who may decide:** Administrator / GPT (external)

**Administrator MAY:**
- Replace any architectural module
- Deprecate existing subsystems
- Introduce new subsystems

**Administrator MAY NOT:**
- Replace a module without running the full regression suite
- Remove constitutional rules
- Reduce verification requirements

---

## Article II: Absolute Invariants

These rules MUST NEVER be violated under any circumstances.

### INV-1: No Evidence → No Claim

**Rule:** A claim of "implemented", "tested", "verified", "learned", "improved", "capability proven", or "authority promoted" MUST be accompanied by evidence.

**Enforcement:** EvidenceLedger MUST reject evidence-less records. EvaluationEngine MUST return FAIL verdict when required evidence is missing.

**Test:** `test_no_pass_without_evidence()` — `EvaluationEngine.evaluate()` with empty evidence → verdict MUST be "FAIL".

### INV-2: Generated ≠ Knowledge

**Rule:** A primitive with `source_type = GENERATED` MUST NOT reach `ACTIVE` status without explicit manual validation.

**Enforcement:** `KnowledgeValidator` checks `LIFECYCLE_GENERATED_ACTIVE` and adds error. `PromotionEngine.can_promote()` returns False for GENERATED → ACTIVE.

**Test:** `test_generated_cannot_activate()` — primitive with GENERATED source_type → ACTIVE → MUST raise `LifecycleError`.

### INV-3: Tested ≠ Verified

**Rule:** Passing tests alone does NOT constitute verification. Verification requires evidence against acceptance criteria.

**Enforcement:** `EvaluationEngine.evaluate()` requires evidence across all required layers. SOLUTION_VALID achievement requires full evidence ledger.

**Test:** `test_achievement_state_distinct()` — the 4 states MUST be distinct values.

### INV-4: Completed ≠ Goal Achieved

**Rule:** `TASK_COMPLETED` (all steps executed) is DISTINCT from `GOAL_ACHIEVED` (acceptance criteria satisfied).

**Enforcement:** `AchievementState` enum has 4 distinct values. `Evaluator._determine_verdict()` uses achievement level to determine evidence thresholds.

**Test:** `test_achievement_state_distinct()` in test_evaluation.py.

### INV-5: Capability Proven → Authority Promoted

**Rule:** A capability MUST be proven (repeated evidence, no regression) before it can trigger authority promotion.

**Enforcement:** `capability_test()` → `tested` → `verified` → `repeated` → `generalized` → `proven`. Each stage requires evidence.

**Test:** Capability tests in test_specification.py.

### INV-6: Worker Cannot Override Administrator Architecture

**Rule:** TaskRunner (worker) MUST NOT modify architectural files (kernel, policy, schema) without explicit Administrator authorization.

**Enforcement:** Task scope is defined in TaskConstructionContract. `files_in_scope` and `files_not_in_scope` are enforced.

**Test:** Architectural boundary test in test_adversarial_spec.py.

### INV-7: Verification Cannot Be Self-Declared

**Rule:** The executor of a task MAY NOT declare that the task is verified. Verification is an independent authority.

**Enforcement:** `PolicyEngine.can_llm_declare_verification()` returns `False`. `KernelOrchestrator.verify()` raises `PermissionError` if LLM tries to self-declare.

**Test:** `test_llm_not_used_for_verification()` in test_kernel.py.

### INV-8: Improvement Requires Baseline

**Rule:** An improvement candidate MUST have a `baseline_evaluation_id`. Without a baseline, improvement cannot be claimed.

**Enforcement:** `ImprovementEngine.decide()` requires `baseline_evaluation_id` in comparator evidence. `Comparator.accept_improvement()` returns False without evidence.

**Test:** `test_accepted_requires_evidence()` in test_evaluation.py.

### INV-9: Architectural Changes Require Evidence

**Rule:** Any change to a constitutional module (kernel, schema, policy, evaluation, experience, knowledge) MUST be accompanied by evidence that the change does not break existing tests.

**Enforcement:** Full regression suite MUST pass after any constitutional module change.

**Test:** `test_regression_tests_run()` — pytest full suite → MUST be 100% PASS.

### INV-10: Unproven Capability Cannot Self-Promote Authority

**Rule:** A capability that has not been proven through repeated, generalized, successful tests cannot promote its own authority level.

**Enforcement:** Capability promotion gate requires evidence_ids from real tasks.

**Test:** Capability adversarial tests in test_adversarial_spec.py.

---

## Article III: Architectural Boundary

### Section 3.1 — Administrator / GPT

**Boundary:** Above the kernel. Defines goals, architecture, and policy.

**MAY:**
- Author TaskConstructionContracts
- Define acceptance criteria and evidence requirements
- Set policy defaults
- Approve architectural changes
- Approve authority model transitions

**MUST NOT:**
- Execute commands directly
- Modify kernel state mid-run
- Bypass verification
- Override LLM boundary policy

### Section 3.2 — Kernel (Orchestrator)

**Boundary:** Coordinates all subsystems. Stateless. Checkpoint-aware.

**MAY:**
- Bootstrap run context
- Call knowledge retrieval
- Orchestrate execution through RuntimeEngine
- Record experience
- Trigger evaluation
- Emit events

**MUST NOT:**
- Execute shell commands directly
- Call LLM directly (delegates to Planner)
- Declare verification of its own output
- Persist API keys or secrets

### Section 3.3 — Runtime Engine (Execution)

**Boundary:** Executes tasks. Stateful per-run. Checkpointed.

**MAY:**
- Execute TaskStep commands via TaskRunner
- Diagnose failures
- Retry bounded number of times
- Request LLM repair (with budget)
- Checkpoint state after each phase

**MUST NOT:**
- Execute commands outside task scope
- Access secrets
- Skip verification
- Bypass budget limits

### Section 3.4 — TaskRunner (Worker)

**Boundary:** Executes individual steps. Deterministic.

**MAY:**
- Run shell commands
- Run Python modules
- Capture stdout/stderr
- Verify step output

**MUST NOT:**
- Modify task contract
- Skip verification
- Access API keys

### Section 3.5 — Planner (LLM)

**Boundary:** Produces plans only. Never executes.

**MAY:**
- Generate Plan from goal
- Suggest repairs for failed steps
- Provide planning context

**MUST NOT:**
- Execute any command
- Declare verification
- Modify kernel state
- Access secrets

### Section 3.6 — Knowledge Engine

**Boundary:** Manages knowledge primitives. Evidence-gated promotion.

**MAY:**
- Create, validate, promote primitives
- Retrieve relevant primitives
- Deprecate obsolete primitives

**MUST NOT:**
- Promote GENERATED to ACTIVE without manual validation
- Skip evidence count check
- Bypass lifecycle state machine

### Section 3.7 — Experience Engine

**Boundary:** Records experiences. Append-only.

**MAY:**
- Record experience from run
- Extract lessons
- Produce knowledge candidates

**MUST NOT:**
- Delete or modify existing experiences
- Fabricate experiences

### Section 3.8 — Evaluation Engine

**Boundary:** Independent evaluator. Evidence-backed verdicts.

**MAY:**
- Score across evaluation layers
- Compare baseline vs candidate
- Return FAIL verdict

**MUST NOT:**
- Self-declare verification
- Accept improvement without evidence
- Override LLM boundary decisions

---

## Article IV: EARLY / MID / FINAL Authority Model

### Section 4.1 — EARLY (Current Baseline — v1.0)

**Definition:** GPT/Administrator directs all tasks. User manually transfers tasks. No automatic dispatch.

| Actor | Action |
|---|---|
| GPT/Administrator | Constructs and directs all tasks |
| User | Manually transfers tasks to NanoBot |
| Kernel | Executes, records, verifies, learns |
| TaskRunner | Executes individual steps |
| Planner | Produces plans on-demand |
| KnowledgeEngine | Stores and retrieves primitives |
| EvaluationEngine | Evaluates with evidence |

**Automatic dispatch:** DISABLED

**Budget:** Hard limits enforced (max_llm_calls, max_retries, etc.)

### Section 4.2 — MID (Target: v1.1)

**Definition:** Agent Core progressively assumes planning/decomposition/verification responsibilities. GPT handles difficult decisions and escalation.

**Progressive Assumptions:**
1. Task construction → Agent Core (after 5 successful autonomous constructions)
2. Task decomposition → Agent Core (after 5 successful autonomous decompositions)
3. Verification → Agent Core (after capability tests pass for verify capability)
4. Knowledge promotion → Agent Core (after knowledge engine fully operational)

**Promotion Gate (EARLY → MID):**
- 5+ successful autonomous task completions (no human intervention required)
- All 8 capabilities have passed TESTED stage
- No constitutional violations in 20 consecutive runs
- Administrator review and approval

### Section 4.3 — FINAL (Target: v2.0)

**Definition:** GPT sets high-level strategy. Agent Core becomes operational brain. TaskRunner remains execution worker. Authority bounded by Constitution.

**Operational Brain Responsibilities:**
- Task construction (autonomous)
- Task decomposition (autonomous)
- Execution orchestration (autonomous)
- Verification (autonomous)
- Knowledge management (autonomous)
- Learning (autonomous)

**Strategy Responsibilities (GPT):**
- Goal definition
- Architectural decisions
- Authority model transitions
- Major policy changes

**Promotion Gate (MID → FINAL):**
- All 8 capabilities have reached PROVEN stage
- 100+ successful autonomous runs
- Zero constitutional violations in 50 consecutive runs
- Explicit Administrator approval after evidence review

### Section 4.4 — Authority Transition Rules

| Transition | Evidence Required | Decision Authority |
|---|---|---|
| EARLY → MID | 5 autonomous completions, 8 capabilities TESTED, 20 clean runs | Administrator |
| MID → FINAL | All 8 PROVEN, 100 autonomous runs, 50 clean runs | Administrator |
| Any backtrack | Constitutional violation evidence | Administrator |

---

## Article V: Evidence Integrity

### Section 5.1 — Evidence Recording

All evidence MUST be recorded at the time of the claim. Inferred evidence is not evidence.

### Section 5.2 — Secret Detection

All evidence, experience, and knowledge persistence layers MUST detect and refuse secrets matching these patterns:
```
sk-[A-Za-z0-9]{20,}
AIza[0-9A-Za-z\-_]{20,}
ghp_[A-Za-z0-9]{20,}
xoxb-[A-Za-z0-9-]{20,}
```

### Section 5.3 — Evidence Ledger

The EvidenceLedger is the authoritative record of evidence. It is:
- Append-only (idempotent on evidence_id)
- Persistent (survives process restart)
- Secret-filtered (refuses secrets)

---

## Article VI: Constitutional Enforcement

### Section 6.1 — Enforcement Mechanisms

| Rule | Mechanism |
|---|---|
| No evidence → No claim | `EvidenceLedger.record()` refuses empty evidence |
| Generated ≠ Active | `KnowledgeValidator` + `PromotionEngine` |
| Tested ≠ Verified | `Evaluator._determine_verdict()` + achievement states |
| Completed ≠ Goal Achieved | `AchievementState` enum (4 distinct values) |
| Capability proven → Authority | `CapabilityTest` gate + promotion stages |
| Worker cannot override architecture | Task scope + `files_not_in_scope` |
| Verification not self-declared | `PolicyEngine.can_llm_declare_verification()` = False |
| Improvement requires baseline | `ImprovementEngine.decide()` + `Comparator` |
| Architectural change requires evidence | Full regression suite |
| Unproven capability cannot self-promote | Capability promotion gate |

### Section 6.2 — Constitutional Violation Reporting

A constitutional violation MUST be:
1. Detected by a test or runtime check
2. Reported with the specific article, section, and invariant violated
3. Fixed before the next run
4. Documented in the run record

---

## Article VII: Amendments

### Section 7.1 — Amendment Process

An amendment to this constitution requires:
1. Written proposal by Administrator
2. Impact assessment (which modules are affected)
3. Full regression suite passes with new rules
4. Adversarial tests pass with new rules
5. Written approval by Administrator

### Section 7.2 — Emergency Suspension

In case of critical system failure, the Administrator MAY temporarily suspend non-safety constitutional rules. This suspension MUST be:
1. Time-limited (max 24 hours)
2. Documented with reason
3. Reviewed within 24 hours
4. Restored or replaced with permanent fix within 72 hours

Safety invariants (Invariants 1, 2, 6, 7) CANNOT be suspended under any circumstances.

---

## Article VIII: Interpretation

### Section 8.1 — Ambiguity Resolution

Ambiguity in this constitution MUST be resolved by:
1. Reading the machine-checkable schemas in `constitution/schemas/`
2. If still ambiguous, Administrator interpretation prevails
3. If still ambiguous, the more restrictive interpretation applies

### Section 8.2 — Conflict Resolution

If a constitutional rule conflicts with implementation, the constitution prevails. Implementation MUST be modified to match.

---

*Constitution version: 1.0.0*
*Specification version: 1.0.0*
*Authority: This constitution governs all layers below it.*
*Amended: 2025*
