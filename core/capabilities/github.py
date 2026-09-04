# core/capabilities/github.py
"""GitHub capability adapter — first practical external capability target for Beta v0.1 proof.

Provides GitHub interactions (repo inspection, issue listing, issue retrieval, comment creation)
bound by capability constraints, policy validation, and isolated exception safety.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Optional

from core.capabilities.adapter import BaseCapabilityAdapter
from core.capabilities.schema import CapabilityConstraint, CapabilityResult, CapabilitySpec

logger = logging.getLogger(__name__)


class GitHubCapabilityAdapter(BaseCapabilityAdapter):
    """Adapter for GitHub capability integration."""

    def __init__(self, github_token: Optional[str] = None):
        self._token = github_token or os.getenv("GITHUB_TOKEN")

    def get_spec(self) -> CapabilitySpec:
        """Return the GitHub capability specification."""
        return CapabilitySpec(
            capability_id="github_integration",
            name="GitHub Integration Capability",
            description="Access GitHub repositories, issues, pull requests, and issue comments.",
            version="1.0.0",
            inputs_schema={
                "action": "string (get_repo | list_issues | get_issue | create_issue_comment)",
                "owner": "string",
                "repo": "string",
                "issue_number": "integer (optional)",
                "body": "string (optional comment text)",
            },
            outputs_schema={
                "action": "string",
                "data": "object or array",
            },
            constraints=CapabilityConstraint(
                max_execution_time_seconds=30.0,
                requires_user_approval=False,  # Checked per-action in execute / authorize_capability
                read_only=False,
                allowed_domains=["api.github.com", "github.com"],
            ),
        )

    def execute(self, inputs: dict[str, Any]) -> CapabilityResult:
        """Execute a GitHub capability action."""
        spec = self.get_spec()
        action = inputs.get("action")
        owner = inputs.get("owner")
        repo = inputs.get("repo")

        if not action or not owner or not repo:
            return CapabilityResult(
                capability_id=spec.capability_id,
                status="FAILED",
                error="Missing required parameters: 'action', 'owner', and 'repo' are required.",
            )

        # Explicit mock mode check for offline test execution when requested
        if inputs.get("mock_offline"):
            return self._execute_mock(action, owner, repo, inputs)

        # Dispatch based on action
        try:
            if action == "get_repo":
                return self._get_repo(owner, repo)
            elif action == "list_issues":
                return self._list_issues(owner, repo)
            elif action == "get_issue":
                issue_number = inputs.get("issue_number")
                if not issue_number:
                    return CapabilityResult(
                        capability_id=spec.capability_id,
                        status="FAILED",
                        error="Action 'get_issue' requires 'issue_number'.",
                    )
                return self._get_issue(owner, repo, int(issue_number))
            elif action == "create_issue_comment":
                issue_number = inputs.get("issue_number")
                body = inputs.get("body")
                if not issue_number or not body:
                    return CapabilityResult(
                        capability_id=spec.capability_id,
                        status="FAILED",
                        error="Action 'create_issue_comment' requires 'issue_number' and 'body'.",
                    )
                return self._create_issue_comment(owner, repo, int(issue_number), body)
            else:
                return CapabilityResult(
                    capability_id=spec.capability_id,
                    status="FAILED",
                    error=f"Unsupported GitHub action '{action}'.",
                )
        except Exception as exc:
            logger.error(f"GitHub capability execution error: {exc}")
            return CapabilityResult(
                capability_id=spec.capability_id,
                status="FAILED",
                error=f"GitHub execution exception: {exc}",
            )

    def _execute_mock(self, action: str, owner: str, repo: str, inputs: dict[str, Any]) -> CapabilityResult:
        """Explicit mock execution path for local testing when requested."""
        return CapabilityResult(
            capability_id="github_integration",
            status="SUCCESS",
            output={
                "action": action,
                "data": {"owner": owner, "repo": repo, "mock": True},
            },
            metadata={"simulated_mock": True},
        )

    def _http_request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[dict[str, Any]] = None,
    ) -> tuple[int, Any]:
        """Perform HTTP request to GitHub API safely."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Agent-Core-Beta/0.1.0",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        body_bytes = None
        if data is not None:
            body_bytes = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                resp_data = resp.read().decode("utf-8")
                return resp.status, json.loads(resp_data) if resp_data else {}
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8") if err.fp else ""
            return err.code, {"error": err.reason, "body": err_body}
        except urllib.error.URLError as err:
            return 503, {"error": f"Network error: {err.reason}"}

    def _get_repo(self, owner: str, repo: str) -> CapabilityResult:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        status, res = self._http_request(url)

        if status == 200:
            return CapabilityResult(
                capability_id="github_integration",
                status="SUCCESS",
                output={"action": "get_repo", "data": res},
                metadata={"owner": owner, "repo": repo, "http_status": status},
            )

        err_detail = res.get("error") if isinstance(res, dict) else "API call failed"
        return CapabilityResult(
            capability_id="github_integration",
            status="FAILED",
            error=f"GitHub API error (HTTP {status}): {err_detail}",
            metadata={"owner": owner, "repo": repo, "http_status": status},
        )

    def _list_issues(self, owner: str, repo: str) -> CapabilityResult:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        status, res = self._http_request(url)

        if status == 200 and isinstance(res, list):
            return CapabilityResult(
                capability_id="github_integration",
                status="SUCCESS",
                output={"action": "list_issues", "data": res},
                metadata={"owner": owner, "repo": repo, "http_status": status},
            )

        err_detail = res.get("error") if isinstance(res, dict) else "API call failed"
        return CapabilityResult(
            capability_id="github_integration",
            status="FAILED",
            error=f"GitHub API error (HTTP {status}): {err_detail}",
            metadata={"owner": owner, "repo": repo, "http_status": status},
        )

    def _get_issue(self, owner: str, repo: str, issue_number: int) -> CapabilityResult:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
        status, res = self._http_request(url)

        if status == 200:
            return CapabilityResult(
                capability_id="github_integration",
                status="SUCCESS",
                output={"action": "get_issue", "data": res},
                metadata={"owner": owner, "repo": repo, "issue_number": issue_number, "http_status": status},
            )

        err_detail = res.get("error") if isinstance(res, dict) else "API call failed"
        return CapabilityResult(
            capability_id="github_integration",
            status="FAILED",
            error=f"GitHub API error (HTTP {status}): {err_detail}",
            metadata={"owner": owner, "repo": repo, "issue_number": issue_number, "http_status": status},
        )

    def _create_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> CapabilityResult:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
        status, res = self._http_request(url, method="POST", data={"body": body})

        if status in (200, 201):
            return CapabilityResult(
                capability_id="github_integration",
                status="SUCCESS",
                output={"action": "create_issue_comment", "data": res},
                metadata={"owner": owner, "repo": repo, "issue_number": issue_number, "http_status": status},
            )

        err_detail = res.get("error") if isinstance(res, dict) else "API call failed"
        return CapabilityResult(
            capability_id="github_integration",
            status="FAILED",
            error=f"GitHub API error (HTTP {status}): {err_detail}",
            metadata={"owner": owner, "repo": repo, "issue_number": issue_number, "http_status": status},
        )
