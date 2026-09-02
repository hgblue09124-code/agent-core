# core/planner/planner.py
"""LLM Planner — provider-agnostic planning engine.

Planner v0.2 — LLM = PLANNER, TaskRunner = EXECUTOR, Verification = AUTHORITY.

Architecture:
    User Intent → Context → Prompt → LLM → JSON → Validate → Plan
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable

from core.planner.schema import (
    Plan,
    PlanStep,
    ValidationResult,
    ValidationError,
)
from core.planner.context import (
    PlannerContext,
    build_context,
    ContextStats,
)
from core.planner.prompt import (
    PromptConfig,
    build_full_prompt,
    parse_llm_response,
)
from core.planner.validator import PlanValidator, validate_plan
from core.projects.manager import ProjectManager
from core.projects.context import load_project_context
from core.tasks.schema import Task, TaskStep, StepType, TaskStatus
from core.tasks.manager import TaskManager


# ── Provider interface ──────────────────────────────────────────────────

class PlannerProvider(ABC):
    """Abstract LLM provider for the planner.

    Implement this to add a new provider:
        class OpenRouterProvider(PlannerProvider):
            def _call_llm(self, system: str, user: str) -> str:
                # call OpenRouter API
                ...

    The provider is responsible for:
    - Formatting the request
    - Calling the LLM API
    - Returning raw text response
    """

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM with system and user prompts. Return raw text response."""
        raise NotImplementedError


# ── Mock provider ──────────────────────────────────────────────────────

class MockPlannerProvider(PlannerProvider):
    """Mock LLM provider for testing without API calls.

    Uses a template-based approach that produces structurally valid JSON
    plans. Does not call any external API.
    """

    def __init__(
        self,
        response_override: Optional[str] = None,
        error_on_call: bool = False,
    ):
        """Args:
            response_override: if set, return this string instead of the template.
            error_on_call: if True, raise RuntimeError on generate().
        """
        self.response_override = response_override
        self.error_on_call = error_on_call
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self._call_count += 1
        if self.error_on_call:
            raise RuntimeError("MockPlannerProvider: error_on_call is True")
        if self.response_override:
            return self.response_override
        return self._build_template_response(user_prompt)

    def _build_template_response(self, user_prompt: str) -> str:
        """Extract the objective from the user prompt and build a template plan."""
        # Try to find the objective in the user prompt
        objective = "Plan based on user request"
        for line in user_prompt.splitlines():
            if line.startswith("## User Objective"):
                # Next non-empty line is the objective
                obj_lines = user_prompt.splitlines()
                for i, l in enumerate(obj_lines):
                    if "User Objective" in l and i + 1 < len(obj_lines):
                        next_line = obj_lines[i + 1].strip()
                        if next_line and not next_line.startswith("#"):
                            objective = next_line
                        break
                break

        # Build a realistic mock plan
        plan = {
            "objective": objective,
            "assumptions": [
                f"Assuming project context provides sufficient detail for: {objective}",
                "Assuming the user has access to the project's source files.",
            ],
            "steps": [
                {
                    "step_id": "step-1",
                    "title": "Inspect project structure",
                    "description": f"Use the inspect step to gather project metadata and file listing for: {objective}",
                    "step_type": "inspect",
                    "dependencies": [],
                    "command": "",
                    "arguments": [],
                    "expected_result": "Project metadata and file listing",
                    "verify_contains": [],
                    "verify_not_contains": [],
                    "expect_exit_code": 0,
                },
                {
                    "step_id": "step-2",
                    "title": "List relevant source files",
                    "description": "List the project source directory to understand the codebase layout",
                    "step_type": "shell",
                    "dependencies": ["step-1"],
                    "command": "ls",
                    "arguments": ["-la"],
                    "expected_result": "Directory listing with source files",
                    "verify_contains": [],
                    "verify_not_contains": [],
                    "expect_exit_code": 0,
                },
            ],
            "verification": [
                {
                    "description": "Project structure is accessible and inspect step returned valid metadata",
                    "method": "inspect",
                    "command": "",
                    "args": [],
                    "expect_exit_code": 0,
                    "verify_contains": [],
                },
                {
                    "description": "Shell step completed without errors",
                    "method": "diff",
                    "command": "",
                    "args": [],
                    "expect_exit_code": 0,
                    "verify_contains": [],
                },
            ],
            "risks": [
                "Assumes project root is accessible from the execution environment.",
            ],
            "estimated_complexity": "simple",
            "notes": f"Auto-generated mock plan for: {objective}",
        }
        return json.dumps(plan, ensure_ascii=False, indent=2)


# ── Environment-based provider ─────────────────────────────────────────

