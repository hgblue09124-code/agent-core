# PLANNER_REPORT.md

> **Scope**: LLM Planner v0.2 — agent-core upgrade from
> "Project Awareness + Deterministic Task Execution" to
> "Project Awareness + LLM-assisted Task Planning + Deterministic Task Execution".
>
> **Core principle**: LLM = PLANNER, TaskRunner = EXECUTOR, Verification = AUTHORITY.
>
> The LLM NEVER executes commands. It only produces a structured plan.
> Existing TaskRunner remains the only execution component.

---

## TL;DR

> **LLM-generated plans are not execution results.**
> **Verification remains authoritative.**

The Planner v0.2 module produces validated `Plan` objects from
user intent + project context. The Plan is then optionally converted
to a `Task`, which the existing `TaskRunner` executes.

- **No LLM invocation required for tests** — `MockPlannerProvider` returns
  valid plans offline.
- **Provider-agnostic**: `OpenRouterPlannerProvider`,
  `LocalPlannerProvider` (ollama/LM Studio), and `MockPlannerProvider` exist.
- **Token-aware context**: builds ≤ 4000 token prompts (configurable),
  labeled APPROXIMATE.
- **Strict validation**: rejects empty objectives, missing steps,
  dangerous commands (`rm -rf`, `eval()`, shell injection patterns),
  cyclic dependencies, unregistered project IDs.
- **CLI**: `python -m core.planner.cli plan <project_id> "<objective>" [--save]`.
- **120 tests pass** (53 planner + 39 task engine + 28 project manager).

---

## A. Before state (after v0.1)

```
agent-core/
├── core/projects/        ← project registry + context loader
├── core/tasks/           ← deterministic task engine
├── projects/registry.json
├── tasks/                ← task JSON files
└── tests/                ← 67 tests
```

**What it could do**: identify Cuu-Gioi, run shell / python / inspect
commands via task definitions. **What it could NOT do**: turn
"natural-language intent" into a structured plan.

---

## B. After state

```
agent-core/
├── core/projects/        ← unchanged
├── core/tasks/           ← unchanged
├── core/planner/         ← NEW
│   ├── __init__.py
│   ├── schema.py         ← Plan, PlanStep, VerificationCriterion, enums
│   ├── context.py        ← ContextBuilder + token estimator
│   ├── prompt.py         ← deterministic PromptBuilder
│   ├── validator.py      ← PlanValidator (structural + safety)
│   ├── planner.py        ← Planner + provider implementations + plan_to_task
│   └── cli.py            ← CLI: plan | validate
├── tests/test_planner.py ← NEW: 53 tests
└── PLANNER_REPORT.md     ← this report
```

**Total tests**: 28 (project) + 39 (task) + 53 (planner) = **120 passing**.

---

## C. Architecture

```
User Intent
    ↓
Project Context  ← core/projects (existing)
    ↓
LLM Planner  ← core/planner (new)
    ├─ ContextBuilder    (token-aware)
    ├─ PromptBuilder     (deterministic)
    ├─ PlannerProvider   (OpenRouter / Local / Mock)
    └─ PlanValidator     (structural + safety)
    ↓
Structured Plan
    ↓
plan_to_task()
    ↓
TaskManager.create_task()
    ↓
Task (existing schema)
    ↓
TaskRunner.run()  ← core/tasks (existing, unchanged)
    ↓
Observation
    ↓
VerificationResult (existing)
    ↓
Result
```

**Critical boundaries**:

| Concern | Owner | Cannot do |
|---|---|---|
| Project discovery | ProjectManager | nothing else |
| **Plan generation** | **Planner** | **execute commands** |
| Plan validation | PlanValidator | generate plans |
| **Plan → Task** | **plan_to_task()** | **execute** |
| **Task execution** | **TaskRunner** | **plan anything** |
| **Verification** | **TaskRunner** | **modify plan** |

---

## D. Planner/Runner boundary

**The LLM NEVER executes commands.** The Planner is purely a code
generator that returns a JSON-shaped plan. The Runner is purely an
executor that runs predefined steps. The two communicate only through
JSON files in `tasks/`.

This separation is enforced:

1. Planner produces `Plan` (not `Task`).
2. `PlanValidator` checks the plan before conversion.
3. `plan_to_task()` translates `PlanStep` → `TaskStep`.
4. The user must run `python -m core.tasks.cli run TASK-XXXX` to execute.
5. `--save` only writes the task; it does NOT run it.

If `--save` is omitted, no task file is created at all.

---

## E. Context strategy

The ContextBuilder is token-aware:

