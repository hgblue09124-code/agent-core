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

## 2. Core Philosophy Pipeline

```
Kernel → Experience → Lesson → Philosophy Candidate → Evidence → Tendency → Behavior → Result → new Evidence
```

1. **Experience**: Execution runs record actions and outcomes.
2. **Lesson**: `LessonEngine` extracts structured patterns from experiences.
3. **Philosophy Candidate**: `PhilosophyEngine.propose_candidate_from_lesson()` bridges a Lesson into a `PhilosophyTendency` candidate with explicit provenance.
4. **Human Teaching & Feedback**: Operators teach, support, challenge, modify, reject, or retire tendencies.
5. **Soft Behavioral Preference**: Planners and decision engines consult active tendencies as soft preferences.
6. **New Evidence**: Results update supporting or contradicting evidence IDs and confidence scores.

---

## 3. Explicit Precedence Hierarchy

The architecture enforces absolute precedence:

$$\text{Kernel / Security / Contracts} > \text{Verification Requirements} > \text{Explicit Task Requirements} > \text{Philosophy / Tendencies}$$

- Philosophy **CANNOT** override Kernel safety invariants (e.g. secret detection, executor/verifier separation).
- Philosophy **CANNOT** bypass verification requirements (e.g. `verify_contains`, test pass criteria).
- Philosophy **CANNOT** alter explicit task objectives or contracts.
- Philosophy acts **ONLY** as a soft behavioral preference when selecting strategies or investigating uncertainty.

---

## 4. Human Teaching & Challenge Mechanisms

Operators have full authority to reshape the Agent's behavioral tendencies over time:

- `teach()`: Introduce a new behavioral tendency.
- `support()`: Strengthen confidence and promote candidate to `SUPPORTED`.
- `challenge()` / `contradict()`: Weaken confidence, add contradicting evidence, and transition status to `WEAKENED`.
- `modify()`: Reshape the tendency statement while preserving evolution history.
- `reject()`: Instantly reject a tendency (confidence = 0.0, status = `REJECTED`).
- `retire()`: Retire an obsolete tendency (confidence = 0.0, status = `RETIRED`).

---

## 5. Operational Self-Knowledge

Philosophy tendencies capture operational self-knowledge derived from evidence and human critique, such as:

- *"I tend to verify assumptions before modifying code."*
- *"I perform better when I inspect project structure first."*
- *"I tend to check test suite execution status before final submission."*
