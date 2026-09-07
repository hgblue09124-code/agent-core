# BIG UPDATE — Real Local-First Personal Agent

**Status:** Specification (implementation freeze until this document is accepted)  
**Date:** 2026-09-07  
**Baseline:** `master` @ `b86e51663a448978f86c0bca551cc5dddcd6b3a3`  
**Related:** `PROJECT_HEALTH_AUDIT.md`, `docs/v0.3/AGENT_CORE_V0.3_BLUEPRINT.md`, `AGENTS.md`, `docs/user-ui.md`

This document is the implementation contract for the next product increment. It is documentation only. It does not change Runtime, LLM, iOS, tests, or architecture by existing.

---

## Spirit

```
REAL execution  >  architecture theater  >  UI polish
```

A Personal Agent is not a chat skin, not a phase legend, and not a second state machine. It is a user message that actually reaches a loaded language model, produces a real decision, executes real actions under policy, writes real memory, and returns a truthful result — or a truthful failure.

If the system cannot do that, it must say so. It must never look successful by falling back to mock, echo, or template copy.

---

## 1. Objective

Close the gap named by the Project Health Audit: **structural/contract completeness versus the default real-world execution path**.

Today the repository has a real Runtime, real Memory stores, a Native SwiftUI User Workspace, and implemented LLM providers. The default production path still classifies by keyword and finishes generic goals with deterministic / mock echo. Users can believe the Agent reasoned when it did not.

This Big Update makes one thing true:

> On Native iOS, a user types in Composer, the existing AgentRuntime runs, a **local LLM is the default reasoning engine**, actions and memory actually happen, Orb / progress / result reflect that Runtime, and failure is honest.

External cloud providers remain **Option 2**, never the silent default, never the silent fallback.

---

## 2. Current Baseline (facts, not aspirations)

These are constraints, not redesign prompts.

| Layer | What exists | Default today |
| --- | --- | --- |
| iOS product | Native SwiftUI User Workspace, Orb, Composer, `WorkspacePresentation` | Presentation maps `AgentRuntimeState` / `AgentRunResult` |
| Swift Runtime | `AgentRuntime`, `AgentRuntimeState`, `AgentRuntimeStore`, `AgentRuntimeEvent`, reducer | Real lifecycle, checkpoints, events |
| LLM contract | `LanguageModelProvider`, `RoutingLanguageModelProvider`, catalog/download | Settings default is On-device, but on-device generate still requires a local OpenAI-compatible sidecar; missing sidecar / weights do not fail closed |
| Cheap path | remember / forget / status | Real Memory writes; this path is legitimate |
| Generic goals | `LocalDeterministicPlanner` / `mock.echo` | Template success: *“Successfully executed goal …”* |
| Memory | `LocalMemoryStore`, `LocalVaultStore` | Real file-backed read/write |
| Python core | `AgentLoopController`, `AgentRuntime`, planner/LLM providers | `AGENTCORE_PLANNER_PROVIDER` defaults to `"mock"` |
| Dual runtime | Swift Runtime on device; Python Runtime behind console API | Product surface for this update is Native iOS |

Do not treat “providers exist” as “inference is the default path.”

---

## 3. Target Architecture

Reuse the systems that already own these jobs. Wire them. Do not replace them.

```
Composer (single entry)
        │
        ▼
LocalAgentService                    existing iOS API boundary
        │
        ▼
AgentRuntime.submit                  canonical Runtime (Swift)
        │
        ├─ cheap deterministic?      remember / forget / status only
        │         │
        │         └─ Memory / Vault  real write, then Result
        │
        ▼
LanguageModelProvider                DEFAULT = Local LLM
        │                            OPTION 2 = external provider (explicit)
        ▼
structured Decision                  Runtime-validated, never raw text as command
        │
        ▼
Policy / authorize                   Runtime owns permission, not the model
        │
        ▼
Actions                              existing capability / tool path
        │
        ▼
Verify                               independent of “the model said it worked”
        │
        ▼
Remember                             durable facts only
        │
        ▼
AgentRunResult + Runtime events
        │
        ▼
WorkspacePresentation                thin adapter, no second state
        │
        ▼
Orb · Progress · Conversation · Result · Actions
```

Ownership stays exactly where v0.3 already put it:

| Concern | Owner | Must not own it |
| --- | --- | --- |
| Agent state, phase, objective lifecycle | `AgentRuntime` | UI, LLM, presentation adapter |
| Reasoning text / structured proposal | `LanguageModelProvider` | Runtime FSM, policy, memory schema |
| Provider selection | `RoutingLanguageModelProvider` + Settings | Agent loop internals |
| Durable memory | `LocalMemoryStore` / `LocalVaultStore` | Chat transcript dump |
| Authorization | existing policy / Runtime | Model output |
| Presentation copy | `WorkspacePresentation` | A new view-model Runtime |
| Orb / progress / result | SwiftUI bound to `AgentRuntimeState` | Timers, fake presence, demo scripts |

Python `core/` remains the kernel for console / CLI. This Big Update does **not** merge the dual runtimes and does **not** invent a bridge Runtime. iOS continues to execute on-device through the existing Swift `AgentRuntime`.

---

## 4. Requirements

The following eighteen items are the agreed Big Update. They are mandatory.

### R1. Local LLM = DEFAULT

Production default reasoning backend is **local**:

- Settings default remains `LLMBackend.onDevice` with `privacyMode = true`.
- A user who has not chosen a cloud provider must hit a **loaded local model** for any goal that needs reasoning.
- “Local” means one of: on-device GGUF actually used for generate/stream, or a user-configured local server (Ollama / llama.cpp) that is **live**. Catalog install without inference is not “local LLM ready.”
- Default must not be Mock, OpenAI, OpenRouter, or xAI.

### R2. External Provider = OPTION 2

OpenAI / OpenRouter / xAI / custom cloud endpoints are opt-in:

- User must explicitly select them in Settings.
- Privacy mode continues to block cloud backends.
- Local failure must **not** silently route to cloud.
- Cloud failure must **not** silently route to mock.

### R3. Canonical Agent Execution Path

There is one production execution path on iOS:

```
Composer
  → LocalAgentService
  → AgentRuntime.submit
  → (cheap deterministic OR LanguageModelProvider)
  → Decision
  → Policy
  → Act
  → Verify
  → Remember
  → AgentRunResult
```

No parallel “chat brain.” No second planner. No UI-owned execution.

Cheap deterministic is allowed **only** for operations that are themselves real and complete without a model (remember / forget / status). It is not a generic-goal substitute.

### R4. Real Chat → LLM → Reasoning → Actions → Memory → Result

For a non-cheap user message:

1. Chat text enters Runtime as an event / goal.
2. Runtime retrieves targeted memory and current state.
3. `LanguageModelProvider.generate` or `.stream` is actually invoked.
4. Runtime validates a Decision (intent, action, arguments, risk).
5. Approved actions execute through existing action interfaces.
6. Verification confirms outcome independently of model text.
7. Useful facts persist through existing Memory APIs.
8. Result shown to the user is derived from that run, not a stock sentence.

A run that skips steps 3–7 for a generic goal is a spec violation.

### R5. Real Personal Agent UX on Native SwiftUI

The product surface is Native iOS, not Web, not WebView.

Home / User Workspace must present, in this information architecture:

```
Conversation
Agent Status
Work Progress
Result
Actions
Composer
```

This is an evolution of the existing Your Agent / Orb / Composer workspace (`HomeView`, `WorkspacePresentation`). It is not a new app shell.

Web Preview remains a UX reference only (`AGENTS.md`).

### R6. Orb reflects real Runtime state

`AgentOrbView` must bind to `AgentRuntimeState.status` (already derived from phase):

| Runtime phase | Orb |
| --- | --- |
| `idle` / `completed` / `failed` / `cancelled` | ready, not spinning |
| `thinking` / `planning` | thinking, spinning if motion allowed |
| `executing` | running, spinning if motion allowed |

Forbidden:

- orb animation driven by send-button timers
- presence set by the View
- “thinking” while Runtime is idle
- “ready” while Runtime is executing

### R7. Composer is the single entry point

Composer on the User Workspace is the only user-facing submit for agent work.

- Submit → `LocalAgentService` / `AgentRuntime.submit`.
- Do not add a second chat composer, a competing Execute-tab brain, or a web-shaped input that bypasses Runtime.
- Developer Live Console stays behind its existing explicit toggle and is not the product entry.

### R8. Real execution progress / events

Progress, steps, and activity come from existing Runtime events and `AgentRuntimeState.steps` / `.progress`.

- UI listens to `AgentRuntimeStore` / existing event stream.
- Step titles are real actions or verified plan steps, not cosmetic placeholders created by the View.
- Progress is not interpolated independently of Runtime.

