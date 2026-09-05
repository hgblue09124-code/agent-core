# Agent-Core iOS Portability Audit

**Date**: 2026-09-04
**Target Architecture**: Native Full-Local Personal Agent on iOS / iPhone
**Audited Repository**: `Agent-Core` (`hgblue09124-code/agent-core`)
**Overall Portability Rating**: **HIGH**

---

## Executive Summary

An architect-level portability audit was performed on `Agent-Core` to evaluate its readiness to serve as the kernel and specification for a full-local, offline-first Personal Agent running natively on iPhone/iOS.

`Agent-Core` is already clean, platform-independent, and modular. It contains zero hardcoded cloud, web-server, or desktop-specific dependencies in its core kernel contracts.

---

## 1. Portability Classification Matrix

| Component | Current Implementation | iOS Portability | Required Action |
|-----------|------------------------|-----------------|-----------------|
| **Agent** | `core/agent.py` orchestrator pipeline (`Observe → Retrieve → Reason → Plan → Policy → Capability Dispatch → Execute → Verify → Experience → Lesson → Memory → Resume`). Pure orchestration logic. | **HIGH** | Maintain contract boundary. Bridge to native Swift runtime API via local C/Swift interface bindings. |
| **Memory** | `core/memory/` (`MemoryManager`, `MemoryStore`). File-backed JSON store in `~/.agent-core/memories/`. | **HIGH** | Map storage root to iOS App Sandbox `Application Support/AgentCore/memories/` or native SQLite. |
| **Experience** | `core/experience/` (`ExperienceEngine`, `ExperienceStore`). Atomic file-backed JSON store. | **HIGH** | Map storage root to iOS App Sandbox `Application Support/AgentCore/experiences/`. |
| **Policy** | `core/kernel/policy.py` (`PolicyEngine`, `authorize_capability`). Deterministic rules and approval checks. | **HIGH** | Zero changes required. Pure deterministic business logic with zero OS dependencies. |
| **Vault** | `core/vault/adapter.py` (`PersonalVaultAdapter`). Narrow storage adapter with local file-backed fallback. | **HIGH** | Implement `iOSKeychainVaultAdapter` / `iOSLocalVaultAdapter` using iOS Secure Enclave / Keychain for credentials. |
| **Capability** | `core/capabilities/` (`CapabilityRegistry`, `ExternalCapabilityBridge`, `GitHubCapabilityAdapter`). Abstract spec contracts. | **HIGH** | Implement native iOS device capabilities (e.g. `iOSContactsCapability`, `iOSCalendarCapability`, `iOSLocationCapability`). |
| **Persistence** | `core/runtime/checkpoint.py` (`CheckpointStore`). Atomic `.tmp` -> `fsync` -> `os.replace` file writes. | **HIGH** | Map runs directory to iOS App Sandbox `Application Support/AgentCore/runs/`. |
| **Runtime** | `core/runtime/engine.py` (`RuntimeEngine`). Stateful execution loop and checkpoint manager. | **MEDIUM** | Wrap runtime loop with iOS Background Tasks API (`BGTaskScheduler`) for suspended/background execution. |
| **Configuration** | `core/config/` (`ConfigManager`, `storage.py`). Relative storage path resolution via `AGENTCORE_STORAGE_DIR`. | **HIGH** | Set `AGENTCORE_STORAGE_DIR` to iOS App Sandbox container path during initialization. |
| **CLI** | `core/cli.py` (`agent-core` CLI entrypoint). Developer command-line tool. | **LOW** | Keep isolated in `core/cli.py`. iOS runtime bypasses CLI and calls local C/Swift native service API directly. |

---

## 2. Dependency & Coupling Analysis

### A. OS & Platform Dependencies
- **Current State**: Uses standard Python `os`, `json`, `pathlib`, `urllib.request`, `time`. Zero platform-specific GUI or OS libraries.
- **Portability**: Excellent. Runs on Linux, macOS, iOS embedded Python/PyBridge environments.

### B. Network & External Service Dependencies
- **Current State**: Network requests in `GitHubCapabilityAdapter` use standard `urllib.request`. Offline fallback mode (`mock_offline=True`) is explicitly supported.
- **Portability**: Fully offline-first compatible. Zero mandatory cloud backend.

### C. File System & Storage Assumptions
- **Current State**: Storage paths resolved via `get_storage_dir()` backed by `AGENTCORE_STORAGE_DIR` environment variable with fallback to `~/.agent-core`.
- **Portability**: Fully compatible with iOS App Sandbox directory permissions.

---

## 3. iOS Alpha Implementation Roadmap

1. **Portable Kernel Core**: `core/agent.py`, `core/kernel/`, `core/memory/`, `core/experience/`, `core/vault/`, `core/capabilities/`.
2. **Components Requiring iOS Adapters**:
   - `PersonalVaultAdapter`: Connect to iOS Keychain / Secure Enclave.
   - Capability Registry: Connect to iOS native APIs (Contacts, EventKit, Photos).
   - Background Runtime: Connect to iOS `BGTaskScheduler`.
3. **No Refactoring Required**: Core kernel architecture remains unchanged.
