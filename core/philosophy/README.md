# Core Philosophy Module — Agent Philosophy & Behavioral Tendencies

> **Architectural Principle**: Philosophy represents soft behavioral tendencies, NOT a Constitution, policy engine, hard rule set, or mandatory instruction list.

---

## 1. Architectural Distinctions

Agent Core maintains strict conceptual separation between core abstractions:

- **Kernel**: *"What the Agent fundamentally is / what the system guarantees."*
  State transitions, safety invariants, policy budgets, and orchestration loop.
- **Rules / Contracts**: *"What the system requires."*
  `TaskConstructionContract`, JSON schemas, verification criteria, and acceptance gates.
- **Experience**: *"What happened."*
  Raw, append-only logs of execution runs, step actions, outcomes, and observations.
- **Lesson**: *"What was learned from what happened."*
  Extracted patterns or observations from experience.
- **Philosophy**: *"How the Agent tends to work because of accumulated learning."*
  Soft behavioral tendencies, preferences, and operational self-knowledge that evolve over time.
- **Knowledge**: *"What the Agent believes/knows about the world or project."*
  Verified primitives, domain concepts, and proven facts about projects or systems.

Do NOT collapse these distinct abstractions into one single layer.

---

## 2. Core Philosophy Pipeline & Hardened Lifecycle

```
Kernel → Experience → Lesson → Philosophy Candidate → Evidence → Tendency → Behavior → Result → new Evidence
```

### Lifecycle States:
- **`CANDIDATE`**: A forming seed derived from a Lesson or single Human Teaching event.
  - *Behavioral Influence*: **ZERO** (`is_active_preference()` = `False`).
- **`SUPPORTED`**: Established tendency backed by supporting evidence or confirmed human feedback (`confidence >= 0.2`).
  - *Behavioral Influence*: **ACTIVE** as a soft preference.
- **`WEAKENED`**: Tendency challenged by contradicting evidence (`confidence < 0.3`).
  - *Behavioral Influence*: **INACTIVE** by default (excluded from `consult_soft_preferences()`).
- **`REJECTED`**: Tendency explicitly rejected by operator (`confidence = 0.0`).
  - *Behavioral Influence*: **PERMANENTLY INACTIVE**.
- **`RETIRED`**: Tendency retired due to obsolescence (`confidence = 0.0`).
  - *Behavioral Influence*: **PERMANENTLY INACTIVE**.

---

## 3. Human Teaching & Feedback Semantics

Human teaching is a strong influence/evidence input, but does **NOT** automatically become established truth:

- `teach()`: Creates a `PhilosophyTendency` in `CANDIDATE` status by default.
- `support()`: Confirms/strengthens a tendency with evidence, transitioning `CANDIDATE` $\rightarrow$ `SUPPORTED`.
- `challenge()` / `contradict()`: Weakens confidence, attaches contradicting evidence IDs, and transitions `SUPPORTED` $\rightarrow$ `WEAKENED`.
- `modify()`: Reshapes the tendency statement while preserving evolution history.
- `reject()`: Rejects a tendency completely (`confidence = 0.0`, `status = REJECTED`).
- `retire()`: Retires an obsolete tendency (`confidence = 0.0`, `status = RETIRED`).

---

## 4. Absolute Precedence Hierarchy

The architecture enforces absolute precedence:

$$\text{Kernel / Security / Contracts} > \text{Verification Requirements} > \text{Explicit Task Requirements} > \text{Philosophy / Tendencies}$$

- Philosophy **CANNOT** override Kernel safety invariants (e.g. secret detection, executor/verifier separation).
- Philosophy **CANNOT** bypass verification requirements (e.g. `verify_contains`, test pass criteria).
- Philosophy **CANNOT** alter explicit task objectives or contracts.
- Philosophy acts **ONLY** as a soft behavioral preference when selecting strategies or investigating uncertainty.

---

## 5. Context-Aware Consultation

`consult_soft_preferences(task_context, min_confidence, include_weakened)`:
- Returns active `SUPPORTED` tendencies sorted by confidence.
- Deterministically filters or ranks tendencies matching task context `tags`, `keywords`, `project_id`, or `goal`.
- `CANDIDATE`, `REJECTED`, and `RETIRED` tendencies are **NEVER** returned.