@dataclass
class EnvironmentPlannerConfig:
    """Configuration loaded from environment variables."""
    provider: str = "mock"      # "mock" | "openrouter" | "local"
    api_key: str = ""
    model: str = "gpt-4o"
    base_url: str = ""


def load_provider_config() -> EnvironmentPlannerConfig:
    """Load provider config from environment variables."""
    import os
    return EnvironmentPlannerConfig(
        provider=os.environ.get("AGENTCORE_PLANNER_PROVIDER", "mock"),
        api_key=os.environ.get("AGENTCORE_PLANNER_API_KEY", ""),
        model=os.environ.get("AGENTCORE_PLANNER_MODEL", "gpt-4o"),
        base_url=os.environ.get("AGENTCORE_PLANNER_BASE_URL", ""),
    )


class LocalPlannerProvider(PlannerProvider):
    """Provider that calls a local LLM server (e.g. ollama, LM Studio).

    Set AGENTCORE_PLANNER_BASE_URL and AGENTCORE_PLANNER_API_KEY.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        api_key: str = "",
        model: str = "llama3",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        import urllib.request
        import urllib.error

        self._call_count += 1
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={
                "Content-Type": "application/json",
                **( {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {} ),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["message"]["content"]
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(
                f"LocalPlannerProvider call failed: {exc}\n"
                "Make sure the local LLM server is running."
            ) from exc


class OpenRouterPlannerProvider(PlannerProvider):
    """Provider that calls OpenRouter API."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "openai/gpt-4o",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        import os
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        import urllib.request
        import urllib.error

        if not self.api_key:
            raise RuntimeError(
                "OpenRouterPlannerProvider: AGENTCORE_PLANNER_API_KEY not set, "
                "and no api_key provided."
            )

        self._call_count += 1
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/agent-core",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(f"OpenRouterPlannerProvider call failed: {exc}") from exc


# ── OpenAI-compatible provider ─────────────────────────────────────────

