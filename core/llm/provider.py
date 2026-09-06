# core/llm/provider.py
"""OpenAI-compatible chat client + optional llama-cpp GGUF backend."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from core.llm.catalog import spec_by_id
from core.llm.download import models_dir


@dataclass
class ChatMessage:
    role: str
    content: str


class OpenAIChatProvider:
    """Chat Completions client for OpenAI, OpenRouter, xAI, Ollama, llama-server."""

    def __init__(
        self,
        *,
        provider_id: str,
        base_url: str,
        api_key: str = "",
        model: str,
        extra_headers: Optional[dict] = None,
        opener=None,
        timeout: int = 120,
    ):
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.extra_headers = extra_headers or {}
        self._opener = opener or urllib.request.urlopen
        self.timeout = timeout
        self._loaded = False

    def load(self) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        system: str = "",
        max_tokens: int = 256,
        temperature: Optional[float] = None,
    ) -> str:
        if not self._loaded:
            raise RuntimeError("Provider not loaded")
        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend({"role": m.role, "content": m.content} for m in messages)
        body = {
            "model": self.model,
            "messages": payload_messages,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if temperature is not None:
            body["temperature"] = temperature
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Agent-Core/0.2.0",
            **self.extra_headers,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with self._opener(req, timeout=self.timeout) as resp:
                parsed = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{self.provider_id} generate failed: {exc}") from exc
        choices = parsed.get("choices") or []
        if not choices:
            raise RuntimeError(f"{self.provider_id} returned no choices")
        message = choices[0].get("message") or {}
        return str(message.get("content") or "")


class GGUFChatProvider:
    """Optional llama-cpp-python backend for a downloaded GGUF file."""

    def __init__(self, model_id: str, dest_dir=None):
        spec = spec_by_id(model_id)
        if spec is None:
            raise RuntimeError(f"Unknown model id {model_id}")
        self.spec = spec
        self.path = models_dir(dest_dir) / spec.filename
        self._llm = None
        self.provider_id = f"gguf:{model_id}"
        self._loaded = False

    def load(self) -> None:
        if not self.path.is_file():
            raise RuntimeError(f"GGUF not downloaded: {self.path}")
        try:
            from llama_cpp import Llama  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python is not installed. Use provider=local (Ollama) "
                "or pip install llama-cpp-python."
            ) from exc
        self._llm = Llama(model_path=str(self.path), n_ctx=2048, verbose=False)
        self._loaded = True

    def unload(self) -> None:
        self._llm = None
        self._loaded = False

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        system: str = "",
        max_tokens: int = 256,
        temperature: Optional[float] = 0.2,
    ) -> str:
        if not self._loaded or self._llm is None:
            raise RuntimeError("Provider not loaded")
        chat = []
        if system:
            chat.append({"role": "system", "content": system})
        chat.extend({"role": m.role, "content": m.content} for m in messages)
        out = self._llm.create_chat_completion(
            messages=chat,
            max_tokens=max_tokens,
            temperature=temperature or 0.2,
        )
        return out["choices"][0]["message"]["content"]


def create_chat_provider(
    provider: Optional[str] = None,
    *,
    opener=None,
) -> object:
    name = (provider or os.environ.get("AGENTCORE_PLANNER_PROVIDER") or "mock").lower()
    if name == "gguf":
        model_id = os.environ.get("AGENTCORE_GGUF_MODEL", "qwen25-0.5b-q4")
        return GGUFChatProvider(model_id)
    if name in ("openai", "openrouter", "xai", "local", "ollama", "custom"):
        defaults = {
            "openai": ("https://api.openai.com/v1", "gpt-4o-mini", os.environ.get("OPENAI_API_KEY", "")),
            "openrouter": (
                "https://openrouter.ai/api/v1",
                os.environ.get("AGENTCORE_PLANNER_MODEL", "openai/gpt-4o-mini"),
                os.environ.get("AGENTCORE_PLANNER_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", ""),
            ),
            "xai": (
                "https://api.x.ai/v1",
                os.environ.get("AGENTCORE_PLANNER_MODEL", "grok-3-mini"),
                os.environ.get("XAI_API_KEY", "") or os.environ.get("AGENTCORE_PLANNER_API_KEY", ""),
            ),
            "local": (
                os.environ.get("AGENTCORE_PLANNER_BASE_URL", "http://127.0.0.1:11434/v1"),
                os.environ.get("AGENTCORE_PLANNER_MODEL", "qwen2.5:0.5b"),
                os.environ.get("AGENTCORE_PLANNER_API_KEY", ""),
            ),
            "ollama": (
                os.environ.get("AGENTCORE_PLANNER_BASE_URL", "http://127.0.0.1:11434/v1"),
                os.environ.get("AGENTCORE_PLANNER_MODEL", "qwen2.5:0.5b"),
                os.environ.get("AGENTCORE_PLANNER_API_KEY", ""),
            ),
            "custom": (
                os.environ.get("AGENTCORE_PLANNER_BASE_URL", "http://127.0.0.1:8080/v1"),
                os.environ.get("AGENTCORE_PLANNER_MODEL", "local-model"),
                os.environ.get("AGENTCORE_PLANNER_API_KEY", ""),
            ),
        }
        base, model, key = defaults[name]
        base = os.environ.get("AGENTCORE_PLANNER_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or base
        extra = {}
        if name == "openrouter":
            extra = {
                "HTTP-Referer": "https://github.com/hgblue09124-code/agent-core",
                "X-Title": "Agent-Core",
            }
        return OpenAIChatProvider(
            provider_id=name,
            base_url=base,
            api_key=key,
            model=model,
            extra_headers=extra,
            opener=opener,
        )
    raise RuntimeError(f"Unknown chat provider {name}")

