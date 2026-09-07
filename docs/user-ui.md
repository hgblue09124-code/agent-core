# Personal Agent User UI

Presentation-only layer over AgentRuntime. Runtime stays the brain.

## Why the old console was a Dev UI

`console/` rendered Runtime internals as the primary interface:

- phase legend (`PLAN` / `EXECUTE` / `VERIFY`)
- `run_id`, event counts, evidence key/value dumps
- metrics (`llm_calls`, tokens)
- no chat composer despite `/api/agent/submit`
- no human activity, no approval card, no result-first layout

The data model was already sufficient (`AgentState`, `Objective`, `AgentEvent`, `CycleResult`). The View was dumping it raw.

## Information architecture

```
USER INTENT
  → OBJECTIVE
  → CURRENT ACTIVITY
  → PROGRESS
  → RESULT
  → DETAILS (developer)
```

Technical fields (`phase`, `state`, `event`, diagnostics) remain in the payload under `developer` and in the Live Console drawer. They are not the default visual hierarchy.

## Mapping

`core/console/presentation.py` is the only place user copy lives.

- Consumes: `AgentState`, `Objective`, `Action`, `ExecutionResult`, `AgentEvent`, `CycleResult`
- Produces: identity, activity, progress, result, pending_approval, history
- Unknown phases/actions fall back to generic human language (`working` + token humanization)
- The View renders those dictionaries. It must not `switch (phase)`.

## Surfaces

- **User workspace** — default. Chat, current objective, activity, progress, result, approval.
- **Live Console** — existing developer feed, behind an explicit toggle. Not deleted.

## API (additive)

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/agent/submit` | existing fields kept; adds `presentation` |
| GET | `/api/agent/workspace` | user snapshot |
| POST | `/api/agent/approve` | `runtime.approve(objective_id)` |
| GET | `/api/agent/state` | raw `AgentState` |
| GET | `/api/runs*` | unchanged Live Console |

No Runtime loop, policy, or capability changes.
