# Native iOS Local Agent API v0.1.0 & GitHub Data Update v0.1

Native Swift local agent service, runtime API, offline-first GitHub Data Update manager, and iOS IPA Release Asset build workflow for embedding Personal Agent locally on iOS / iPhone.

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
├── ExportOptions.plist
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

## 3. GitHub Data Update v0.1 (Real Data & Configuration Sync)

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

---

## 4. How to Open, Build, and Test in Xcode

### Requirements
- **macOS**: 14.0+
- **Xcode**: 15.0+
- **Target iOS Version**: iOS 17.0+

### Step-by-Step Instructions

1. **Open Project**:
   ```bash
   open ios/AgentCoreIOS.xcodeproj
   ```

2. **Select Scheme & Destination**:
   - Scheme: `AgentCoreIOS`
   - Destination: **iPhone 15 Pro (Simulator)**

3. **Build & Run App (`⌘R`)**:
   Press **Product > Run** (`⌘R`).

4. **Run Unit Tests via Command Line**:
   ```bash
   xcodebuild test \
     -project ios/AgentCoreIOS.xcodeproj \
     -scheme AgentCoreIOS \
     -destination 'platform=iOS Simulator,name=iPhone 15 Pro,OS=latest' \
     CODE_SIGNING_REQUIRED=NO \
     CODE_SIGNING_ALLOWED=NO
   ```

---

## 5. iOS IPA Build, Signing, and GitHub Release Publishing

### Release Asset Specification
The native iOS app is built and packaged into an installable `.ipa` archive:
- **Filename**: `AgentCore-iOS-v0.1.0.ipa`
- **Bundle ID**: `com.agentcore.ios`
- **Version**: `0.1.0` (Build `1`)
- **Structure**: `Payload/AgentCoreIOS.app/` containing `Info.plist` and executable binary.

### GitHub Actions CI Workflow
The CI pipeline (`.github/workflows/ci.yml`) automatically builds, validates, and publishes `AgentCore-iOS-v0.1.0.ipa`:
1. **Signing Check**: Verifies if required Apple Signing Secrets are set in GitHub.
2. **Keychain & Provisioning Setup**: Imports `.p12` certificate and `.mobileprovision` profile.
3. **Archive & Export**: Runs `xcodebuild archive` and `xcodebuild -exportArchive -exportOptionsPlist ios/ExportOptions.plist`.
4. **Automated IPA Validation**: Runs `python scripts/validate_ipa.py AgentCore-iOS-v0.1.0.ipa`.
5. **Artifact Upload**: Uploads `AgentCore-iOS-v0.1.0.ipa` as a GitHub Actions artifact.
6. **GitHub Release Attachment**: Automatically attaches `AgentCore-iOS-v0.1.0.ipa` to GitHub Release / tag `v0.1.0` using `softprops/action-gh-release@v2`.

### Required GitHub Secrets for Code Signing
To enable direct IPA creation and signing in GitHub Actions, add the following secrets in **Settings > Secrets and variables > Actions**:
- `APPLE_CERTIFICATE_P12_BASE64`: Base64-encoded Apple Development or Distribution `.p12` certificate.
- `P12_PASSWORD`: Password for the `.p12` certificate file.
- `PROVISIONING_PROFILE_BASE64`: Base64-encoded `.mobileprovision` file matching `com.agentcore.ios`.

> **Note on Blocker**: If these secrets are missing, CI will log an explicit blocker warning and skip IPA export. CI will **NOT** create a fake or corrupt `.ipa` file.

---

## 6. How to Download & Install `AgentCore-iOS-v0.1.0.ipa` on iPhone

### Option A: Sideloading via AltStore / SideStore / TrollStore (Developer / Ad-Hoc)
1. Download `AgentCore-iOS-v0.1.0.ipa` from [GitHub Releases v0.1.0](https://github.com/hgblue09124-code/agent-core/releases/tag/v0.1.0) or Actions Artifacts.
2. Open AltStore / SideStore on your iPhone.
3. Tap `+` and select `AgentCore-iOS-v0.1.0.ipa`.
4. Enable **Developer Mode** on iOS (`Settings > Privacy & Security > Developer Mode`).

### Option B: Apple TestFlight / Enterprise / Ad-Hoc Deployment
1. Download `AgentCore-iOS-v0.1.0.ipa` signed with your team's Ad-Hoc / Enterprise provisioning profile.
2. Install via Apple Configurator 2, Xcode (`Window > Devices and Simulators`), or MDM provider.

---

## 7. Release Verification Gate

| Verification Target | Status | Notes |
|---------------------|--------|-------|
| **macOS GitHub Actions CI Simulator** | **`VERIFIED IN CI`** | Executed in `.github/workflows/ci.yml` via `xcodebuild test` on `macos-14` runner. |
| **IPA VALIDATION TOOL** | **`PASSED`** | Verified via `scripts/validate_ipa.py` and `tests/test_ipa_validation.py`. |
| **IPA RELEASE ASSET** | **`READY IN CI`** | Configured in `.github/workflows/ci.yml` with artifact & release upload. |
| **PHYSICAL DEVICE VERIFIED** | **`PENDING SIGNING`** | Requires owner's Apple Developer signing credentials set in GitHub Secrets. |
| **LINUX / PYTHON KERNEL CONTRACT VERIFIED** | **`PASSED`** | 780 unit/integration tests passed in local CI sandbox. |
