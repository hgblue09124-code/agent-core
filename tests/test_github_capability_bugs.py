#!/usr/bin/env python3
# tests/test_github_capability_bugs.py
"""Focused regression test suite for Bug #1 and Bug #2 fixes.

Bug #1: GitHub API HTTP errors (401, 403, 404, 503, etc.) must NEVER return status="SUCCESS".
Bug #2: GitHub write actions (create_issue_comment) must require explicit user approval.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.agent import Agent, AgentRunResult
from core.capabilities.github import GitHubCapabilityAdapter
from core.capabilities.schema import CapabilityResult
from core.kernel.policy import PolicyEngine


class TestBug1GitHubAPIErrors(unittest.TestCase):
    """Regression tests for Bug #1: HTTP errors must be reported as FAILED."""

    def setUp(self):
        self.gh = GitHubCapabilityAdapter()

    def test_http_401_unauthorized_returns_failed(self):
        with patch.object(self.gh, "_http_request", return_value=(401, {"error": "Unauthorized", "body": "Bad credentials"})):
            res: CapabilityResult = self.gh.execute({"action": "get_repo", "owner": "owner", "repo": "repo"})
            self.assertFalse(res.success)
            self.assertEqual(res.status, "FAILED")
            self.assertIn("HTTP 401", res.error)

    def test_http_403_forbidden_returns_failed(self):
        with patch.object(self.gh, "_http_request", return_value=(403, {"error": "Forbidden", "body": "Rate limit exceeded"})):
            res: CapabilityResult = self.gh.execute({"action": "list_issues", "owner": "owner", "repo": "repo"})
            self.assertFalse(res.success)
            self.assertEqual(res.status, "FAILED")
            self.assertIn("HTTP 403", res.error)

    def test_http_404_not_found_returns_failed(self):
        with patch.object(self.gh, "_http_request", return_value=(404, {"error": "Not Found"})):
            res: CapabilityResult = self.gh.execute({"action": "get_issue", "owner": "owner", "repo": "repo", "issue_number": 999})
            self.assertFalse(res.success)
            self.assertEqual(res.status, "FAILED")
            self.assertIn("HTTP 404", res.error)

    def test_http_503_network_failure_returns_failed(self):
        with patch.object(self.gh, "_http_request", return_value=(503, {"error": "Network error: Connection refused"})):
            res: CapabilityResult = self.gh.execute({"action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": 1, "body": "Test comment"})
            self.assertFalse(res.success)
            self.assertEqual(res.status, "FAILED")
            self.assertIn("HTTP 503", res.error)

    def test_successful_200_response_returns_success(self):
        with patch.object(self.gh, "_http_request", return_value=(200, {"full_name": "owner/repo"})):
            res: CapabilityResult = self.gh.execute({"action": "get_repo", "owner": "owner", "repo": "repo"})
            self.assertTrue(res.success)
            self.assertEqual(res.status, "SUCCESS")

    def test_failed_capability_execution_yields_failed_agent_run(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
        agent = Agent(project_id="default")

        with patch.object(agent._capabilities.get("github_integration"), "_http_request", return_value=(401, {"error": "Unauthorized"})):
            res: AgentRunResult = agent.run(
                "Run with failing github API call",
                capability_dispatch=("github_integration", {"action": "get_repo", "owner": "owner", "repo": "repo"}),
            )
            self.assertFalse(res.success)
            self.assertEqual(res.verification_verdict, "FAIL")
            self.assertTrue(any("github_integration" in err for err in res.errors))


class TestBug2GitHubWriteApproval(unittest.TestCase):
    """Regression tests for Bug #2: GitHub write capabilities require explicit approval."""

    def setUp(self):
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"
        self.agent = Agent(project_id="default")
        self.policy = PolicyEngine()

    def test_write_action_without_approval_is_denied_by_policy(self):
        spec = self.agent._capabilities.get("github_integration").get_spec()

        authorized, reason = self.policy.authorize_capability(
            spec,
            action="create_issue_comment",
            inputs={"action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": 1, "body": "comment"},
            user_approved=False,
        )
        self.assertFalse(authorized)
        self.assertIn("requires explicit user approval", reason)

    def test_write_action_with_approval_is_authorized(self):
        spec = self.agent._capabilities.get("github_integration").get_spec()

        authorized, reason = self.policy.authorize_capability(
            spec,
            action="create_issue_comment",
            inputs={"action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": 1, "body": "comment"},
            user_approved=True,
        )
        self.assertTrue(authorized)
        self.assertIsNone(reason)

    def test_readonly_action_without_approval_is_authorized(self):
        spec = self.agent._capabilities.get("github_integration").get_spec()

        for read_action in ("get_repo", "list_issues", "get_issue"):
            authorized, reason = self.policy.authorize_capability(
                spec,
                action=read_action,
                inputs={"action": read_action, "owner": "owner", "repo": "repo"},
                user_approved=False,
            )
            self.assertTrue(authorized, f"Read-only action '{read_action}' should be authorized without user approval")
            self.assertIsNone(reason)

    def test_agent_run_denies_unapproved_write_capability(self):
        res: AgentRunResult = self.agent.run(
            "Create issue comment without approval",
            capability_dispatch=(
                "github_integration",
                {"action": "create_issue_comment", "owner": "owner", "repo": "repo", "issue_number": 1, "body": "comment"},
            ),
            user_approved=False,
        )
        self.assertFalse(res.success)
        self.assertTrue(any("denied" in err.lower() for err in res.errors))


if __name__ == "__main__":
    unittest.main()