### R9. Answer vs Work Performed

The product must distinguish:

| Kind | Meaning | UI |
| --- | --- | --- |
| **Answer** | Model / Runtime language responding to the user | Conversation bubble |
| **Work performed** | Actions executed, memory written, verifications | Progress / Result / Activity |

Rules:

- A conversational answer with zero actions is an Answer, not “task completed with work.”
- Work without a useful Answer still shows Work Performed.
- Template echo (`ECHO: …`, “Successfully executed goal …”, mock planner text) must never be labeled as Work Performed in production.
- Result card copy comes from `AgentRunResult` / verified outcomes via `WorkspacePresentation`.

### R10. Real Memory integration

Memory is already real. This update must **use** it on the reasoning path:

- Before LLM calls: targeted retrieve (`LocalMemoryStore` / vault), not full transcript dump.
- After verified success: persist only durable useful results (facts, preferences, decisions).
- remember / forget remain first-class real operations on the cheap path.
- Do not invent a second memory store, embedding index, or transcript archive as the source of truth.

### R11. Truthful failure semantics

Production fails closed. See §11.

If the local model is not loaded, the sidecar is down, the provider is unauthorized, policy denies, or verification fails, the user sees a real error state. The Agent does not complete with a demo answer.

### R12. End-to-end behavioral testing

Tests must prove behavior, not only contracts. See §12.

Mock providers remain test-only, injected explicitly.

### R13. iOS validation

Agent verification for this product:

- Xcode build PASS for `AgentCoreIOS`.
- Relevant XCTest PASS (Runtime, LLM routing, workspace presentation, memory).
- Unsigned IPA packaging is **owner acceptance**, not the agent’s default job (`AGENTS.md` §8).

### R14. No mock / deterministic fallback in production

In production / default app runtime:

- `MockLanguageModelProvider` is not the active backend.
- `LocalDeterministicPlanner` is not the generic-goal planner.
- `mock.echo` is not the generic-goal action.
- Missing LLM ≠ “run the cheap loop anyway and report success.”

Allowed without a model: remember / forget / status, and explicit operator/debug flags that cannot ship as default.

### R15. Do not create a second Runtime / EventBus / Planner / Memory / state system

Reuse:

- `AgentRuntime`, `AgentRuntimeState`, `AgentRuntimeStore`, `AgentRuntimeEvent`, `AgentRuntimeReducer`
- `LanguageModelProvider` / `RoutingLanguageModelProvider`
- `LocalMemoryStore`, `LocalVaultStore`, `LocalCheckpointStore`
- `WorkspacePresentation`, `HomeView`, `AgentOrbView`, Composer
- existing policy / capability types

Forbidden: a new orchestrator, a new event bus, a new planner protocol, a new memory JSON schema, a new “agent state” owned by SwiftUI, or a Python-in-process rewrite of the iOS Runtime.

### R16. No broad rewrite

Scope is wiring + truthful defaults + tests + the smallest iOS binding fixes required for R1–R15.

Out of scope: new visual language, tab IA overhaul, dual-runtime merge, new model catalog families, kernel/policy redesign, constitution rewrite.

### R17. Validation Gate

Implementation PRs cannot merge without the gate in §13 of this document.

### R18. Git / PR requirements for the Big Update implementation

When implementation happens (not this documentation commit):

- One focused PR (or a short stacked series with one concern each).
- PR contains: relevant implementation, relevant tests, Xcode build result, concise summary.
- No unrelated refactors.
- Description must state: default backend, what happens when the model is missing, and which existing types were reused.
- Do not mix docs-only and implementation in a way that hides Runtime changes.

This file’s introduction onto the repository is documentation-only and must not open an implementation PR.

---

## 5. Non-goals

The Big Update is **not**:

- A new Agent architecture, v0.4 Runtime, or replacement FSM.
- Merging Swift and Python runtimes.
- On-device llama.cpp Swift bindings as a mandatory first slice if a real local OpenAI-compatible generate path already works — unless that is the only way to satisfy R1 without a sidecar lie. (If generate still requires a sidecar, the UI and Runtime must say “local server required / not loaded,” never “On-device ready” with mock completion.)
- Cloud-first intelligence.
- Vector DB / embeddings / RAG platform.
- Multi-agent, swarm, or background 24/7 browsing.
- Web / React / WebView Personal Agent.
- Fake autonomy via repeated model calls.
- Redesigning Orb cosmetics, tab bar, or marketing copy.
- Expanding GitHub capabilities or adding new tool families.
- Changing kernel policy rules, vault JSON schema, or CI/release workflows except as required to stop mock-default.

