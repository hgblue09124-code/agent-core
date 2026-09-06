Agent Core v0.3 — Personal Agent Runtime

Status: Architecture Baseline
Version: v0.3
Previous: v0.2.x

⸻

1. Mission

Agent Core v0.3 transforms the product from a chat-centric AI application into a runtime-first Personal Agent.

The LLM is the reasoning engine. The Runtime is the Agent.

v0.3 is not “v0.2 + more features”.

It is a re-centering of the system around a persistent Personal Agent Runtime.

The primary optimization targets are:

* useful autonomous behavior
* reliability
* low token/context usage
* deterministic execution
* clear state ownership
* minimal architectural complexity

⸻

2. Non-Negotiable Principles

2.1 Runtime-first

Agent behavior must be owned by the Runtime.

Chat, UI, providers, memory storage, and external integrations are supporting systems.

2.2 LLM is replaceable

The Runtime must work with different reasoning providers:

* local GGUF
* Ollama / llama.cpp
* OpenAI-compatible endpoints
* xAI
* future providers

Provider choice must not leak into core agent logic.

2.3 Deterministic-first

If the Runtime can safely determine the result without an LLM, it must do so.

Deterministic
    ↓
Cheap reasoning
    ↓
Normal reasoning
    ↓
Deep reasoning

Never spend model computation simply because it is available.

2.4 Minimal context

Never send all available memory or conversation history by default.

Context must be:

* relevant
* minimal
* fresh
* traceable

2.5 Observable autonomy

Every meaningful autonomous action must have:

* a reason
* an explicit action
* a result
* verification
* a visible state

2.6 Bounded execution

No autonomous loop may run indefinitely.

Retries, replanning, and model calls must have explicit bounds.

2.7 Simplicity

Do not introduce abstractions, managers, protocols, or layers without a concrete runtime need.

More architecture is not more intelligence.

⸻

3. The Agent Model

The core concepts are:

Agent
 ├── Objective
 ├── State
 ├── Events
 ├── Context
 ├── Decision
 ├── Actions
 ├── Verification
 └── Memory

These concepts must remain distinct even if implementation uses fewer concrete types.

⸻

3.1 Agent

The Agent is a persistent runtime entity.

It owns:

* current state
* active objective
* pending work
* autonomy policy
* execution lifecycle

The Agent is not a chat session.

⸻

3.2 Objective

An Objective represents something the user wants the Agent to accomplish or monitor.

Examples:

Prepare a release.
Monitor a project.
Remember an important preference.
Track a recurring task.

An Objective should have:

intent
desired outcome
status
constraints
success criteria

One conversation may create or modify an Objective.

The Objective survives beyond the individual message that created it.

⸻

3.3 Event

An Event is something the Agent may need to react to.

Sources include:

User input
Application state change
Task completion
External result
Scheduled trigger
Integration event

Events should drive work.

Do not continuously call an LLM to discover whether something changed.

⸻

3.4 State

The Runtime owns explicit Agent state.

Recommended states:

Idle
Observing
Understanding
Retrieving
Deciding
Executing
Verifying
Waiting
NeedsUser
Completed
Failed
Paused

The exact enum may evolve.

The ownership rule may not.

The Runtime owns state transitions.

The LLM may propose a decision; it must not arbitrarily mutate Agent state.

⸻

4. Canonical Agent Loop

The v0.3 loop is:

OBSERVE
   ↓
UNDERSTAND
   ↓
RETRIEVE
   ↓
DECIDE
   ↓
ACT
   ↓
VERIFY
   ↓
REMEMBER
   ↓
WATCH / FINISH

Not every event needs every stage.

Simple events should take the shortest safe path.

⸻

4.1 Observe

Accept relevant events.

The Runtime determines whether the event is:

* irrelevant
* informational
* associated with an existing Objective
* actionable
* requiring user input

⸻

4.2 Understand

Classify intent and complexity.

Prefer deterministic classification where practical.

The Runtime should determine:

What happened?
What objective does it belong to?
Does anything need to happen?
How complex is the decision?

⸻

4.3 Retrieve

Build a context pack specifically for the current decision.

Do not construct one giant global context.

Prefer:

Event
  ↓
Relevant Objective
  ↓
Relevant Memory
  ↓
Current State
  ↓
Minimal Context Pack

⸻

4.4 Decide

Determine the next safe action.

Decision may be produced by:

* deterministic rules
* lightweight classification
* LLM reasoning
* deeper planning

Escalate only when necessary.

The output should become a structured internal Decision before execution.

⸻

