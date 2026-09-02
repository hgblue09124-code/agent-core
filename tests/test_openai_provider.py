#!/usr/bin/env python3
# tests/test_openai_provider.py
"""OpenAI-compatible provider v0.4 — offline tests.

Run: python3 -m unittest tests.test_openai_provider -v

Tests mock urllib.request.urlopen. No real API calls.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.planner.planner import (
    OpenAIPlannerProvider,
    Planner,
    PlanResult,
)
from core.planner.schema import Plan, PlanStep, PlanComplexity


def _make_mock_response(payload: dict) -> MagicMock:
    """Build a MagicMock that quacks like a urllib response."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _valid_plan_json() -> str:
    return json.dumps({
        "objective": "Inspect the project",
        "assumptions": ["Test assumption"],
        "steps": [
            {
                "step_id": "step-1",
                "title": "Inspect",
                "description": "Inspect project",
                "step_type": "inspect",
                "dependencies": [],
                "command": "",
                "arguments": [],
                "expected_result": "metadata",
                "verify_contains": [],
                "verify_not_contains": [],
                "expect_exit_code": 0,
            },
            {
                "step_id": "step-2",
                "title": "Echo hello",
                "description": "Run echo",
                "step_type": "shell",
                "dependencies": ["step-1"],
                "command": "echo",
                "arguments": ["hello"],
                "expected_result": "hello printed",
                "verify_contains": ["hello"],
                "verify_not_contains": [],
                "expect_exit_code": 0,
            },
        ],
        "verification": [
            {
                "description": "Check output",
                "method": "manual",
                "command": "",
                "args": [],
                "expect_exit_code": 0,
                "verify_contains": [],
            }
        ],
        "risks": [],
        "estimated_complexity": "simple",
        "notes": "Test",
    })


# ── Provider unit tests ────────────────────────────────────────────────

class TestOpenAIProvider(unittest.TestCase):
    """OpenAIPlannerProvider — unit tests with mocked HTTP."""

    def test_missing_api_key_raises(self):
        """Missing API key raises RuntimeError."""
        import os
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            provider = OpenAIPlannerProvider(api_key="", base_url="https://x.test/v1")
            with self.assertRaises(RuntimeError):
                provider.generate("sys", "user")
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved

    def test_successful_call_returns_content(self):
        """Successful HTTP call returns message content."""
        provider = OpenAIPlannerProvider(
            api_key="sk-test",
            model="gpt-4o",
            base_url="https://x.test/v1",
        )
        mock_resp = _make_mock_response({
            "choices": [{"message": {"content": "hello from LLM"}}]
        })
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = provider.generate("sys", "user")
        self.assertEqual(result, "hello from LLM")
        self.assertEqual(provider.call_count, 1)

    def test_request_url_uses_base_url(self):
        """The base URL is used in the request."""
        provider = OpenAIPlannerProvider(
            api_key="sk-test",
            model="gpt-4o",
            base_url="https://api.example.com/v2",
        )
        mock_resp = _make_mock_response({
            "choices": [{"message": {"content": "ok"}}]
        })
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            provider.generate("sys", "user")
            # Verify the URL passed to urlopen
            args, _ = mock_urlopen.call_args
            req = args[0]
            self.assertEqual(req.full_url, "https://api.example.com/v2/chat/completions")

    def test_request_includes_auth_header(self):
        """The Authorization header contains the API key."""
        provider = OpenAIPlannerProvider(
            api_key="sk-test-123",
            model="gpt-4o",
            base_url="https://x.test/v1",
        )
        mock_resp = _make_mock_response({
            "choices": [{"message": {"content": "ok"}}]
        })
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            provider.generate("sys", "user")
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.get_header("Authorization"), "Bearer sk-test-123")

    def test_request_payload_includes_messages(self):
        """The request body contains system + user messages."""
        provider = OpenAIPlannerProvider(
            api_key="sk-test",
            model="gpt-4o-mini",
            base_url="https://x.test/v1",
        )
        mock_resp = _make_mock_response({
            "choices": [{"message": {"content": "ok"}}]
        })
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            provider.generate("SYS", "USER")
            req = mock_urlopen.call_args[0][0]
            body = json.loads(req.data.decode("utf-8"))
            self.assertEqual(body["model"], "gpt-4o-mini")
            self.assertEqual(body["messages"][0]["role"], "system")
            self.assertEqual(body["messages"][0]["content"], "SYS")
            self.assertEqual(body["messages"][1]["role"], "user")
            self.assertEqual(body["messages"][1]["content"], "USER")

    def test_http_error_raises(self):
        """HTTP errors raise RuntimeError."""
        import urllib.error
        provider = OpenAIPlannerProvider(
            api_key="sk-test",
            base_url="https://x.test/v1",
        )
        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.HTTPError(
                       "https://x.test/v1/chat/completions", 500, "Server Error",
                       {}, io.StringIO("boom"))):
            with self.assertRaises(RuntimeError):
                provider.generate("sys", "user")

    def test_env_var_api_key_loaded(self):
        """OPENAI_API_KEY is loaded from environment."""
        import os
        os.environ["OPENAI_API_KEY"] = "from-env"
        try:
            provider = OpenAIPlannerProvider()
            self.assertEqual(provider.api_key, "from-env")
        finally:
            del os.environ["OPENAI_API_KEY"]


# ── End-to-end Planner integration test ────────────────────────────────

class TestPlannerWithOpenAIProvider(unittest.TestCase):
    """Planner integrates with OpenAIPlannerProvider end-to-end (offline)."""

    def test_planner_validates_real_provider_response(self):
        """Planner.plan() with OpenAI provider returns valid Plan."""
        mock_resp = _make_mock_response({
            "choices": [{"message": {"content": _valid_plan_json()}}]
        })

        provider = OpenAIPlannerProvider(
            api_key="sk-test",
            model="gpt-4o",
            base_url="https://x.test/v1",
        )
        planner = Planner(provider=provider)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = planner.plan("cuu-gioi", "Inspect the project")

        self.assertTrue(result.validation.valid, f"errors: {result.validation.errors}")
        self.assertIsNotNone(result.plan)
        self.assertEqual(result.plan.project_id, "cuu-gioi")
        self.assertEqual(len(result.plan.steps), 2)
        self.assertEqual(result.provider_name, "OpenAIPlannerProvider")

    def test_planner_malformed_response_fails_gracefully(self):
        """Planner.plan() with non-JSON response returns validation error."""
        mock_resp = _make_mock_response({
            "choices": [{"message": {"content": "this is not json"}}]
        })

        provider = OpenAIPlannerProvider(
            api_key="sk-test", base_url="https://x.test/v1",
        )
        planner = Planner(provider=provider)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = planner.plan("cuu-gioi", "Test")

        self.assertIsNone(result.plan)
        self.assertFalse(result.validation.valid)
        codes = [e.code for e in result.validation.errors]
        self.assertIn("PARSE_ERROR", codes)


# ── Mock mode still works ──────────────────────────────────────────────

class TestMockModeStillWorks(unittest.TestCase):
    """MockPlannerProvider remains the default."""

    def test_default_provider_is_mock(self):
        """Without env vars, provider is MockPlannerProvider."""
        import os
        for k in ("AGENTCORE_PLANNER_PROVIDER", "AGENTCORE_PLANNER_API_KEY",
                  "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
            os.environ.pop(k, None)
        from core.planner.planner import create_provider, MockPlannerProvider
        provider = create_provider()
        self.assertIsInstance(provider, MockPlannerProvider)


def run_tests() -> bool:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
