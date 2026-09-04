# core/vault/__init__.py
"""Personal Vault interface and narrow storage adapter module for Agent-Core."""

from core.vault.adapter import BaseVaultAdapter, PersonalVaultAdapter

__all__ = ["BaseVaultAdapter", "PersonalVaultAdapter"]
