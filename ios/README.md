# Native iOS Local Agent API v0.1.0

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

## 1. Project Directory Structure

```
ios/
├── AgentCoreIOS/
│   ├── API/
│   │   ├── AgentAPIModels.swift
│   │   ├── AgentRuntimeContract.swift
│   │   └── LocalAgentService.swift
│   ├── App/
│   │   ├── AgentCoreIOSApp.swift
│   │   └── Info.plist
│   ├── Providers/
│   │   ├── AgentModelProvider.swift
│   │   └── LocalDeterministicPlanner.swift
│   ├── Runtime/
│   │   └── AgentRuntime.swift
│   ├── Storage/
│   │   ├── LocalCheckpointStore.swift
│   │   ├── LocalExperienceStore.swift
│   │   ├── LocalMemoryStore.swift
│   │   └── LocalVaultStore.swift
│   └── Update/
│       ├── AppDataUpdateModels.swift
│       ├── DataUpdateValidator.swift
│       ├── GitHubDataUpdateConfiguration.swift
│       └── GitHubDataUpdateManager.swift
├── AgentCoreIOS.xcodeproj/
│   └── project.pbxproj
├── Tests/
│   └── LocalAgentServiceTests.swift
└── README.md
```

---

## 2. Action-Aware Policy & Security Boundaries

`AgentRuntime` and `PolicyEngine` enforce strict action-aware capability authorization:

- **READ Actions** (`get_repo`, `get_issue`, `list_issues`, `get`, `read`, `list`, `search`, `status`, `inspect`, `fetch`):
  - **Allowed without explicit user approval** (`userApproved = false`).
- **MUTATING / WRITE Actions** (`create_issue_comment`, `create`, `update`, `delete`, `post`, `put`, `patch`, `write`, `comment`, `merge`, `close`):
  - **Strictly require `userApproved = true`**.
  - Unapproved requests return **`DENIED`** and downstream execution is strictly blocked.

---

## 3. GitHub Data Update v0.1

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
1. **Manifest Comparison**: Fetch remote manifest and compare `dataVersion` with `installedDataVersion`. Version downgrade or same-version reinstallation is safely rejected as a no-op.
2. **Path Safety Check**: Rejects absolute paths (`/etc/passwd`), path traversal (`..`), and forbidden file extensions (`.swift`, `.dylib`, `.so`, `.a`, `.sh`, `.bin`, `.exec`).
3. **Delta Preservation**: Copies existing active dataset snapshot into `staging/` before applying manifest updates, preserving unchanged local files.
4. **Integrity Validation**: Validates exact file size and computed SHA-256 checksum against manifest requirements.
5. **Atomic Commit / Swap**: Moves active data to backup, swaps staging to active, and removes backup on commit.
6. **Automatic Rollback**: Restores previous active dataset from backup if download or validation fails.
7. **Offline-First Resilience**: If GitHub is unreachable, Agent-Core continues operating normally using the last known-good local data.

---

## 4. Strict Security & Executable Code Boundary

> **SECURITY INVARIANT**: GitHub Data Update v0.1 downloads **DATA AND CONFIGURATION ONLY** (JSON, configuration, prompts, policies, capability metadata).
>
> It **MUST NOT** download, compile, or execute:
> - Swift source code
> - Dynamic native libraries (`.dylib`, `.so`)
> - Executable binaries or scripts
>
> All binary application updates remain the exclusive responsibility of Apple App Store / TestFlight releases.

---

## 5. How to Open, Build, and Run in Xcode

### Requirements
- **macOS**: 14.0+
- **Xcode**: 15.0+
- **Target iOS Version**: iOS 17.0+

### Step-by-Step Instructions

1. **Open Project**:
   Double click `ios/AgentCoreIOS.xcodeproj` in Finder or run in Terminal:
   ```bash
   open ios/AgentCoreIOS.xcodeproj
   ```

2. **Select Scheme & Device / Simulator**:
   - Scheme: `AgentCoreIOS`
   - Target Destination: Select **iPhone 15 Pro (Simulator)** or **iPhone 16 Pro (Simulator)**.
   - For physical iPhone testing: Connect iPhone via USB/Wi-Fi, select device in destination menu, and configure signing team in **Signing & Capabilities**.

3. **Build & Run App (`⌘R`)**:
   Press **Product > Run** (`⌘R`). The diagnostic app launches with:
   - Header badge: **`LOCAL ONLY`**
   - Action buttons: `[Run]`, `[Remember]`, `[Retrieve]`, `[Resume]`, `[Health]`, `[Check Updates]`, `[Sync Now]`

4. **Run Native Unit & Integration Tests (`⌘U`)**:
   Press **Product > Test** (`⌘U`). Xcode executes the 15-test suite in `LocalAgentServiceTests.swift`.

---

## 6. Release Verification Gate

| Verification Target | Status | Notes |
|---------------------|--------|-------|
| **SIMULATOR VERIFIED** | **`NOT YET EXECUTED`** | Requires Xcode on macOS developer environment. |
| **PHYSICAL DEVICE VERIFIED** | **`NOT YET EXECUTED`** | Requires owner's physical iPhone & signing certificate. |
| **LINUX / PYTHON KERNEL CONTRACT VERIFIED** | **`PASSED`** | 770+ unit/integration tests passed in local CI sandbox. |
| **API & DATA UPDATE CONTRACT MIRROR VERIFIED** | **`PASSED`** | Verified via `tests/test_ios_native_api_contract.py` & `tests/test_github_data_update_contract.py`. |
