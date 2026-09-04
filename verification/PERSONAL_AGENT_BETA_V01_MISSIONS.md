# Personal Agent Beta v0.1 Mission Readiness Specification & Metrics

**Date**: 2026-09-04
**Target Ecosystem**: Agent-Core (`hgblue09124-code/agent-core`)
**Version**: `v0.1.0-beta`
**Ecosystem Integration Status**: **READY FOR BETA USAGE (MOCK/LOCAL TESTED)**

---

## Ecosystem Composition Architecture

```
Agent-Core (Authority / Kernel / Cognition)
  ├── PersonalVaultAdapter ──► agent-personal-vault (Persistent Personal Storage)
  └── ExternalCapabilityBridge ──► agent-capabilities (Pluggable Execution Modules)
```

---

## 1. Beta Mission Set (15 Representative Missions) & Evidence Matrix

### Evidence Classification Legend
- **STATIC**: Schema and architecture design verification.
- **MOCK/LOCAL**: Executable local unit/integration tests (`tests/test_personal_agent_beta_smoke.py`).
- **REAL_EXTERNAL**: Live execution against external services (e.g. `api.github.com`). Marked `NOT EXECUTED` if `GITHUB_TOKEN` is absent in environment.

---

### Mission Matrix

| Mission # | Description | Input | Expected Behavior | Evidence Classification | Local Execution Status | Live External Status |
|-----------|-------------|-------|-------------------|-------------------------|------------------------|----------------------|
| **Mission 1** | Remember Information | "Remember primary branch is master" | Store memory/vault item | **MOCK/LOCAL** | **PASSED** (`test_mission_01`) | N/A |
| **Mission 2** | Retrieve Information | "What is primary branch?" | Retrieve personal context | **MOCK/LOCAL** | **PASSED** (`test_mission_02`) | N/A |
| **Mission 3** | Update Stored Info | "Update editor to Neovim" | Atomically update key | **MOCK/LOCAL** | **PASSED** (`test_mission_03`) | N/A |
| **Mission 4** | Basic Reasoning | Task reasoning request | Evaluate and plan steps | **MOCK/LOCAL** | **PASSED** (`test_mission_04`) | N/A |
| **Mission 5** | Multi-Step Planning | Multi-step task | Generate DAG & execute | **MOCK/LOCAL** | **PASSED** (`test_mission_05`) | N/A |
| **Mission 6** | Vault Read/Write | Store and read vault key | Storage & retrieval | **MOCK/LOCAL** | **PASSED** (`test_mission_06`) | N/A |
| **Mission 7** | Capability Discovery | Query CapabilityRegistry | List specs & schemas | **MOCK/LOCAL** | **PASSED** (`test_mission_07`) | N/A |
| **Mission 8** | Capability Execution | Execute GitHub get_repo | Invoke adapter action | **MOCK/LOCAL** / **REAL_EXTERNAL** | **PASSED** (`test_mission_08`) | **NOT EXECUTED** (No GITHUB_TOKEN) |
| **Mission 9** | Policy Denial | Write call on read-only cap | Deny before dispatch | **MOCK/LOCAL** | **PASSED** (`test_mission_09`) | N/A |
| **Mission 10** | Approval-Required Action | Write call create_issue_comment | Deny without approval; pass with approval | **MOCK/LOCAL** | **PASSED** (`test_mission_10`) | N/A |
| **Mission 11** | Capability Failure Handling | Execute crashing capability | Trap exception; return FAILED | **MOCK/LOCAL** | **PASSED** (`test_mission_11`) | N/A |
| **Mission 12** | Resume Interrupted Task | `agent.resume(run_id)` | Load state and resume loop | **MOCK/LOCAL** | **PASSED** (`test_mission_12`) | N/A |
| **Mission 13** | End-to-End Workflow | Full personal agent request | Execute complete pipeline | **MOCK/LOCAL** | **PASSED** (`test_mission_13`) | N/A |
| **Mission 14** | Repeated Execution | Sequential requests | State/experiences persist | **MOCK/LOCAL** | **PASSED** (`test_mission_14`) | N/A |
| **Mission 15** | Failure Without False Success | GitHub API 401/403/404/503 | Return FAILED; no false success | **MOCK/LOCAL** | **PASSED** (`test_mission_15`) | N/A |

