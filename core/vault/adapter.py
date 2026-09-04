# core/vault/adapter.py
"""Narrow storage interface & adapter for agent-personal-vault.

Architectural Ownership:
- Core remains responsible for identity, cognition, policy, orchestration, experience, learning, and continuity.
- Personal Vault remains responsible for persistent personal data and personal context storage.
- Core does NOT duplicate or embed Vault implementation details; it communicates through this narrow interface.
"""

from __future__ import annotations

import importlib
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

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
    def is_available(self) -> bool:
        """Return True if external personal vault backend is connected and available."""
        pass


class PersonalVaultAdapter(BaseVaultAdapter):
    """Adapter bridging Agent-Core to agent-personal-vault.

    Supports optional external vault instances or auto-discovery of
    agent_personal_vault / agent_vault modules. Falls back gracefully
    to an in-memory/local storage buffer if no external Vault is present.
    """

    def __init__(self, external_vault: Optional[Any] = None):
        self._vault_client = external_vault
        self._fallback_store: dict[str, dict[str, Any]] = {}

        if self._vault_client is None:
            self._vault_client = self._auto_discover_vault()

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

        # Always update local fallback store for local resilience
        self._fallback_store[key] = {"data": data, "category": category}
        return success if self._vault_client is not None else True

    def get_status(self) -> dict[str, Any]:
        """Return diagnostic status of the vault adapter."""
        return {
            "available": self.is_available(),
            "external_vault_type": type(self._vault_client).__name__ if self._vault_client else None,
            "fallback_entries_count": len(self._fallback_store),
        }
