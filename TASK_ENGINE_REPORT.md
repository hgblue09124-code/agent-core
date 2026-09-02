# TASK_ENGINE_REPORT.md

> **Scope**: Task Engine v0.1 — upgrade agent-core from
> "project-aware kernel" to "project-aware task management kernel".
> Deterministic task creation, persistence, execution, and verification
> against registered projects.
>
> **Status**: experimental. v0.1 is **deterministic infrastructure, not
> an autonomous agent**.

---

## TL;DR

> **Task Engine v0.1 is deterministic infrastructure, not an autonomous
> agent.** It can create, persist, inspect, execute, and verify tasks
> that consist of predefined shell / Python / inspect commands. It does
> **not** make intelligent decisions.

```
TASK → LOAD PROJECT → LOAD CONTEXT → EXECUTE PREDEFINED STEPS →
CAPTURE OUTPUT → VERIFY → SAVE RESULT
```

It uses **only the Python standard library** (`subprocess`, `json`,
`pathlib`, `dataclasses`, `unittest`, `datetime`). **No LLM, no vector
DB, no RAG, no eval(), no multi-agent loop, no heavy deps.**

---

## A. Before state

After PROJECT_INTEGRATION_REPORT v0.1:

```
agent-core/
├── core/projects/        ← project registry + context loader
│   ├── __init__.py
│   ├── manager.py
│   ├── context.py
│   └── cli.py
├── projects/registry.json
├── tests/test_project_manager.py
└── PROJECT_INTEGRATION_REPORT.md
```

**What it could do**: list projects, look up metadata, read project
docs.
**What it could NOT do**: create tasks, execute anything, persist
results, verify anything.

---

## B. After state

```
agent-core/
├── core/projects/        ← unchanged
│   ├── __init__.py
│   ├── manager.py
│   ├── context.py
│   └── cli.py
├── core/tasks/           ← NEW: Task Engine
│   ├── __init__.py
│   ├── schema.py         ← Task, TaskStep, StepResult, VerificationResult, enums
│   ├── manager.py        ← TaskManager (CRUD + JSON persistence)
│   ├── context.py        ← TaskContext (Task + Project docs)
│   ├── runner.py         ← TaskRunner (deterministic executor + verifier)
│   └── cli.py            ← CLI: create | add-step | list | inspect | run | delete
├── projects/registry.json
├── tasks/                ← NEW
│   ├── index.json        ← {"next_id": N, "tasks": {…}}
│   └── task-NNNN.json    ← one per task (atomic write)
├── tests/
│   ├── test_project_manager.py    ← (unchanged, 28 tests)
│   └── test_task_engine.py        ← NEW (39 tests)
└── TASK_ENGINE_REPORT.md          ← this report
```

---

## C. Architecture

```
                 ┌──────────────────────────┐
                 │  projects/registry.json  │
                 │  (cuu-gioi registered)   │
                 └────────────┬─────────────┘
                              │
                              ▼
       ┌──────────────────────────────────────────────┐
       │  core/projects/manager.py — ProjectManager   │
       │  ────────────────────────────────            │
       │  register / get / list / validate / locate   │
       └────────────────────┬─────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
   ProjectContext                            (more)
   (load_project_context)
        │
        ▼
   ┌────────────────────────────────────┐
   │  core/tasks/schema.py              │  ← Task, TaskStep, StepResult,
   │  • TaskStatus enum                 │     VerificationResult, StepType
   │  • StepType enum                   │     + serialization (to_dict/from_dict)
   │  • Task dataclass + JSON           │
   └────────────┬───────────────────────┘
                │
       ┌────────┴────────┐
       ▼                 ▼
   TaskManager       TaskContext
   (CRUD/JSON)       (Task + Project docs)
       │
       ▼
   ┌────────────────────────────────────┐
   │  core/tasks/runner.py — TaskRunner │
   │  ────────────────────────────      │
   │  PENDING → RUNNING → step×N →     │
   │  COMPLETED|FAILED + Verification   │
   └────────────┬───────────────────────┘
                │
                ▼
   ┌────────────────────────────────────┐
   │  core/tasks/cli.py                │
   │  python -m core.tasks.cli {…}      │
   └────────────────────────────────────┘
```