If a change does not make Chat → real local reasoning → real work → truthful result more true, it does not belong in this update.

---

## 6. Canonical Agent Execution Path

### 6.1 Product path (iOS)

Canonical. No alternative production path.

1. User submits text through Composer on User Workspace.
2. `LocalAgentService` forwards the goal to `AgentRuntime.submit`.
3. Runtime records the event, creates / attaches an objective, transitions phase via existing state ownership.
4. Classify:
   - **Cheap real path:** remember / forget / status → Memory APIs → result. No LLM required.
   - **Reasoning path:** everything else.
5. Reasoning path builds a **minimal context pack**: current objective, event, targeted memory, current state.
6. Runtime calls `LanguageModelProvider` (router already injected). Default backend is local.
7. Provider returns text; Runtime parses / validates a Decision. Raw model text is not executable.
8. Policy authorizes. Mutating / external / irreversible work may enter NeedsUser.
9. `ActionExecutor` / existing capability dispatch runs approved actions only.
10. Verifier confirms outcomes (memory exists, evidence present, tool result accepted).
11. MemoryWriter persists durable useful results only.
12. Runtime emits events; `AgentRuntimeStore` reduces `AgentRuntimeState`.
13. `WorkspacePresentation` maps state + `AgentRunResult` to conversation, status, progress, result.
14. Orb, progress, and result update from that state.

### 6.2 What is not a path

- Execute tab inventing its own plan list.
- View calling a provider directly.
- Console HTML as iOS substitute.
- `MockLanguageModelProvider` in the default app container.
- Python `Agent.run()` invoked from iOS in this update.

### 6.3 Python / console

Unchanged in charter. Console User Workspace already sits on Python `AgentRuntime`. Do not “fix” Python mock-default in the same slice unless a tiny shared contract test requires it. iOS local-first is the product target.

---

## 7. Execution Flow

```
USER MESSAGE
    │
    ▼
Composer  ───────────────────────────────────────────  only entry
    │
    ▼
AgentRuntime
    │
    ├─ OBSERVE / UNDERSTAND
    │     cheap real intent? ──yes──► ACT (memory) ─► VERIFY ─► RESULT
    │             │ no
    ▼             ▼
RETRIEVE targeted memory
    │
    ▼
DECIDE via Local LLM (default) or Option-2 provider
    │
    │  provider missing / not loaded / privacy block
    │     └── FAIL CLOSED ─► phase=failed ─► truthful error
    │
    ▼
structured Decision
    │
    ▼
AUTHORIZE
    │  denied / needs user ─► NeedsUser / DENIED (not fake success)
    ▼
ACT  (real tools / memory / existing capabilities)
    │
    ▼
VERIFY
    │  fail ─► bounded retry / replan / wait / ask / fail
    ▼
REMEMBER (durable useful only)
    ▼
FINISH or WATCH
    ▼
UI: Answer + Work Performed from Runtime state
```

Idle when idle. No timer → LLM polling loop.

---

## 8. LLM Requirements

### 8.1 Default

| Setting | Production value |
| --- | --- |
| Backend | Local (`on_device` / local server explicitly configured) |
| Privacy mode | On, unless user turns it off **and** selects Option 2 |
| Mock backend | Tests only |
| Cloud backends | Option 2, explicit |

### 8.2 Load semantics

- `load()` must mean the generate path can succeed.
- Catalog download without a runnable backend is `WEIGHTS_NOT_LOADED` / `notLoaded`, not success.
- `RoutingLanguageModelProvider.displayStatus()` must stay honest (`REAL_LOCAL_MODEL` only when generate would actually hit that model).
- CHANGELOG line “Cheap loop still runs if the LLM sidecar is down” is **incompatible** with this spec for generic goals. Sidecar down → fail closed.

### 8.3 Runtime integration

- `AgentRuntime` already depends on `LanguageModelProvider`, not concrete stacks. Keep that.
- Generic-goal planning / reasoning **must** call `generate` or `stream`.
- If the provider throws `notLoaded`, `providerUnavailable`, `generationFailed`: map to `AgentExecutionPhase.failed` with the error on `AgentRuntimeState.error`. Do not catch-and-echo.

