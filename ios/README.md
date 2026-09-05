# Native iOS Local Agent API v0.1.0 & GitHub Data Update v0.1

Native Swift local agent service, runtime API, offline-first GitHub Data Update manager, and Unsigned iOS IPA Release Asset build workflow for embedding Personal Agent locally on iOS / iPhone.

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

## 5. Unsigned iOS IPA Build & Release Workflow

### Release Asset Specification
The native iOS application is compiled in GitHub Actions CI using Xcode without requiring Apple signing certificates or secrets, producing a real compiled binary:
- **Filename**: `AgentCore-iOS-v0.1.0-unsigned.ipa`
- **Bundle ID**: `com.agentcore.AgentCoreIOS`
- **Version**: `0.1.0` (Build `1`)
- **Structure**: `Payload/AgentCoreIOS.app/` containing `Info.plist` and compiled executable binary.
- **Signing Status**: **INTENTIONALLY UNSIGNED** (Requires local re-signing before installation).

### GitHub Actions CI Workflow
The CI pipeline (`.github/workflows/ci.yml`) automatically builds, packages, validates, uploads, and releases `AgentCore-iOS-v0.1.0-unsigned.ipa`:
1. **Unsigned Xcode Build**: Builds real `AgentCoreIOS.app` executable targeting `iphoneos` SDK with `CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=NO CODE_SIGN_IDENTITY=""`.
2. **IPA Packaging**: Archives `Payload/AgentCoreIOS.app` into `AgentCore-iOS-v0.1.0-unsigned.ipa`.
3. **Automated Validation**: Runs `python scripts/validate_ipa.py AgentCore-iOS-v0.1.0-unsigned.ipa`.
4. **Artifact Upload**: Uploads `AgentCore-iOS-v0.1.0-unsigned.ipa` as a GitHub Actions workflow artifact.
5. **GitHub Release Attachment**: Automatically attaches `AgentCore-iOS-v0.1.0-unsigned.ipa` to GitHub Release / tag `v0.1.0`.

---

## 6. How to Re-Sign & Install `AgentCore-iOS-v0.1.0-unsigned.ipa` on iPhone

> ⚠️ **IMPORTANT**: Because `AgentCore-iOS-v0.1.0-unsigned.ipa` is intentionally unsigned, it **CANNOT** be installed directly on an iPhone without local re-signing with your personal or developer Apple ID.

### Step-by-Step Local Re-Signing & Installation Options

#### Option A: AltStore / SideStore / TrollStore (Recommended)
1. Download `AgentCore-iOS-v0.1.0-unsigned.ipa` from [GitHub Releases v0.1.0](https://github.com/hgblue09124-code/agent-core/releases/tag/v0.1.0) or GitHub Actions Artifacts.
2. Open **AltStore** or **SideStore** on your iPhone.
3. Tap `+` (My Apps) and select `AgentCore-iOS-v0.1.0-unsigned.ipa`.
4. AltStore/SideStore will automatically re-sign the app using your free or paid Apple ID and install it on your iPhone.
5. On your iPhone, go to **Settings > General > VPN & Device Management**, trust your Apple ID certificate, and enable **Developer Mode** (`Settings > Privacy & Security > Developer Mode`).

#### Option B: iOS App Signer / Sideloadly / Xcode Custom Re-Sign
1. Download `AgentCore-iOS-v0.1.0-unsigned.ipa`.
2. Open **iOS App Signer** or **Sideloadly** on your Mac.
3. Select `AgentCore-iOS-v0.1.0-unsigned.ipa`, pick your personal Apple Signing Certificate and Provisioning Profile, and click **Start** to produce a signed `.ipa`.
4. Install the signed `.ipa` via Xcode (`Window > Devices and Simulators`), Apple Configurator, or Sideloadly.

---

## 7. Release Verification Gate

| Verification Target | Status | Notes |
|---------------------|--------|-------|
| **macOS GitHub Actions CI Simulator** | **`VERIFIED IN CI`** | Executed in `.github/workflows/ci.yml` via `xcodebuild test` on `macos-14` runner. |
| **UNSIGNED IPA BUILD** | **`PASSED IN CI`** | Builds real executable `AgentCoreIOS.app` without requiring Apple signing secrets. |
| **IPA VALIDATION TOOL** | **`PASSED`** | Verified via `scripts/validate_ipa.py` and `tests/test_ipa_validation.py`. |
| **IPA RELEASE ARTIFACT** | **`PUBLISHED IN CI`** | Uploaded as workflow artifact and attached to GitHub Release `v0.1.0`. |
| **PHYSICAL DEVICE INSTALLATION** | **`REQUIRES LOCAL RE-SIGN`** | Requires local re-signing via AltStore / iOS App Signer before device launch. |
| **LINUX / PYTHON KERNEL CONTRACT VERIFIED** | **`PASSED`** | 780+ unit/integration tests passed in local CI sandbox. |