4.5 Act

Actions must pass through controlled Runtime interfaces.

Conceptually:

Reasoning
   ↓
Decision
   ↓
Policy
   ↓
Action
   ↓
Result

Never allow raw model text to directly mutate application state.

⸻

4.6 Verify

Meaningful actions require verification.

Examples:

Save data
→ confirm data exists.
Execute task
→ confirm expected state.
External request
→ confirm accepted result.

Verification failure should lead to one of:

Retry
Replan
Wait
Ask user
Fail safely

Never retry forever.

⸻

4.7 Remember

Persist only information with future value.

Do not automatically convert:

* every conversation
* every tool result
* every intermediate state
* every model output

into durable memory.

⸻

4.8 Watch / Finish

After an action:

One-shot Objective
→ Finish
Persistent Objective
→ Continue observing
Missing authorization/input
→ NeedsUser
Temporary dependency
→ Wait

This is the foundation of persistent agent behavior.

⸻

5. Autonomy

Autonomy is a Runtime policy.

The LLM does not decide whether it is allowed to act.

Before execution:

Decision
   ↓
Autonomy / Policy Check
   ├── Allowed → Execute
   ├── Confirmation Required → NeedsUser
   └── Denied → Stop

Safe autonomous actions

Generally include actions that are:

* low risk
* reversible
* informational
* internal
* explicitly authorized

Confirmation actions

Generally include actions that:

* have external consequences
* are irreversible
* expose sensitive information
* spend money
* publish or send information
* modify important user data

User policy may explicitly expand or restrict autonomy.

⸻

6. Memory Architecture

Memory is a source of useful personal context, not a transcript archive.

At minimum, distinguish:

Working Context
≠
Execution State
≠
Durable Memory

Working Context

Temporary information required for the current decision.

Execution State

Information required to continue or recover the current Objective.

Durable Memory

Information worth retaining for future interactions.

Useful durable categories may include:

Facts
Preferences
Goals
Projects
Decisions
Routines
Important history

Memory retrieval must be targeted.

⸻

7. Context Economy

The Agent should optimize:

Useful decisions per token.

Preferred flow:

Event
 ↓
Classify
 ↓
Targeted retrieval
 ↓
Minimal context
 ↓
Decision

Avoid:

* full conversation replay
* full memory injection
* duplicate context
* unnecessary tool output
* repeated system instructions
* planner calls for trivial tasks

Context should be assembled as late as practical and discarded when no longer needed.

⸻

8. Reasoning Economy

Model capability should scale with task complexity.

Simple
  ↓
Deterministic / local
  ↓
Normal
  ↓
Deep reasoning

Examples:

Remember X
→ deterministic memory operation
Check current state
→ Runtime / integration
Classify request
→ cheap path
Complex multi-step objective
→ LLM planning/reasoning

A model call must have a meaningful purpose.

Autonomy must not become:

event → LLM → event → LLM → event → LLM

Prefer:

event → evaluate → act → verify

⸻

9. Decision Contract

The reasoning layer should produce a structured Decision.

Conceptually:

Decision
 ├── intent
 ├── action
 ├── arguments
 ├── confidence
 ├── risk
 └── verification

The exact schema may evolve.

The ownership rule does not:

The Runtime validates decisions before execution.

Natural-language model output is not an executable command.

⸻

10. Action Contract

Actions must be explicit and observable.

Conceptually:

Action
 ├── identifier
 ├── type
 ├── arguments
 ├── authorization state
 ├── execution state
 └── result

This enables:

* Activity
* verification
* retries
* recovery
* debugging
* user visibility

⸻

11. Failure and Recovery

Failure is part of normal Agent behavior.

Useful failure classes:

Transient
Permanent
Invalid action
Missing context
Missing authorization
Provider unavailable
Verification failure

Recovery:

Failure
  ↓
Classify
  ├── Retry
  ├── Replan
  ├── Wait
  ├── Ask user
  └── Fail safely

All autonomous recovery must be bounded.

⸻

12. Provider Boundary

The provider layer remains infrastructure.

The Runtime requests reasoning without knowing whether the provider is:

GGUF
Ollama
llama.cpp
OpenAI-compatible
xAI
Other

Do not spread provider-specific branches throughout Agent Core.

Avoid:

if provider == xAI
if provider == OpenAI
if provider == Ollama

inside core agent behavior.

Provider selection belongs to the provider/routing subsystem.

⸻

13. Event-Driven Autonomy

Persistent objectives should be event-driven whenever possible.

Prefer:

Event
 ↓