### 8.4 Option 2

- OpenAI-compatible providers already exist (`OpenAICompatibleProvider`). Reuse them.
- Switching backend is a Settings concern. Runtime still sees one protocol.
- No `if provider == xAI` inside the agent loop.

### 8.5 Context economy

Keep v0.3 rules: relevant, minimal, fresh, traceable. No full history dump. No “send the vault.”

### 8.6 Deterministic vs mock

| Allowed without LLM | Forbidden without LLM |
| --- | --- |
| remember / forget / status | generic Q&A completed as success |
| policy deny short-circuit | mock planner text as the answer |
| explicit test injection | production `mock.echo` as the work |

---

## 9. Memory / Action Requirements

### Memory

- Source of truth: existing `LocalMemoryStore` / `LocalVaultStore`.
- Retrieve before reasoning; write after verification.
- Do not persist every conversation, every tool blob, or failed attempts as durable memory (v0.3 MemoryWriter rule).
- UI Vault tab continues to show real store contents, not demo fixtures.

### Actions

- Execute only through existing Runtime action / capability interfaces.
- `mock.echo` is not a production generic action.
- Mutating / external actions still require existing authorization (`user_approved` / policy).
- Verification is independent: “tool returned” ≠ “objective succeeded.”
- Work Performed in the UI lists actions that actually ran.

---

## 10. iOS UX Requirements

Native SwiftUI only.

### Layout (User Workspace)

1. **Orb + status** — real `AgentRuntimeState.status` / phase-derived copy.
2. **Conversation** — user turns from Composer; agent turns from Answer and/or Result, labeled honestly.
3. **Work progress** — `steps` + `progress` while `thinking|planning|executing`.
4. **Result** — Answer vs Work Performed (R9). Errors use failed/cancelled state, not a green “Done.”
5. **Actions** — retry / cancel / approve mapped to existing Runtime APIs.
6. **Composer** — single submit.

`WorkspacePresentation` remains the only iOS copy adapter from `AgentRuntimeState` / `AgentRunResult`. Do not `switch (phase)` in random views.

### Honesty in chrome

- “On-device” in Settings must not imply a loaded model if weights or local server are missing.
- Do not show Live Console internals (`run_id`, token counts, phase enum) as the default hierarchy.

### Motion

Orb spin only for thinking/running, and only if Reduce Motion is off (already implemented). Keep it.

---

## 11. Failure Semantics

Fail closed. Fail out loud. Never look smart when you are not.

| Condition | Runtime | UI |
| --- | --- | --- |
| Local model not loaded / weights missing | `failed` + `LanguageModelError.notLoaded` | Error result; Orb ready; no fake answer |
| Local server / sidecar down | `failed` + `providerUnavailable` | Same |
| Privacy mode + cloud backend | `failed` + privacy error (already thrown) | Same |
| Option-2 key missing | `failed` + key missing (already thrown) | Same |
| Generation error / cancel | `failed` / `cancelled` | Truthful |
| Policy deny | DENIED / NeedsUser — not success | Approval card or denial copy |
| Verification fail | bounded retry/replan/ask/fail | Progress shows failed step |
| Cheap-path memory I/O fail | `failed` | Error, not “remembered” |

**Never:**

- Catch provider errors and return “Successfully executed goal …”
- Swap in `MockLanguageModelProvider` because local failed.
- Mark `phase = completed` when no Decision was validated and no real cheap action ran.
- Animate Orb as thinking after the run has failed.

Recovery remains the existing bounded policy (retry / replan / wait / ask / fail). This update does not add a new recovery framework.

---

## 12. Testing Requirements

### 12.1 What tests must prove

Behavioral tests, not only JSON contracts:

1. **LLM invoked:** a generic goal with a fake-but-instrumented `LanguageModelProvider` records `generate`/`stream` called.
2. **Default is local:** app/default settings resolve to a non-mock local backend; privacy mode blocks cloud.
3. **Fail closed:** provider `notLoaded` / `providerUnavailable` → `AgentRunResult` failed, no success template, no `mock.echo`.
4. **Cheap path still real:** remember/forget write and delete Memory without requiring a model.
5. **Memory on reasoning path:** retrieve happens before generate in the instrumented Runtime path; a verified durable fact is written after.
6. **Answer vs work:** result payload can distinguish model text from executed actions.
7. **Presentation honesty:** `WorkspacePresentation` maps `failed` to error presence, not `resultReady` success.
8. **Orb/status mapping:** phase → `AgentStatus` unchanged and covered.
9. **No second system:** tests target existing types (`AgentRuntime`, `LanguageModelProvider`, stores, presentation).