---

## 2. Detailed Mission Specifications

### Mission 1: Remember Information
- **Input**: `memory.remember("Primary development branch is master", memory_type="user_context")`
- **Expected Behavior**: Stores information in memory store with importance score.
- **Pass/Fail Criteria**: PASS if memory store contains entry matching "master".
- **Safety Condition**: Sensitive keys must be redacted from logs/events.

### Mission 2: Retrieve Stored Information
- **Input**: `vault.retrieve_context("branch")`
- **Expected Behavior**: Retrieves personal context from `PersonalVaultAdapter` / memory store.
- **Pass/Fail Criteria**: PASS if retrieved context contains "master".
- **Safety Condition**: Unrelated user context must not be exposed across project boundaries.

### Mission 3: Update Stored Information
- **Input**: `vault.store_context("preferred_editor", {"editor": "neovim"})`
- **Expected Behavior**: Atomically updates existing key in vault.
- **Pass/Fail Criteria**: PASS if subsequent retrieval for editor preference returns "neovim".
- **Safety Condition**: Update must maintain schema validity and preserve audit history.

### Mission 4: Basic Reasoning Task
- **Input**: `agent.run("Basic reasoning task check")`
- **Expected Behavior**: Evaluates project context via Planner and computes step hierarchy.
- **Pass/Fail Criteria**: PASS if valid plan is generated and verified by Kernel.
- **Safety Condition**: Reasoning cannot bypass security policies.

### Mission 5: Multi-Step Planning Task
- **Input**: `agent.run("Inspect workspace architecture and verify docs")`
- **Expected Behavior**: Generates multi-step plan and executes steps sequentially.
- **Pass/Fail Criteria**: PASS if all plan steps execute, verify, and complete.
- **Safety Condition**: Total plan runtime must respect policy time/token budgets.

### Mission 6: Vault Read/Write
- **Input**: `vault.store_context("github_org", {"org": "hgblue09124"})` -> `retrieve_context("github_org")`
- **Expected Behavior**: Context written to vault layer and retrieved accurately.
- **Pass/Fail Criteria**: PASS if stored dictionary matches retrieved payload.
- **Safety Condition**: Storage failure in vault falls back gracefully to local store without crashing Core.

### Mission 7: Capability Discovery
- **Input**: `agent._capabilities.list_specs()`
- **Expected Behavior**: Returns all registered capability specifications.
- **Pass/Fail Criteria**: PASS if `github_integration` and `mock.echo` specs are discoverable.
- **Safety Condition**: Capability discovery must be read-only and non-side-effecting.

### Mission 8: Capability Execution
- **Input**: Execute `github_integration` action `get_repo` for `owner="hgblue09124"`, `repo="agent-core"`.
- **Expected Behavior**: Invokes adapter action and returns structured `CapabilityResult`.
- **Pass/Fail Criteria**: PASS if status is `SUCCESS` and output contains repo metadata.
- **Safety Condition**: Execution must respect timeout limits (`max_execution_time_seconds=30.0`).

### Mission 9: Policy Denial
- **Input**: Execute write capability when read-only constraint applies.
- **Expected Behavior**: `PolicyEngine.authorize_capability()` denies execution before dispatch.
- **Pass/Fail Criteria**: PASS if result returns `authorized=False` and reason indicates read-only restriction.
- **Safety Condition**: Denied requests must never execute downstream code.

### Mission 10: Approval-Required Write Action
- **Input**: Action `create_issue_comment` on GitHub capability without explicit `user_approved=True`.
- **Expected Behavior**: Policy engine rejects execution due to missing explicit user approval. When `user_approved=True` is provided, authorization passes.
- **Pass/Fail Criteria**: PASS if unapproved returns `authorized=False` and approved returns `authorized=True`.
- **Safety Condition**: Mutating actions must NEVER execute without confirmed user authorization.