1. **Reads from existing ProjectManager** — no duplication.
2. **Selects** three documents: AGENT.md, ARCHITECTURE.md,
   source-of-truth.md + project metadata.
3. **Limits** by character count: `max_tokens × 4 chars`.
4. **Skips** documents that would exceed the budget.
5. **Returns stats**: `total_chars`, `approx_tokens`,
   `documents_included`, `documents_excluded`.

**Default budget**: 4000 tokens (≈ 16000 chars).

```
Context:
  Tổng chars : 14013
  Tokens ≈    : 3133 (APPROXIMATE)
  Docs        : project_metadata, AGENT.md, source-of-truth.md
```

---

## F. Token estimation strategy

The estimator uses a **deterministic character/word approximation**:

- `tokens ≈ chars / 4` (English heuristic)
- `tokens ≈ words / 0.75` (word-based)
- Combined: `(char_est + word_est) / 2`

The output is **explicitly labeled APPROXIMATE** in every printout.
Production code should swap in `tiktoken` if exact counts are required.

The estimator is wrapped behind three pure functions:
- `estimate_tokens(text)` — char-based
- `estimate_tokens_words(text)` — word-based
- `estimate_tokens_combined(text)` — average

---

## G. Schema

### G.1 Plan

```python
@dataclass
class Plan:
    objective: str            # restate user goal
    project_id: str           # from registry
    assumptions: list[str]    # made by planner
    steps: list[PlanStep]
    verification: list[VerificationCriterion]
    risks: list[str]
    estimated_complexity: PlanComplexity
    notes: str
```

### G.2 PlanStep

```python
@dataclass
class PlanStep:
    step_id: str                       # "step-1"
    title: str
    description: str
    step_type: str                     # "shell" | "python" | "inspect"
    dependencies: list[str]            # step_ids
    command: str
    arguments: list[str]
    expected_result: str
    verify_contains: list[str]         # run-time checks
    verify_not_contains: list[str]
    expect_exit_code: int
```

### G.3 VerificationCriterion

```python
@dataclass
class VerificationCriterion:
    description: str
    method: str                        # "manual" | "typecheck" | "test" | "diff" | "inspect"
    command: str                       # optional
    args: list[str]
    expect_exit_code: int
    verify_contains: list[str]
```

### G.4 Stable JSON

`to_dict()` / `from_dict()` / `to_json()` / `from_json()` roundtrip cleanly.

---

## H. Validation

`PlanValidator` rejects:

| Code | Trigger |
|---|---|
| `EMPTY_OBJECTIVE` | objective is empty |
| `INVALID_PROJECT_ID` | project not in registry |
| `NO_STEPS` | plan has no steps |
| `MISSING_STEP_ID` / `INVALID_STEP_ID` / `DUPLICATE_STEP_ID` | step id issues |
| `MISSING_STEP_TITLE` | step has no title |
| `INVALID_STEP_TYPE` | step_type not in {shell, python, inspect} |
| `MISSING_COMMAND` | shell step without command |
| `MISSING_MODULE` | python step without module |
| `UNKNOWN_DEPENDENCY` | dependency on non-existent step |
| `SELF_DEPENDENCY` | step depends on itself |
| `CYCLIC_DEPENDENCIES` | graph has cycles |
| `FORBIDDEN_COMMAND` | command in forbidden set (rm, sudo, …) |
| `UNSAFE_SHELL_PATTERN` | contains `&&`, `|`, `;`, etc. |
| `UNSAFE_PYTHON_PATTERN` | contains `eval(`, `exec(`, etc. |
| `PARSE_ERROR` | LLM output was not valid JSON |
| `DESERIALIZE_ERROR` | JSON did not match schema |

Warnings (non-blocking):
- `SHORT_OBJECTIVE`
- `NO_VERIFICATION_CRITERIA`
- `EMPTY_VERIFICATION_DESC`
- `UNKNOWN_VERIFICATION_METHOD`

---

## I. Security model

### I.1 Hard boundaries

1. **The LLM never sees the LLM API key when running with the
   MockProvider.** MockProvider does not require keys.
2. **No `eval()`, no `exec()`, no dynamic compilation anywhere** in
   `core/planner/`. Verified by inspection.
3. **No `shell=True`** in any subprocess call.
4. **No curl / wget / ssh / sudo / chmod / chown / rm / kill** in plans.
5. **Project IDs are validated against the registry** — plans cannot
   be generated for unknown projects.
6. **`--save` does NOT execute** — it only persists a Task to disk.

### I.2 Forbidden patterns