---

## D. Task lifecycle

```
   ┌─────────┐  run()    ┌─────────┐  all steps  ┌──────────┐
   │ PENDING │ ────────► │ RUNNING │ ──passed──► │COMPLETED │
   └─────────┘           └────┬────┘             └──────────┘
        │                     │ step fails          │
        │                     ▼                     ▼
        │ CANCELLED      ┌─────────┐         ┌────────────┐
        └──────────────► │ FAILED  │         │ VERIFIED?  │
                        └─────────┘         │ (yes/no)   │
                                            └────────────┘
```

- `PENDING` → `RUNNING`: only valid from `PENDING`
- `RUNNING` → `COMPLETED | FAILED | CANCELLED`
- Terminal states (`COMPLETED`, `FAILED`, `CANCELLED`) cannot transition further
- **COMPLETED ≠ VERIFIED** (a task can be COMPLETED with
  `verification.verified = False`)

---

## E. Persistence design

- **One file per task**: `tasks/task-NNNN.json`
- **Index file**: `tasks/index.json` (atomic write via tmp + replace)
- **Atomic writes**: every save goes through a `.tmp` file, then
  `os.replace()` for crash safety
- **Stable serialization**: dataclass → `to_dict()` → JSON
- **Timestamps**: ISO 8601 (UTC, seconds precision)
- **IDs**: `TASK-0001`, `TASK-0002`, … (deterministic, readable)
- **No database**, no locking, single-process

Example `task-0001.json`:

```json
{
  "task_id": "TASK-0001",
  "project_id": "cuu-gioi",
  "title": "Audit cuu-gioi structure",
  "description": "...",
  "status": "COMPLETED",
  "created_at": "2026-09-02T15:43:05+00:00",
  "started_at": "2026-09-02T15:43:06+00:00",
  "completed_at": "2026-09-02T15:43:06+00:00",
  "steps": [
    {
      "type": "inspect",
      "title": "Inspect cuu-gioi project",
      "command": "", "args": [], "module": "", "py_args": [],
      "cwd": "", "inspect_project_id": "",
      "expect_exit_code": 0, "verify_contains": [], "verify_not_contains": [],
      "result": {
        "stdout": "Project: Cửu Giới (Nine Realms)\n...",
        "stderr": "",
        "exit_code": 0,
        "duration_seconds": 0.0,
        "started_at": "...",
        "finished_at": "..."
      }
    }
  ],
  "result": "2 passed, 0 failed, 0 pending",
  "verification": {
    "verified": true,
    "checks_performed": ["Bước 1 …: exit=0", "Bước 2 …: exit=0", "Project context loaded"],
    "failures": [],
    "verified_at": "...",
    "all_steps_passed": true,
    "failed_step_index": -1
  },
  "error": null
}
```

---

## F. Runner design

```
TASK
  │
  ▼
Validate (can_run? = status==PENDING)
  │
  ▼
mark_running() + save
  │
  ▼
load_task_context(task)  ──connects to──► ProjectManager + ProjectContext
  │
  ▼
for each TaskStep (sequential):
  │
  ├─ SHELL   → subprocess.run([cmd, arg1, arg2, …])  [no shell=True]
  ├─ PYTHON  → subprocess.run([python_exe, -m, module, …py_args])
  └─ INSPECT → ProjectManager lookup → returns project summary as stdout
  │
  ▼
Capture: stdout, stderr, exit_code, duration_seconds, started_at, finished_at
  │
  ▼
Save partial result after each step
  │
  ▼
If any step exit_code != expect_exit_code: mark FAILED, stop
Else: all passed → mark COMPLETED → run verification → save
```