Evaluate
 ↓
Decision
 ↓
Action

Avoid:

Timer
 ↓
LLM
 ↓
Timer
 ↓
LLM
 ↓
Timer
 ↓
LLM

The Agent should remain idle when there is nothing meaningful to process.

This reduces:

* token usage
* latency
* battery consumption
* network usage
* cloud cost

⸻

14. iOS / UI Principle

The UI must represent Agent behavior.

It must not become a second Agent Runtime.

Home should answer:

“What is my Agent doing for me?”

rather than:

“What can I ask the chatbot?”

The product should surface:

Active objectives
Things being monitored
Recently completed work
Pending decisions
Important observations
Agent state

Chat remains an interface.

It is not the architecture.

⸻

15. Activity

Activity represents meaningful Agent behavior.

Examples:

Objective created
Objective updated
Event observed
Decision made
Action executed
Verification succeeded
Verification failed
Memory updated
Approval requested
Objective completed

Do not expose raw internal noise as user-facing activity.

⸻

16. Security / Privacy

The Runtime must control privacy and authorization independently of the LLM.

Rules:

* minimize sensitive context before provider calls
* respect privacy mode outside the model
* keep secrets in secure storage
* enforce cloud/local policy in the application
* do not trust model output as authorization

A model saying “the user authorized this” is not authorization.

⸻

17. Source-of-Truth Ownership

Keep ownership explicit:

Agent State
→ Runtime
Objective Lifecycle
→ Runtime
Execution State
→ Runtime
Autonomy / Authorization
→ Policy / Runtime
Durable Memory
→ Memory subsystem
Provider Selection
→ Routing subsystem
Reasoning
→ LLM provider
Action Execution
→ Action subsystem
Presentation
→ UI

No subsystem should silently become the source of truth for another.

⸻

18. Architectural Anti-Goals

v0.3 must actively avoid:

God Objects

Do not turn one Runtime class into the owner of the entire application.

Abstraction Explosion

Do not add protocols/managers/layers merely for theoretical flexibility.

Chat Coupling

Agent behavior must work without a chat screen.

Provider Coupling

Core Runtime must not depend on a specific model vendor.

LLM Dependency

Simple deterministic operations must work without an LLM.

Fake Autonomy

Repeated model calls do not constitute intelligence.

Feature Inflation

Do not add features merely because they are easy to implement.

⸻

19. Implementation Strategy

v0.3 implementation should follow this order:

1. Runtime state + ownership
2. Objective / Event model
3. Canonical Agent Loop
4. Decision / Action contracts
5. Verification + recovery
6. Context economy
7. Autonomy policy
8. Memory integration
9. iOS integration
10. UI refinement
11. Hardening / tests

Do not start by redesigning every screen.

Do not start by adding providers.

Do not start by adding new model catalogs.

The Runtime is the priority.

⸻

20. Grok / Jules Contract

Grok — Core Intelligence

Primary responsibility:

* Personal Agent Runtime design
* state machine
* decision flow
* autonomy
* event-driven behavior
* context economy
* recovery/replanning

Grok should optimize for behavioral capability without inflating the architecture.

⸻

Jules — Product Integration

Primary responsibility:

* v0.2 → v0.3 refactoring
* Runtime integration
* persistence
* iOS state binding
* Activity
* UI integration
* tests
* CI/release compatibility

Jules should preserve Runtime ownership boundaries.

⸻

Shared Rule

Both agents must treat this document as the v0.3 architectural baseline.

Before adding an abstraction or feature, ask:

Does this make the Personal Agent more capable, reliable, autonomous, or efficient?

If not, do not add it.

⸻

21. Definition of Done

v0.3 is successful when the system can demonstrate:

User gives an objective
        ↓
Agent understands it
        ↓
Objective becomes persistent
        ↓
Agent observes relevant events
        ↓
Relevant context is retrieved
        ↓
Agent decides
        ↓
Policy validates action
        ↓
Agent acts
        ↓
Result is verified
        ↓
Useful information is remembered
        ↓
Agent finishes or continues watching

And:

No unnecessary LLM call
No unnecessary context
No uncontrolled autonomous loop
No provider dependency in core
No hidden state mutation
No unverified meaningful action

⸻

22. Final Definition

The v0.3 architecture can be reduced to one principle:

The model provides intelligence.
The Runtime provides agency.

Agent Core should therefore optimize not for the biggest model, the largest context, or the most features.

It should optimize for:

A small, reliable, persistent runtime that turns intelligence into useful personal action.

That is the foundation of Agent Core v0.3.