- Shell metacharacters: `&&`, `||`, `;`, `|`, `>`, `>>`, `<`, `$(`, `"`
- Dangerous commands: `rm`, `rmdir`, `dd`, `mkfs`, `fdisk`, `shutdown`,
  `reboot`, `kill`, `killall`, `pkill`, `sudo`, `chmod`, `chown`,
  `iptables`, `firewall-cmd`, `systemctl`, `service`, `useradd`,
  `userdel`, `mount`, `umount`, `crontab`, `apt`, `apt-get`, `yum`,
  `dnf`, `pacman`, `brew`, `pip`, `npm`, `pnpm`, `curl`, `wget`,
  `scp`, `ssh`, `nc`, `netcat`
- Python patterns: `eval(`, `exec(`, `__import__`, `compile(`,
  `globals()`, `locals()`

---

## J. Test results

### J.1 Counts

| Suite | Tests | Pass |
|---|---|---|
| `test_project_manager.py` | 28 | 28 ✅ |
| `test_task_engine.py` | 39 | 39 ✅ |
| `test_planner.py` | 53 | 53 ✅ |
| **Total** | **120** | **120 ✅** |

```
$ python3 -m unittest tests.test_task_engine tests.test_project_manager tests.test_planner
...
Ran 120 tests in 0.298s

OK
```

### J.2 Planner test coverage

| Class | Tests | Covers |
|---|---|---|
| `TestSchema` | 5 | Plan/PlanStep/VerificationCriterion roundtrip, summary, step_id validation |
| `TestContextBuilder` | 7 | token estimator, budget enforcement, build_context, None handling |
| `TestPromptBuilder` | 7 | system prompt, user prompt, full tuple, fence stripping, parse |
| `TestValidator` | 14 | valid plan passes, empty/unknown/duplicate/cyclic/dep/cmd/injection/eval rejected |
| `TestMockProvider` | 4 | valid JSON output, call count, response override, error_on_call |
| `TestPlanner` | 8 | happy path, unknown project, invalid LLM output, malformed JSON, stats, provider name, factory, config |
| `TestPlanToTask` | 4 | step mapping, type mapping, verification hints, status PENDING |
| `TestCLICLI` | 2 | module imports, print_plan runs |

---

## K. Manual test results

### K.1 Plan generation (MockProvider)

```
$ python3 -m core.planner.cli plan cuu-gioi "Audit Runtime Console"
Provider : mock
Model    : gpt-4o
Project  : Cửu Giới (Nine Realms)

▶ Đang lên kế hoạch: 'Audit Runtime Console'

Context:
  Tổng chars : 14013
  Tokens ≈    : 3133 (APPROXIMATE)
  Docs        : project_metadata, AGENT.md, source-of-truth.md

Objective : Plan based on user request
Dự án    : cuu-gioi
Complexity: simple
Tổng bước: 2

Giả định:
  • Assuming project context provides sufficient detail ...
  • Assuming the user has access to the project's source files.

Các bước:
  1. [inspect] Inspect project structure
  2. [shell] List relevant source files (deps: step-1)

Xác minh:
  • Project structure is accessible and inspect step returned valid metadata [inspect]
  • Shell step completed without errors [diff]

Rủi ro:
  ⚠ Assumes project root is accessible from the execution environment.
```

### K.2 Plan → Task → Inspect

```
$ python3 -m core.planner.cli plan cuu-gioi "Inspect frontend" --save
✅ Đã lưu thành task: TASK-0002
   Tiếp theo: python -m core.tasks.cli run TASK-0002
```

```
$ python3 -m core.tasks.cli inspect TASK-0002
Nhiệm vụ : TASK-0002
Dự án     : cuu-gioi
Tiêu đề  : Plan based on user request
Trạng thái: PENDING
Tổng bước : 2
```

### K.3 Run the generated task (separate step)

```
$ python3 -m core.tasks.cli run TASK-0002
▶ Chạy TASK-0002
Trạng thái: COMPLETED
Kết quả   : 2 passed, 0 failed, 0 pending
Xác minh  : ✅ ĐÃ XÁC MINH
```

### K.4 No automatic execution

The Planner does NOT auto-execute. Confirmed:
- `plan <id> <objective>` (no `--save`): no task created
- `plan <id> <objective> --save`: only writes JSON, does not run
- `inspect TASK-XXXX` is still the way to check a generated task
- `run TASK-XXXX` is still required to actually execute

---

## L. Context/token statistics