### F.1 Safety rules

- **No `eval()`** anywhere. Verified by reading the source.
- **No dynamic Python generation**. Only predefined step types.
- **`subprocess` uses explicit args** (no `shell=True`).
- **Timeout per step** (default 60s).
- **Failed commands surface** as `exit_code != 0`, with stdout/stderr
  captured.
- **No silent exception swallowing**: every exception is recorded in
  the step's `result.error` and bubbles up to mark the task FAILED.
- **Project validation**: unknown project → task FAILED before any
  step runs.

### F.2 Verification model

After all steps pass, `runner._verify()` runs:

1. **Per-step checks**:
   - `result.exit_code == step.expect_exit_code`
   - Every string in `verify_contains` is present in `result.stdout`
   - No string in `verify_not_contains` is present in `result.stdout`
2. **Project-context check**: `TaskContext.project_exists == True`
3. Result recorded in `task.verification`:
   - `verified: bool`
   - `checks_performed: list[str]`
   - `failures: list[str]`
   - `verified_at: ISO 8601`
   - `all_steps_passed: bool`
   - `failed_step_index: int`

`status == COMPLETED` does **not** imply
`verification.verified == True`. They are independent.

---

## G. Test results

### G.1 Counts

| Suite | Tests | Pass |
|---|---|---|
| `test_project_manager.py` | 28 | 28 ✅ |
| `test_task_engine.py` | 39 | 39 ✅ |
| **Total** | **67** | **67 ✅** |

```
$ python3 -m unittest tests.test_task_engine tests.test_project_manager -v
...
Ran 67 tests in 0.297s
OK
```

### G.2 Coverage by class

`test_task_engine.py` (39 tests):

| Class | Tests | Covers |
|---|---|---|
| `TestSchema` | 13 | TaskID format, status transitions, dataclass roundtrip, mark_* methods, step_summary, total_duration |
| `TestTaskManager` | 11 | create, persist, get, list (filter by project/status), update, delete, count |
| `TestTaskContext` | 2 | cuu-gioi load, missing project graceful fail |
| `TestTaskRunner` | 11 | shell success/fail, python step, inspect step, verification pass/fail, duration capture, re-run guard, unknown project, sequential multi-step, stop on first fail |
| `TestCLICreate` | 2 | module imports |

### G.3 CLI test results

```
$ python3 -m core.tasks.cli list
Không có nhiệm vụ nào.

$ python3 -m core.tasks.cli create cuu-gioi "Audit cuu-gioi structure" --description "Liệt kê docs, kiểm tra AGENT.md"
✅ Đã tạo: TASK-0001

$ python3 -m core.tasks.cli add-step TASK-0001 inspect "Inspect cuu-gioi project"
✅ Đã thêm bước vào TASK-0001

$ python3 -m core.tasks.cli add-step TASK-0001 shell "Echo hello" --cmd "echo" --arg "hello-from-task"
✅ Đã thêm bước vào TASK-0001

$ python3 -m core.tasks.cli run TASK-0001
▶ Chạy TASK-0001: Audit cuu-gioi structure

Nhiệm vụ : TASK-0001
Trạng thái: COMPLETED
Tổng bước : 2
Kết quả   : 2 passed, 0 failed, 0 pending
Xác minh  : ✅ ĐÃ XÁC MINH
  • Bước 1 [Inspect cuu-gioi project]: exit=0
  • Bước 2 [Echo hello]: exit=0
  • Project context loaded

✅ HOÀN THÀNH VÀ ĐÃ XÁC MINH
```

---

## H. Cuu-Gioi untouched

Verified — no Cuu-Gioi source file was modified:

```
$ ls -la /root/.nanobot/workspace/Cuu-Gioi/AGENT.md \
         /root/.nanobot/workspace/Cuu-Gioi/ARCHITECTURE.md \
         /root/.nanobot/workspace/Cuu-Gioi/docs/architecture/source-of-truth.md

-rw-r--r-- 1 root root  9008 Sep  2 22:00 AGENT.md
-rw-r--r-- 1 root root 20268 Sep  2 22:00 ARCHITECTURE.md
-rw-r--r-- 1 root root  4904 Sep  2 22:01 docs/architecture/source-of-truth.md
```

`Sep 2 22:00–22:01` is the timestamp from the previous
`PROJECT_INTEGRATION_REPORT` work. No new modifications.

The Task Engine only **read** these files via the existing
`ProjectManager` + `ProjectContext` interface. It did not touch
gameplay, application code, or any other Cuu-Gioi file.

---

## I. Known limitations

1. **No intelligence.** The runner executes predefined steps exactly as
   written. It does not decide what to do next.
2. **No LLM.** No generation, no embeddings, no planning.
3. **No retry / loop.** A failing step marks the task FAILED. The next
   step is not executed. There is no automatic retry.
4. **No parallelism.** Steps run sequentially.
5. **No cancellation propagation.** A long-running `subprocess` cannot
   be killed mid-step from outside the process.
6. **No file watching.** Tasks are loaded on demand.
7. **Single-process.** No locking, no concurrency.
8. **No timestamps/result caching.** Every `load_context` re-reads all
   three project docs.
9. **No streaming output.** Each step's stdout/stderr is captured
   fully, then truncated to 5 lines for display.
10. **CLI is positional, not subcommand-strict.** `add-step`'s flag
    parsing is custom. A future version should use `argparse`.

---

## J. Future evolution (not implemented)

> Documented here, not built. The Task Engine v0.1 is the foundation;
> these are the next layers.

```
Task
  ↓
LLM Planner              ← (future) decomposes intent into steps
  ↓
Tool Execution           ← (v0.1) deterministic runner
  ↓
Observation              ← (future) parses step results semantically
  ↓
Verification             ← (v0.1) ✓
  ↓
Retry                    ← (future) on verification failure
  ↓
Result                   ← (v0.1) ✓
```

Layer-by-layer plan:

1. **v0.1 (this PR)**: deterministic runner + verification. ✓
2. **v0.2 (suggested)**: `--arg`/`--py-arg` becomes argparse; add
   `cancel` for RUNNING tasks; add per-step retry policy.
3. **v0.3 (suggested)**: simple "intent → steps" plan generator driven
   by `ProjectContext` (no LLM; uses templates).
4. **v0.4 (suggested)**: pluggable LLM planner behind a flag; keep
   deterministic runner as the executor regardless.
5. **v0.5+ (deferred)**: parallel steps, observation parsing,
   self-correction loop.

---

## K. Final summary

| Item | Status |
|---|---|
| Task schema with stable JSON serialization | ✅ |
| Task manager with atomic JSON persistence | ✅ |
| Task context (Task + Project docs) | ✅ |
| Deterministic runner (shell / python / inspect) | ✅ |
| Explicit verification (COMPLETED ≠ VERIFIED) | ✅ |
| CLI (create / add-step / list / inspect / run / delete) | ✅ |
| 67 unit tests passing | ✅ |
| Existing 28 tests still passing | ✅ |
| No LLM, no eval(), stdlib only | ✅ |
| Cuu-Gioi untouched | ✅ |
| No commit, no push | ✅ |

**Files created**:

- `core/tasks/__init__.py`
- `core/tasks/schema.py`
- `core/tasks/manager.py`
- `core/tasks/context.py`
- `core/tasks/runner.py`
- `core/tasks/cli.py`
- `tests/test_task_engine.py`
- `TASK_ENGINE_REPORT.md`

**Files modified**: none.
**Files deleted**: none.
**Dependencies added**: none.

---

> Task Engine v0.1 is deterministic infrastructure, not an autonomous
> agent. It is the **bottom rung of a ladder**, designed to be climbed
> one rung at a time. The next rungs (LLM planning, observation
> parsing, retry) are documented but not built.