### 12.2 Mock policy

- Mock LLM **allowed in tests**, injected at the `LanguageModelProvider` seam.
- Tests that represent production default **must not** install mock as the router default.
- Do not weaken existing policy / loop tests.

### 12.3 What not to do

- Do not rewrite the 892-test suite.
- Do not add screenshot-only UI tests as the proof of LLM invocation.
- Do not skip Xcode tests because Python tests pass.

---

## 13. Validation Gate

An implementation PR for this Big Update is blocked unless every line is true:

```
VALIDATION GATE — Real Local-First Personal Agent

[ ] Default production backend is Local LLM, not mock, not cloud
[ ] Option-2 providers are explicit Settings choices only
[ ] Generic Composer submit invokes LanguageModelProvider (not LocalDeterministicPlanner / mock.echo)
[ ] Missing/unloaded local model fails closed with a user-visible error
[ ] No silent fallback: local → cloud, local → mock, error → template success
[ ] remember / forget / status still work as real Memory operations without a model
[ ] Reasoning path retrieves targeted memory and may persist durable results
[ ] Actions that claim Work Performed actually executed and were verified
[ ] Answer and Work Performed are distinguishable in the User Workspace
[ ] Orb / progress / result bind to AgentRuntimeState / AgentRunResult only
[ ] Composer remains the single user-facing submit
[ ] No new Runtime, EventBus, Planner, Memory store, or UI-owned agent state
[ ] No broad rewrite (shell, tabs, kernel policy, vault schema, CI) beyond wiring
[ ] New/updated behavioral tests cover invoke, fail-closed, memory, presentation
[ ] Existing relevant tests still PASS
[ ] Xcode build PASS for AgentCoreIOS
[ ] PR is focused; summary names reused types and default/failure behavior
```

If any box is false, the PR is not Done. Polish does not compensate.

---

## 14. Git / PR Requirements (implementation later)

This section applies to **implementation** of the Big Update, not to the commit that adds this file.

1. Branch from current `master`.
2. Smallest diff that satisfies the Validation Gate.
3. One concern per PR if the work must split (e.g. fail-closed routing, then Runtime generic-goal wiring, then presentation labels). Do not open speculative PRs.
4. PR body includes:
   - default backend
   - fail-closed behavior
   - list of existing types reused
   - test commands / Xcode result
   - confirmation of non-goals (no second Runtime, no rewrite)
5. No drive-by formatting, no unrelated file moves, no “while we are here” catalog expansion.
6. Do not treat unsigned IPA or device install as agent Done.

---

## 15. Definition of Done

The Big Update is Done when a reviewer can perform this without debug flags:

1. Cold-start the Native iOS app on default settings (local, privacy on).
2. If the local model is not actually runnable: Composer submit of a generic question **fails visibly**. Orb does not pretend to finish well. No “Successfully executed goal.”
3. If the local model **is** runnable: the same submit calls the local LLM, Runtime walks decide → (optional) act → verify, events update progress, Orb matches phase, and the workspace shows an Answer and any Work Performed as distinct facts.
4. “Remember that my preferred language is Swift” still writes Memory without needing the model.
5. “Forget …” removes it.
6. Switching to Option 2 is explicit; privacy mode still blocks cloud.
7. Killing the local backend mid-flight fails closed; it does not complete via mock.
8. Validation Gate is fully checked.
9. Xcode build PASS; relevant tests PASS.

Until that behavior exists, the product remains a Functional Prototype with a real Runtime and a fake default brain. That is the gap this document exists to close.

---

## 16. Implementation Constraints (for the next agent)

When implementation is requested — and not before:

```
TARGET     Wire default local LLM through existing AgentRuntime on Native iOS
ALLOWED    Router/load semantics, Runtime generic-goal path, fail-closed errors,
           WorkspacePresentation honesty, behavioral tests
FORBIDDEN  New Runtime/EventBus/Planner/Memory/state, web rewrite, UI chrome
           redesign, dual-runtime merge, mock default, silent fallback
DONE       Validation Gate + Definition of Done
```

Read less. Change less. Ship the real path.

```
The model provides intelligence.
The Runtime provides agency.
The UI tells the truth.
```
