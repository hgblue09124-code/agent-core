# core/vault/adapter.py
"""Narrow storage interface & adapter for agent-personal-vault.

Architectural Ownership:
- Core remains responsible for identity, cognition, policy, orchestration, experience, learning, and continuity.
- Personal Vault remains responsible for persistent personal data and personal context storage.
- Core does NOT duplicate or embed Vault implementation details; it communicates through this narrow interface.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from core.config.storage import get_storage_dir

logger = logging.getLogger(__name__)


class BaseVaultAdapter(ABC):
    """Abstract base adapter contract for personal vault integration."""

    @abstractmethod
    def retrieve_context(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieve relevant personal context entries for a given query."""
        pass

    @abstractmethod
    def store_context(self, key: str, data: dict[str, Any], category: str = "user_preference") -> bool:
        """Store or update a personal data entry in the vault."""
        pass

    @abstractmethod
    def delete_context(self, key: str) -> bool:
        """Remove a personal context entry from the vault."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if external personal vault backend is connected and available."""
        pass


class PersonalVaultAdapter(BaseVaultAdapter):
    """Adapter bridging Agent-Core to agent-personal-vault.

    Supports optional external vault instances or auto-discovery of
    agent_personal_vault / agent_vault modules. Falls back gracefully
    to an atomic file-backed local storage buffer if no external Vault is present.
    """

    def __init__(self, external_vault: Optional[Any] = None, storage_dir: Optional[str] = None):
        self._vault_client = external_vault
        if storage_dir:
            self._vault_dir = Path(storage_dir)
        else:
            self._vault_dir = get_storage_dir("vault")
        self._vault_dir.mkdir(parents=True, exist_ok=True)
        self._fallback_path = self._vault_dir / "fallback_vault.json"

        self._fallback_store: dict[str, dict[str, Any]] = self._load_fallback_store()

        if self._vault_client is None:
            self._vault_client = self._auto_discover_vault()

    def _load_fallback_store(self) -> dict[str, dict[str, Any]]:
        """Load local fallback vault data from disk."""
        if self._fallback_path.exists():
            try:
                with open(self._fallback_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(f"Failed to load fallback vault store: {exc}")
        return {}

    def _save_fallback_store(self) -> None:
        """Atomic write fallback store to disk."""
        tmp = self._vault_dir / "fallback_vault.json.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._fallback_store, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._fallback_path)
        except Exception as exc:
            logger.error(f"Failed to save fallback vault store: {exc}")

    def _auto_discover_vault(self) -> Optional[Any]:
        """Attempt to dynamically import external agent-personal-vault package."""
        for mod_name in ("agent_personal_vault", "agent_vault", "personal_vault"):
            try:
                mod = importlib.import_module(mod_name)
                if hasattr(mod, "VaultClient"):
                    return mod.VaultClient()
                if hasattr(mod, "PersonalVault"):
                    return mod.PersonalVault()
                return mod
            except ImportError:
                continue
            except Exception as exc:
                logger.warning(f"Error initializing discovered vault module '{mod_name}': {exc}")
        return None

    def is_available(self) -> bool:
        """Check if an external Vault implementation is available."""
        if self._vault_client is not None:
            if hasattr(self._vault_client, "is_available"):
                try:
                    return bool(self._vault_client.is_available())
                except Exception:
                    return False
            return True
        return False

    def retrieve_context(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieve personal context matching query."""
        if self._vault_client is not None:
            try:
                if hasattr(self._vault_client, "retrieve_context"):
                    return self._vault_client.retrieve_context(query=query, limit=limit)
                if hasattr(self._vault_client, "search"):
                    return self._vault_client.search(query=query, limit=limit)
                if hasattr(self._vault_client, "get"):
                    res = self._vault_client.get(query)
                    return [res] if res else []
            except Exception as exc:
                logger.error(f"External Vault retrieval exception: {exc}")
                # Vault failure must not crash Core — fall back to local buffer
                pass

        # Fallback query matching over local buffer
        q_lower = query.lower()
        results: list[dict[str, Any]] = []
        for key, entry in self._fallback_store.items():
            content_str = str(entry.get("data", "")).lower() + " " + key.lower()
            if any(term in content_str for term in q_lower.split()):
                results.append({"key": key, "category": entry.get("category"), "data": entry.get("data")})
            if len(results) >= limit:
                break
        return results

    def store_context(self, key: str, data: dict[str, Any], category: str = "user_preference") -> bool:
        """Store personal context item in vault."""
        success = False
        if self._vault_client is not None:
            try:
                if hasattr(self._vault_client, "store_context"):
                    success = bool(self._vault_client.store_context(key=key, data=data, category=category))
                elif hasattr(self._vault_client, "put"):
                    success = bool(self._vault_client.put(key=key, value=data))
            except Exception as exc:
                logger.error(f"External Vault storage exception: {exc}")
                success = False

        # Always update local fallback store and persist to disk for local resilience
        self._fallback_store[key] = {"data": data, "category": category}
        self._save_fallback_store()
        return success if self._vault_client is not None else True

    def delete_context(self, key: str) -> bool:
        """Remove a personal context entry from vault."""
        removed = False
        if self._vault_client is not None and hasattr(self._vault_client, "delete_context"):
            try:
                removed = bool(self._vault_client.delete_context(key=key))
            except Exception as exc:
                logger.error(f"External Vault delete exception: {exc}")
        if key in self._fallback_store:
            del self._fallback_store[key]
            self._save_fallback_store()
            removed = True
        return removed

    def get_status(self) -> dict[str, Any]:
        """Return diagnostic status of the vault adapter."""
        return {
            "available": self.is_available(),
            "external_vault_type": type(self._vault_client).__name__ if self._vault_client else None,
            "fallback_entries_count": len(self._fallback_store),
        }