| Metric | Value |
|---|---|
| Documents considered | project_metadata, AGENT.md, ARCHITECTURE.md, source-of-truth.md |
| Documents included (default budget 4000 tokens) | project_metadata, AGENT.md, source-of-truth.md (3 of 4) |
| Documents excluded | ARCHITECTURE.md (would have exceeded budget) |
| Total chars in context | 14,013 |
| Approx tokens | 3,133 |
| Token estimator | `(chars / 4 + words / 0.75) / 2` |
| Label | APPROXIMATE |

(ARCHITECTURE.md is excluded because it alone is 20KB. The user can
raise the budget with `max_context_tokens=8000` if needed.)

---

## M. Real LLM test result

> ⚠️ **Skipped**: no `AGENTCORE_PLANNER_API_KEY` was set in this
> environment, and no local LLM server was running on
> `localhost:11434`.

The `MockPlannerProvider` was used instead. To enable a real provider:

```bash
export AGENTCORE_PLANNER_PROVIDER=openrouter
export AGENTCORE_PLANNER_API_KEY=sk-or-v1-...
export AGENTCORE_PLANNER_MODEL=openai/gpt-4o

# Or for local:
export AGENTCORE_PLANNER_PROVIDER=local
export AGENTCORE_PLANNER_BASE_URL=http://localhost:11434
export AGENTCORE_PLANNER_MODEL=llama3
```

---

## N. Cuu-Gioi integrity check

```
$ ls -la /root/.nanobot/workspace/Cuu-Gioi/AGENT.md
       /root/.nanobot/workspace/Cuu-Gioi/ARCHITECTURE.md
       /root/.nanobot/workspace/Cuu-Gioi/docs/architecture/source-of-truth.md
-rw-r--r-- 1 root root  9008 ... AGENT.md
-rw-r--r-- 1 root root 20268 ... ARCHITECTURE.md
-rw-r--r-- 1 root root  4904 ... source-of-truth.md
```

**No Cuu-Gioi files were modified by the Planner.** The Planner only
reads project documentation via the existing ProjectManager.

---

## O. Known limitations

1. **No LLM call in tests.** `MockPlannerProvider` returns templated
   plans. Real LLM quality is unknown until a real provider is
   configured.
2. **No streaming.** Each planner call is a single request/response.
3. **No retry / re-prompt.** If the LLM produces invalid JSON, the
   user must re-run the CLI.
4. **Approximate token count.** Replace with `tiktoken` for exact
   counts.
5. **Context truncation is character-based.** If a single document
   exceeds the budget, it is dropped entirely. A future version
   should truncate rather than drop.
6. **OpenRouter / Local providers are simple.** No streaming, no
   tool-calling, no JSON-mode negotiation. The provider trusts that
   the prompt yields JSON.
7. **No automatic plan execution.** User must explicitly run.
8. **No plan-to-plan comparison / diff.**
9. **No multi-objective plans.** One plan = one objective = one task.
10. **Cycle detection is O(V+E).** Acceptable for ≤ 100 steps.

---

## P. Next recommended step

> **Plan re-prompting loop (v0.3)**: when validation fails, automatically
> re-prompt the LLM with the validation errors as feedback. Cap retries
> at 3. This dramatically improves real-world LLM reliability.

Or, alternatively:

> **Persistent plan cache**: store every generated plan as
> `plans/PLAN-NNNN.json` so plans can be re-inspected, re-validated,
> and compared over time without re-running the LLM.

Both are small, additive changes. Neither breaks the LLM/Runner
boundary. Neither makes the LLM execute anything.

---

## Q. Final summary

| Item | Status |
|---|---|
| Plan / PlanStep / VerificationCriterion schema | ✅ |
| Token-aware context builder | ✅ |
| Deterministic prompt builder | ✅ |
| Provider-agnostic LLM interface | ✅ (OpenRouter + Local + Mock) |
| Strict validation (structural + safety) | ✅ |
| Plan → Task conversion | ✅ |
| CLI (`plan`, `validate`, `--save`) | ✅ |
| 53 planner tests + 67 existing tests = 120 tests | ✅ |
| No LLM required for tests | ✅ (MockProvider) |
| No eval(), no exec(), no shell=True | ✅ |
| Cuu-Gioi untouched | ✅ |
| No commit, no push | ✅ |

**Files created**: `core/planner/{__init__,schema,context,prompt,validator,planner,cli}.py`, `tests/test_planner.py`, `PLANNER_REPORT.md`.

**Files modified**: none.

**Dependencies added**: none.

---

> LLM-generated plans are not execution results.
> Verification remains authoritative.
> The LLM plans. The Runner executes. The Verifier decides.
