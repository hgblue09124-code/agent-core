# Native iOS Local Agent API v0.1 & GitHub Data Update v0.1

Native Swift local agent service, runtime API, and offline-first GitHub Data Update manager for embedding Personal Agent locally on iOS / iPhone.

## Architecture Overview

```
SwiftUI App (App/AgentCoreIOSApp.swift)
    ↓
LocalAgentService API (API/LocalAgentService.swift)
    ↓
AgentRuntime (Runtime/AgentRuntime.swift)
    ├── Local Storage (Storage/ - Memories, Experiences, Runs, Vault)
    ├── Local Model Provider (Providers/LocalDeterministicPlanner.swift)
    └── GitHub Data Update Manager (Update/GitHubDataUpdateManager.swift)
            ↓ (Data/Config Only - NO Swift/Executable Code)
        GitHub Repository (manifest.json)
```

---

## 1. Action-Aware Policy & Security Boundaries

`AgentRuntime` and `PolicyEngine` enforce strict action-aware capability authorization:

- **READ Actions** (`get_repo`, `get_issue`, `list_issues`, `get`, `read`, `list`, `search`, `status`, `inspect`, `fetch`):
  - **Allowed without explicit user approval** (`userApproved = false`).
- **MUTATING / WRITE Actions** (`create_issue_comment`, `create`, `update`, `delete`, `post`, `put`, `patch`, `write`, `comment`, `merge`, `close`):
  - **Strictly require `userApproved = true`**.
  - Unapproved requests return **`DENIED`** and downstream execution is strictly blocked.

---

## 2. GitHub Data Update v0.1

`GitHubDataUpdateManager` (`ios/AgentCoreIOS/Update/`) provides offline-first, atomic data and configuration updates for local agent prompts, capability metadata, and configuration sets.

### Manifest Schema (`AppDataManifest`)
```json
{
  "schemaVersion": 1,
  "dataVersion": "2026.09.05.001",
  "minimumClientVersion": "0.1.0",
  "files": [
    {
      "path": "agent-config/default.json",
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "size": 4821
    }
  ]
}
```

### Update Lifecycle & Integrity Rules
1. **Manifest Comparison**: Fetch remote manifest and compare `dataVersion` with `installedDataVersion`.
2. **Path Safety Check**: Rejects absolute paths (`/etc/passwd`), path traversal (`..`), and forbidden file extensions (`.swift`, `.dylib`, `.so`, `.a`, `.sh`, `.bin`, `.exec`).
3. **Download to Staging**: Downloads updated files into `<App_Sandbox>/Application Support/AgentCore/data/staging/`.
4. **Integrity Validation**: Validates exact file size and computed SHA-256 checksum against manifest requirements.
5. **Atomic Commit / Swap**: Moves active data to backup, swaps staging to active, and removes backup on commit.
6. **Automatic Rollback**: Restores previous active dataset from backup if download or validation fails.
7. **Offline-First Resilience**: If GitHub is unreachable, Agent-Core continues operating normally using the last known-good local data.

---

## 3. Strict Security & Executable Code Boundary

> **SECURITY INVARIANT**: GitHub Data Update v0.1 downloads **DATA AND CONFIGURATION ONLY** (JSON, configuration, prompts, policies, capability metadata).
>
> It **MUST NOT** download, compile, or execute:
> - Swift source code
> - Dynamic native libraries (`.dylib`, `.so`)
> - Executable binaries or scripts
>
> All binary application updates remain the exclusive responsibility of Apple App Store / TestFlight releases.

---

## 4. Public API Contract (`LocalAgentServiceProtocol`)

```swift
public protocol LocalAgentServiceProtocol: Sendable {
    func run(goal: String, userApproved: Bool) async -> AgentRunResult
    func resume(runId: String) async -> AgentRunResult
    func remember(key: String, value: String) async -> MemoryResult
    func retrieve(query: String) async -> [MemoryItem]
    func updateMemory(key: String, value: String, userApproved: Bool) async -> MemoryResult
    func listCapabilities() async -> [Capability]
    func executeCapability(capabilityId: String, input: [String: String], userApproved: Bool) async -> CapabilityResult
    func getRun(runId: String) async -> AgentRunResult?
    func getExperience() async -> [Experience]
    func health() async -> AgentHealth
}
```

---

## 5. Result Status Semantics

- **`SUCCESS`**: Operation completed and verified.
- **`FAILED`**: Execution error, network failure, or step verification failure.
- **`DENIED`**: PolicyEngine rejected operation due to missing user approval (`userApproved = false`).
- **`NOT_EXECUTED`**: Capability required live external credentials/network which were absent.

---

## 6. Xcode Setup Instructions

1. Open Xcode on macOS.
2. Create or open **iOS App** target `AgentCoreIOS` (SwiftUI / Swift).
3. Drag and drop `ios/AgentCoreIOS/` into the Xcode project navigator.
4. Drag and drop `ios/Tests/` into the Xcode Test Target navigator.
5. Build and run on iOS Simulator or physical iPhone (`⌘R`).
6. Run tests via **Product > Test** (`⌘U`).

---

## 7. Release Verification Gate

| Target | Status |
|--------|--------|
| **SIMULATOR VERIFIED** | **`NOT YET EXECUTED`** (Linux CI sandbox lacks Xcode toolchain) |
| **DEVICE VERIFIED** | **`NOT YET EXECUTED`** (Requires attached physical iPhone) |
| **LINUX / PYTHON KERNEL CONTRACT VERIFIED** | **`PASSED`** (750+ tests passed) |
| **API & DATA UPDATE CONTRACT MIRROR VERIFIED** | **`PASSED`** (`tests/test_ios_native_api_contract.py` & `tests/test_github_data_update_contract.py`) |