### Mission 11: Capability Failure Handling
- **Input**: Execute capability that throws an unexpected internal runtime exception.
- **Expected Behavior**: `CapabilityRegistry` / `ExternalCapabilityBridge` catches exception and returns `status="FAILED"`.
- **Pass/Fail Criteria**: PASS if Core remains operational and records failure in experience log.
- **Safety Condition**: Capability exceptions must never crash the Core kernel.

### Mission 12: Resume Interrupted Task
- **Input**: `agent.resume(interrupted_run_id)`
- **Expected Behavior**: Loads run state checkpoint from disk and resumes orchestration loop.
- **Pass/Fail Criteria**: PASS if resumed run completes with verdict `PASS`.
- **Safety Condition**: Resume must restore authoritative state atomically without duplication or corruption.

### Mission 13: End-to-End Personal-Agent Workflow
- **Input**: Request: "Retrieve user preferences, check repository status, and record experience."
- **Expected Behavior**: Pipeline executes full Beta v0.1 acceptance flow across Core + Vault + Capabilities.
- **Pass/Fail Criteria**: PASS if `AgentRunResult.success` is `True` and observations reflect all stages.
- **Safety Condition**: Every stage must pass policy checks and verification.

### Mission 14: Repeated Execution / Continuity
- **Input**: Sequential execution of multiple requests across process restarts.
- **Expected Behavior**: State, experiences, and strategies accumulate persistently across runs.
- **Pass/Fail Criteria**: PASS if run IDs persist distinctively without state corruption.
- **Safety Condition**: Storage writes must be atomic (`.tmp` -> `fsync` -> `os.replace`).

### Mission 15: External Capability Failure Without False Success
- **Input**: GitHub API call returning HTTP 401/403/404/503 error.
- **Expected Behavior**: `GitHubCapabilityAdapter` returns `status="FAILED"` with error message.
- **Pass/Fail Criteria**: PASS if status is `FAILED` and Core records failure (never false success).
- **Safety Condition**: **CRITICAL INVARIANT**: False external success rate must equal 0.0%.

---

## 3. Measurable Beta Metrics & Invariants

### Executable Local Baseline Performance (MOCK/LOCAL Mode)

| Metric Name | Target Value | Measured Baseline Value | Status |
|-------------|--------------|-------------------------|--------|
| **Local Task Success Rate** | ≥ 95.0% | **100.0%** (15/15 missions) | **PASS (MOCK/LOCAL)** |
| **False-Success Rate** | **0.0%** (Hard Invariant) | **0.0%** | **PASS** |
| **Unauthorized Action Rate** | **0.0%** (Hard Invariant) | **0.0%** | **PASS** |
| **Failure Recovery Rate** | ≥ 90.0% | **100.0%** | **PASS** |
| **E2E Latency (Average)** | < 500 ms | **194.5 ms** | **PASS** |
| **Vault Operation Latency** | < 1 ms | **0.004 ms** | **PASS** |
| **Context Retrieval Latency** | < 5 ms | **0.040 ms** | **PASS** |
| **Capability Dispatch Latency**| < 1000 ms | **507.1 ms** | **PASS** |
| **Experience Recording Latency**| < 10 ms | **3.93 ms** | **PASS** |
| **Resume Continuity Latency** | < 5 ms | **0.17 ms** | **PASS** |
| **Live External Service Status**| N/A | **NOT EXECUTED** (No GITHUB_TOKEN) | **NOT EXECUTED** |

---

## 4. Compatibility Report Summary

- **Core ↔ Vault**: **PASS (MOCK/LOCAL)**
- **Core ↔ Capabilities**: **PASS (MOCK/LOCAL)**
- **Policy Boundary**: **PASS (LOCAL)**
- **Continuity / Resume**: **PASS (LOCAL)**
- **Live External Credentials Execution**: **NOT EXECUTED** (No GITHUB_TOKEN in local CI/test env)
- **Beta Readiness Status**: **READY FOR LOCAL DEVELOPER PREVIEW**
