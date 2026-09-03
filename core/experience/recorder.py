# core/experience/recorder.py
"""Experience recorder — captures runtime events as experience records.

This is the integration point between v0.6 RuntimeEngine and v0.8 Experience Engine.
It normalises raw runtime state into structured experience records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from core.experience.schema import Experience


# ── Failure Taxonomy ────────────────────────────────────────────────────

class FailureCategory(str):
    CONFIGURATION  = "CONFIGURATION"   # wrong/missing config
    ENVIRONMENT    = "ENVIRONMENT"     # env var, path, permission
    NETWORK       = "NETWORK"         # connectivity issues
    DEPENDENCY    = "DEPENDENCY"      # missing module, package
    SYNTAX        = "SYNTAX"          # parse/compile error
    TEST_FAILURE  = "TEST_FAILURE"    # test suite failed
    RUNTIME      = "RUNTIME"         # runtime exception
    TIMEOUT       = "TIMEOUT"         # operation timed out
    RESOURCE      = "RESOURCE"        # out of memory/disk/CPU
    LOGIC        = "LOGIC"           # wrong output, incorrect behavior
    VERIFICATION  = "VERIFICATION"    # verification failed
    UNKNOWN       = "UNKNOWN"         # could not determine cause

    @classmethod
    def detect(cls, error: str, stderr: str = "") -> "FailureCategory":
        """Deterministic failure category from error text."""
        blob = f"{error} {stderr}".lower()
        if re.search(r"no module|import error|modulenotfound|importerror", blob):
            return cls.DEPENDENCY
        if re.search(r"connection refused|dns lookup|timeout|network|httperror", blob):
            return cls.NETWORK
        if re.search(r"syntaxerror|parse error|indentation", blob):
            return cls.SYNTAX
        if re.search(r"test.*failed|assertion|pytest|unittest", blob):
            return cls.TEST_FAILURE
        if re.search(r"config|setting|environment variable", blob):
            return cls.CONFIGURATION
        if re.search(r"permission denied|no such file|not found", blob):
            return cls.ENVIRONMENT
        if re.search(r"out of memory|memory error|disk full|resource", blob):
            return cls.RESOURCE
        if re.search(r"timeout|timed out", blob):
            return cls.TIMEOUT
        if re.search(r"exit code|failed|error", blob):
            return cls.RUNTIME
        return cls.UNKNOWN


@dataclass
class FailureRecord:
    """Structured failure record."""
    category: str
    symptom: str
    cause: str
    recovery: str
    evidence: str = ""
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "symptom": self.symptom,
            "cause": self.cause,
            "recovery": self.recovery,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }


# ── Secret detection ────────────────────────────────────────────────────

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xoxb-[A-Za-z0-9-]{20,}"),
    re.compile(r"password\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"secret\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"token\s*[=:]\s*\S+", re.IGNORECASE),
]


def _scrub(text: str) -> str:
    """Remove secret-like patterns from text."""
    result = text
    for pat in _SECRET_PATTERNS:
        result = pat.sub("[REDACTED]", result)
    return result


# ── Experience Recorder ─────────────────────────────────────────────────

@dataclass
class RecordedExperience:
    """A normalised experience ready to be stored."""
    experience: Experience
    failure: Optional[FailureRecord] = None
    observations: list[str] = field(default_factory=list)

    def to_experience(self) -> Experience:
        return self.experience


class ExperienceRecorder:
    """Converts raw runtime data into structured experience records.

    Usage:
        recorder = ExperienceRecorder()
        recorder.start(run_id="RUN-001", goal="create file", project_id="test")
        recorder.record_action("write_file", {"path": "/tmp/test.txt"})
        recorder.record_observation("file created at /tmp/test.txt")
        recorder.record_failure(category=FailureCategory.RUNTIME, symptom="...", ...)
        recorder.record_verification("file contains expected content")
        exp = recorder.finalize()
    """

    def __init__(self):
        self._run_id: str = ""
        self._goal: str = ""
        self._project_id: str = ""
        self._task_id: str = ""
        self._context: list[str] = []
        self._actions: list[str] = []
        self._observations: list[str] = []
        self._verifications: list[str] = []
        self._failure: Optional[FailureRecord] = None
        self._cost: float = 0.0
        self._duration: float = 0.0
        self._llm_calls: int = 0
        self._estimated_tokens: int = 0
        self._start_time: Optional[float] = None
        self._outcome: str = ""

    def start(self, run_id: str, goal: str, project_id: str,
              task_id: str = "", llm_calls: int = 0,
              estimated_tokens: int = 0) -> None:
        self._run_id = run_id
        self._goal = goal
        self._project_id = project_id
        self._task_id = task_id
        self._llm_calls = llm_calls
        self._estimated_tokens = estimated_tokens
        self._start_time = None

    def record_action(self, action: str) -> None:
        self._actions.append(action)

    def record_observation(self, obs: str) -> None:
        self._observations.append(obs)

    def record_verification(self, check: str) -> None:
        self._verifications.append(check)

    def record_failure(self, *, category: str, symptom: str,
                      cause: str = "", recovery: str = "",
                      evidence: str = "", confidence: float = 0.5) -> None:
        self._failure = FailureRecord(
            category=category,
            symptom=symptom,
            cause=cause,
            recovery=recovery,
            evidence=evidence,
            confidence=confidence,
        )

    def set_outcome(self, outcome: str) -> None:
        self._outcome = outcome

    def set_metrics(self, cost: float = 0.0, duration: float = 0.0,
                    llm_calls: int = 0, estimated_tokens: int = 0) -> None:
        self._cost = cost
        self._duration = duration
        self._llm_calls = llm_calls
        self._estimated_tokens = estimated_tokens

    def record_context(self, text: str) -> None:
        self._context.append(text)

    def finalize(self) -> RecordedExperience:
        # Scrub all text
        actions = " | ".join(_scrub(a) for a in self._actions)
        observations = " | ".join(_scrub(o) for o in self._observations)
        verifications = " | ".join(_scrub(v) for v in self._verifications)
        context = " | ".join(_scrub(c) for c in self._context)

        exp = Experience(
            run_id=self._run_id,
            goal=_scrub(self._goal),
            project_id=self._project_id,
            task_id=self._task_id,
            context_summary=context,
            action=actions,
            observation=observations,
            outcome=_scrub(self._outcome),
            failure=(_scrub(self._failure.symptom) if self._failure else ""),
            recovery=(_scrub(self._failure.recovery) if self._failure else ""),
            verification=verifications,
            cost=self._cost,
            duration=self._duration,
            llm_calls=self._llm_calls,
            estimated_tokens=self._estimated_tokens,
        )
        return RecordedExperience(experience=exp, failure=self._failure,
                                  observations=self._observations)


def record_from_run_state(run_state: dict, task_outcomes: list[dict]) -> Experience:
    """Create an Experience from a RuntimeEngine run state.

    This is the main integration bridge from v0.6 to v0.8.
    """
    from datetime import datetime, timezone

    failures = []
    actions = []
    observations = []
    verifications = []
    recovery_text = ""

    for t in task_outcomes:
        actions.append(t.get("title", ""))
        obs = t.get("result", "")
        if obs:
            observations.append(obs)
        vf = t.get("verification", {})
        if vf:
            verifications.append(str(vf))
        err = t.get("error", "")
        if err:
            failures.append(err)

    failure_text = "; ".join(failures) if failures else ""
    category = FailureCategory.detect(failure_text) if failure_text else ""

    metrics = run_state.get("metrics", {})
    goal = run_state.get("goal", "")

    exp = Experience(
        run_id=run_state.get("run_id", ""),
        goal=goal,
        project_id=run_state.get("project_id", ""),
        context_summary="",
        action="; ".join(actions),
        observation="; ".join(observations),
        outcome=run_state.get("status", "UNKNOWN"),
        failure=failure_text,
        recovery=recovery_text,
        verification="; ".join(verifications),
        cost=0.0,
        duration=0.0,
        llm_calls=metrics.get("llm_calls", 0),
        estimated_tokens=metrics.get("estimated_tokens", 0),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return exp
