# core/llm/catalog.py
"""Tiny → medium GGUF catalog (weights only). Shared ids with iOS ModelCatalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config.storage import get_storage_dir


@dataclass(frozen=True)
class ModelSpec:
    id: str
    display_name: str
    family: str
    parameter_label: str
    size_class: str  # tiny | small | medium
    quantization: str
    download_url: str
    filename: str
    approximate_bytes: int
    sha256: Optional[str]
    ollama_tag: str


LLM_MODELS: list[ModelSpec] = [
    ModelSpec(
        id="qwen25-0.5b-q4",
        display_name="Qwen2.5 0.5B Instruct",
        family="Qwen2.5",
        parameter_label="0.5B",
        size_class="tiny",
        quantization="Q4_K_M",
        download_url="https://huggingface.co/bartowski/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf",
        filename="Qwen2.5-0.5B-Instruct-Q4_K_M.gguf",
        approximate_bytes=397_808_192,
        sha256="6eb923e7d26e9cea28811e1a8e852009b21242fb157b26149d3b188f3a8c8653",
        ollama_tag="qwen2.5:0.5b",
    ),
    ModelSpec(
        id="llama32-1b-q4",
        display_name="Llama 3.2 1B Instruct",
        family="Llama-3.2",
        parameter_label="1B",
        size_class="tiny",
        quantization="Q4_K_M",
        download_url="https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        filename="Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        approximate_bytes=771_000_000,
        sha256=None,
        ollama_tag="llama3.2:1b",
    ),
    ModelSpec(
        id="llama32-3b-q4",
        display_name="Llama 3.2 3B Instruct",
        family="Llama-3.2",
        parameter_label="3B",
        size_class="small",
        quantization="Q4_K_M",
        download_url="https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        filename="Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        approximate_bytes=2_020_000_000,
        sha256=None,
        ollama_tag="llama3.2:3b",
    ),
    ModelSpec(
        id="phi35-mini-q4",
        display_name="Phi-3.5 Mini Instruct",
        family="Phi-3.5",
        parameter_label="3.8B",
        size_class="medium",
        quantization="Q4_K_M",
        download_url="https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf",
        filename="Phi-3.5-mini-instruct-Q4_K_M.gguf",
        approximate_bytes=2_400_000_000,
        sha256=None,
        ollama_tag="phi3.5:3.8b",
    ),
]


def spec_by_id(model_id: str) -> Optional[ModelSpec]:
    for spec in LLM_MODELS:
        if spec.id == model_id:
            return spec
    return None


def models_dir(root: Optional[Path] = None) -> Path:
    base = Path(root) if root else Path(get_storage_dir())
    return base / "models"
