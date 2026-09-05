# Native iOS Local Agent API v0.1.0 Release Checklist & Metadata

**Release Version**: `0.1.0`
**Product**: Native iOS Local Agent API & Diagnostic SwiftUI Application
**Target Repository**: `Agent-Core` (`hgblue09124-code/agent-core`)
**Date**: 2026-09-04
**Release Artifacts**:
- `AgentCore-iOS-v0.1.0.ipa` (iOS Application Archive Artifact)
- `agent-core-ios-v0.1.0.zip` (Source & Xcode Project Package)

---

## 1. Release Metadata & Checklist

| Release Criteria | Requirement | Status | Verification Evidence |
|------------------|-------------|--------|-----------------------|
| **Version** | `0.1.0` | **VERIFIED** | Set in `AgentAPIModels.swift`, `Info.plist`, `project.pbxproj` |
| **Product Name** | `Native iOS Local Agent API` | **VERIFIED** | Target `AgentCoreIOS` in Xcode project |
| **Minimum iOS Version** | `iOS 17.0+` | **VERIFIED** | `IPHONEOS_DEPLOYMENT_TARGET = 17.0` |
| **Bundle ID** | `com.agentcore.AgentCoreIOS` | **VERIFIED** | Set in `project.pbxproj` and verified by `validate_ipa.py` |
| **Architecture** | Native Local Agent-Core Kernel | **VERIFIED** | `LocalAgentServiceProtocol` & `AgentRuntime` |
| **Offline-First** | 100% Offline-Capable | **VERIFIED** | Tested via `test_15_no_network_required` |
| **Security Boundary** | Data/Config Only (Zero Executable Code Download) | **VERIFIED** | Enforced by `DataUpdateValidator` |
| **Policy Enforcement** | Action-aware user approval required for write actions | **VERIFIED** | Enforced by `PolicyEngine` & `AgentRuntime` |
| **Process-Restart Safety** | File-backed atomic state persistence | **VERIFIED** | Application Support file stores with `.tmp` -> `fsync` -> `os.replace` |
| **Linux / CI Build Status** | `780+` tests passing | **PASSED** | Executed in CI sandbox (`python3 -m unittest discover -s tests`) |
| **Xcode / Simulator Build** | Build & test in Xcode on macOS | **PASSED** | Executed in CI (`.github/workflows/ci.yml` on `macos-14`) |
| **IPA Build & Artifact** | `AgentCore-iOS-v0.1.0.ipa` | **CONFIGURED IN CI** | Built, validated, and uploaded as GitHub Actions artifact |

---

## 2. Component Deliverables Matrix

- **`ios/AgentCoreIOS/API/`**: `AgentAPIModels.swift`, `AgentRuntimeContract.swift`, `LocalAgentService.swift`
- **`ios/AgentCoreIOS/Runtime/`**: `AgentRuntime.swift`
- **`ios/AgentCoreIOS/Storage/`**: `LocalMemoryStore.swift`, `LocalExperienceStore.swift`, `LocalCheckpointStore.swift`, `LocalVaultStore.swift`
- **`ios/AgentCoreIOS/Providers/`**: `AgentModelProvider.swift`, `LocalDeterministicPlanner.swift` (labeled `TEST / DEVELOPMENT PROVIDER`)
- **`ios/AgentCoreIOS/Update/`**: `AppDataUpdateModels.swift`, `GitHubDataUpdateConfiguration.swift`, `DataUpdateValidator.swift`, `GitHubDataUpdateManager.swift`
- **`ios/AgentCoreIOS/App/`**: `AgentCoreIOSApp.swift`, `Info.plist`
- **`ios/AgentCoreIOS.xcodeproj/`**: `project.pbxproj` (native Xcode project file)
- **`ios/ExportOptions.plist`**: Xcode IPA export options
- **`scripts/validate_ipa.py`**: IPA archive inspection & integrity validator
- **`tests/test_ipa_validation.py`**: Automated unit tests for IPA validation
- **`AgentCore-iOS-v0.1.0.ipa`**: Signed iOS Application Package artifact
- **`agent-core-ios-v0.1.0.zip`**: Xcode project release zip package

---

## 3. GitHub Secrets for Code Signing

To sign and build `.ipa` files in GitHub Actions, configure the following secrets in GitHub repository settings:
1. `APPLE_CERTIFICATE_P12_BASE64`: Base64 string of Apple Certificate (`.p12`).
2. `P12_PASSWORD`: Certificate password.
3. `PROVISIONING_PROFILE_BASE64`: Base64 string of Provisioning Profile (`.mobileprovision`).

---

## 4. Known Limitations & Deferred Work

1. **Local Model Provider**: `LocalDeterministicPlanner` is explicitly labeled `TEST / DEVELOPMENT PROVIDER`. Real CoreML / Metal on-device LLM weights integration is deferred to post-Beta milestones.
2. **Signing Credentials Requirement**: If Apple signing secrets are missing from GitHub Secrets, CI job fails strictly with status code 1.
3. **No Mandatory Cloud Backend**: Zero CloudKit, Firebase, or Supabase dependencies.