class OpenAIPlannerProvider(PlannerProvider):
    """Provider that calls any OpenAI-compatible API endpoint.

    Environment variables:
        OPENAI_API_KEY   — API key (required)
        OPENAI_BASE_URL  — base URL (default: https://api.openai.com/v1)
        OPENAI_MODEL     — model name (default: gpt-4o)

    Works with OpenAI, Azure OpenAI (with custom endpoint), and other
    OpenAI-compatible servers (vllm, text-gen-webui, etc.).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        import os
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL",
                            "https://api.openai.com/v1")).rstrip("/")
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        import urllib.request
        import urllib.error

        if not self.api_key:
            raise RuntimeError(
                "OpenAIPlannerProvider: OPENAI_API_KEY not set."
            )

        self._call_count += 1
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(
                f"OpenAIPlannerProvider call failed: {exc}"
            ) from exc


def create_provider(
    config: Optional[EnvironmentPlannerConfig] = None,
) -> PlannerProvider:
    """Factory to create a provider from environment config."""
    cfg = config or load_provider_config()

    if cfg.provider == "openai":
        return OpenAIPlannerProvider(
            api_key=cfg.api_key,
            model=cfg.model,
            base_url=cfg.base_url,
        )
    elif cfg.provider == "openrouter":
        return OpenRouterPlannerProvider(
            api_key=cfg.api_key,
            model=cfg.model,
            base_url=cfg.base_url or "https://openrouter.ai/api/v1",
        )
    elif cfg.provider == "local":
        return LocalPlannerProvider(
            base_url=cfg.base_url or "http://localhost:11434",
            api_key=cfg.api_key,
            model=cfg.model,
        )
    elif cfg.provider == "openai":
        return OpenAIPlannerProvider(
            api_key=cfg.api_key,
            model=cfg.model,
            base_url=cfg.base_url,
        )
    else:
        return MockPlannerProvider()


# ── Planner ─────────────────────────────────────────────────────────────

@dataclass
class PlanResult:
    """Result of a planning operation."""
    plan: Optional[Plan]
    validation: ValidationResult
    raw_llm_output: str
    context_stats: Optional[ContextStats]
    provider_name: str
    error: Optional[str] = None


class Planner:
    """LLM-assisted planner with validation.

    Pipeline:
        intent → context → prompt → LLM → parse → validate → plan

    The LLM NEVER executes commands. Only the TaskRunner executes.
    """

    def __init__(
        self,
        provider: Optional[PlannerProvider] = None,
        max_context_tokens: int = 4000,
    ):
        self.provider = provider or MockPlannerProvider()
        self.max_context_tokens = max_context_tokens
        self._project_ids: set[str] = set()

    def _load_registered_projects(self) -> set[str]:
        """Load project IDs from the registry."""
        if not self._project_ids:
            mgr = ProjectManager()
            self._project_ids = {p.project_id for p in mgr.list_projects()}
        return self._project_ids

    def plan(
        self,
        project_id: str,
        objective: str,
    ) -> PlanResult:
        """Generate a plan for an objective against a registered project.

        Returns a PlanResult with plan, validation, stats, and any error.
        """
        # 1. Load project context
        proj_ctx = load_project_context(project_id)
        if proj_ctx is None:
            return PlanResult(
                plan=None,
                validation=ValidationResult(valid=False),
                raw_llm_output="",
                context_stats=None,
                provider_name=self.provider.__class__.__name__,
                error=f"Project '{project_id}' not found in registry.",
            )

        # 2. Build context
        context = build_context(
            agent_contract=proj_ctx.agent_contract,
            architecture=proj_ctx.architecture,
            source_of_truth=proj_ctx.source_of_truth,
            project_metadata={
                "project_id": proj_ctx.project_id,
                "name": proj_ctx.name,
                "root_path": proj_ctx.root_path,
                "status": proj_ctx.status,
            },
            max_tokens=self.max_context_tokens,
        )

        # 3. Build prompt
        config = PromptConfig(
            project_id=project_id,
            project_name=proj_ctx.name,
            objective=objective,
        )
        system_prompt, user_prompt = build_full_prompt(config, context.sections)

        # 4. Call LLM
        try:
            raw_output = self.provider.generate(system_prompt, user_prompt)
        except Exception as exc:
            return PlanResult(
                plan=None,
                validation=ValidationResult(valid=False),
                raw_llm_output="",
                context_stats=context.stats,
                provider_name=self.provider.__class__.__name__,
                error=f"LLM call failed: {exc}",
            )

        # 5. Parse
        try:
            parsed = parse_llm_response(raw_output)
        except ValueError as exc:
            vr = ValidationResult(valid=False)
            vr.add_error("PARSE_ERROR", str(exc), field="raw_response")
            return PlanResult(
                plan=None,
                validation=vr,
                raw_llm_output=raw_output,
                context_stats=context.stats,
                provider_name=self.provider.__class__.__name__,
                error=str(exc),
            )

        # 6. Deserialize to Plan
        try:
            # Inject project_id so the LLM doesn't need to guess it
            parsed_with_project = dict(parsed)
            parsed_with_project["project_id"] = project_id
            plan = Plan.from_dict(parsed_with_project)
        except (KeyError, TypeError, ValueError) as exc:
            vr = ValidationResult(valid=False)
            vr.add_error("DESERIALIZE_ERROR", f"Failed to parse plan: {exc}", field="plan")
            return PlanResult(
                plan=None,
                validation=vr,
                raw_llm_output=raw_output,
                context_stats=context.stats,
                provider_name=self.provider.__class__.__name__,
                error=str(exc),
            )

        # 7. Validate
        project_ids = self._load_registered_projects()
        validator = PlanValidator(project_ids=project_ids)
        validation = validator.validate(plan)

        if not validation.valid:
            return PlanResult(
                plan=None,
                validation=validation,
                raw_llm_output=raw_output,
                context_stats=context.stats,
                provider_name=self.provider.__class__.__name__,
                error="Plan failed validation.",
            )

        return PlanResult(
            plan=plan,
            validation=validation,
            raw_llm_output=raw_output,
            context_stats=context.stats,
            provider_name=self.provider.__class__.__name__,
        )


# ── Plan → Task conversion ─────────────────────────────────────────────

def plan_to_task(plan: Plan) -> Task:
    """Convert a validated Plan into a Task.

    The Task can then be saved via TaskManager and executed by TaskRunner.
    """
    steps = []
    for ps in plan.steps:
        step_type_map = {
            "shell": StepType.SHELL,
            "python": StepType.PYTHON,
            "inspect": StepType.INSPECT,
        }
        step = TaskStep(
            type=step_type_map.get(ps.step_type, StepType.SHELL),
            title=ps.title,
            description=ps.description,
            command=ps.command,
            args=list(ps.arguments),
            expect_exit_code=ps.expect_exit_code,
            verify_contains=list(ps.verify_contains),
            verify_not_contains=list(ps.verify_not_contains),
        )
        steps.append(step)

    return Task(
        task_id="",           # filled by TaskManager.create_task
        project_id=plan.project_id,
        title=plan.objective,
        description=f"Plan: {plan.notes or plan.objective}",
        status=TaskStatus.PENDING,
        created_at="",
        steps=steps,
    )
