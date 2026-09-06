# core/llm/__init__.py
"""Tiny→medium local GGUF catalog, download, and OpenAI-compatible providers."""

from core.llm.catalog import LLM_MODELS, ModelSpec, models_dir, spec_by_id
from core.llm.download import download_model, gguf_info, is_gguf
from core.llm.provider import ChatMessage, OpenAIChatProvider, create_chat_provider

__all__ = [
    "LLM_MODELS",
    "ModelSpec",
    "models_dir",
    "spec_by_id",
    "download_model",
    "gguf_info",
    "is_gguf",
    "ChatMessage",
    "OpenAIChatProvider",
    "create_chat_provider",
]
