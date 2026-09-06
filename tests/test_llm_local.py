#!/usr/bin/env python3
"""Local GGUF catalog, download, and OpenAI-compatible chat provider tests."""

from __future__ import annotations

import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request

from core.llm.catalog import LLM_MODELS, spec_by_id
from core.llm.download import DownloadError, download_model, gguf_info, is_gguf
from core.llm.provider import ChatMessage, OpenAIChatProvider, create_chat_provider


def write_minimal_gguf(path: Path, architecture: str = "qwen2", name: str = "toy") -> None:
    buf = bytearray()
    buf += b"GGUF"
    buf += struct.pack("<I", 3)
    buf += struct.pack("<Q", 0)
    buf += struct.pack("<Q", 2)

    def add_string(s: str) -> None:
        raw = s.encode("utf-8")
        buf.extend(struct.pack("<Q", len(raw)))
        buf.extend(raw)

    add_string("general.architecture")
    buf.extend(struct.pack("<I", 8))
    add_string(architecture)
    add_string("general.name")
    buf.extend(struct.pack("<I", 8))
    add_string(name)
    path.write_bytes(buf)


class _FakeHTTP:
    def __init__(self, payload: bytes, headers: dict | None = None):
        self._payload = payload
        self.headers = headers or {"Content-Length": str(len(payload))}

    def read(self, n: int = -1) -> bytes:
        if not self._payload:
            return b""
        if n < 0:
            data, self._payload = self._payload, b""
            return data
        data, self._payload = self._payload[:n], self._payload[n:]
        return data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestLLMCatalog(unittest.TestCase):
    def test_catalog_covers_tiny_to_medium(self):
        classes = {m.size_class for m in LLM_MODELS}
        self.assertIn("tiny", classes)
        self.assertIn("small", classes)
        self.assertIn("medium", classes)
        self.assertIsNotNone(spec_by_id("qwen25-0.5b-q4"))
        self.assertEqual(len(LLM_MODELS), 4)

    def test_gguf_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "toy.gguf"
            write_minimal_gguf(path, architecture="llama", name="fixture")
            self.assertTrue(is_gguf(path))
            info = gguf_info(path)
            self.assertEqual(info["architecture"], "llama")
            self.assertEqual(info["name"], "fixture")
            self.assertEqual(info["version"], 3)

    def test_download_from_file_like_opener(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.gguf"
            write_minimal_gguf(src)
            payload = src.read_bytes()
            spec = spec_by_id("qwen25-0.5b-q4")
            self.assertIsNotNone(spec)
            tiny = spec.__class__(
                id="toy",
                display_name="toy",
                family="toy",
                parameter_label="0B",
                size_class="tiny",
                quantization="F16",
                download_url="https://huggingface.co/example/toy.gguf",
                filename="toy.gguf",
                approximate_bytes=len(payload),
                sha256=None,
                ollama_tag="toy",
            )

            def opener(req, timeout=0):
                self.assertIsInstance(req, Request)
                return _FakeHTTP(payload)

            dest = download_model(tiny, dest_dir=Path(tmp), opener=opener)
            self.assertTrue(dest.is_file())
            self.assertTrue(is_gguf(dest))

    def test_download_rejects_host(self):
        spec = spec_by_id("qwen25-0.5b-q4")
        bad = spec.__class__(
            **{**spec.__dict__, "download_url": "https://evil.example/a.gguf", "sha256": None}
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DownloadError):
                download_model(bad, dest_dir=Path(tmp))


class TestOpenAIChatProvider(unittest.TestCase):
    def test_generate_parses_choices(self):
        payload = json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": "pong"}}]}
        ).encode()

        def opener(req, timeout=0):
            self.assertIn("/chat/completions", req.full_url)
            self.assertEqual(req.get_header("Authorization"), "Bearer sk")
            return _FakeHTTP(payload)

        provider = OpenAIChatProvider(
            provider_id="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk",
            model="gpt-4o-mini",
            opener=opener,
        )
        provider.load()
        text = provider.generate([ChatMessage(role="user", content="ping")])
        self.assertEqual(text, "pong")

    def test_create_chat_provider_xai(self):
        prev_provider = os.environ.get("AGENTCORE_PLANNER_PROVIDER")
        prev_key = os.environ.get("XAI_API_KEY")
        os.environ["AGENTCORE_PLANNER_PROVIDER"] = "xai"
        os.environ["XAI_API_KEY"] = "xai-test"
        try:
            provider = create_chat_provider("xai")
            self.assertEqual(provider.provider_id, "xai")
            self.assertIn("x.ai", provider.base_url)
        finally:
            if prev_provider is None:
                os.environ.pop("AGENTCORE_PLANNER_PROVIDER", None)
            else:
                os.environ["AGENTCORE_PLANNER_PROVIDER"] = prev_provider
            if prev_key is None:
                os.environ.pop("XAI_API_KEY", None)
            else:
                os.environ["XAI_API_KEY"] = prev_key


if __name__ == "__main__":
    unittest.main()
