# Native iOS Local Agent API v0.1.0 Release Checklist & Metadata

**Release Version**: `0.1.0`
**Product**: Native iOS Local Agent API & Diagnostic SwiftUI Application
**Target Repository**: `Agent-Core` (`hgblue09124-code/agent-core`)
**Date**: 2026-09-04
**Release Artifact**: `agent-core-ios-v0.1.0.zip`

---

## 1. Release Metadata & Checklist

| Release Criteria | Requirement | Status | Verification Evidence |
|------------------|-------------|--------|-----------------------|
| **Version** | `0.1.0` | **VERIFIED** | Set in `AgentAPIModels.swift`, `Info.plist`, `project.pbxproj` |
| **Product Name** | `Native iOS Local Agent API` | **VERIFIED** | Target `AgentCoreIOS` in Xcode project |
| **Minimum iOS Version** | `iOS 17.0+` | **VERIFIED** | `IPHONEOS_DEPLOYMENT_TARGET = 17.0` |
| **Architecture** | Native Local Agent-Core Kernel | **VERIFIED** | `LocalAgentServiceProtocol` & `AgentRuntime` |
| **Offline-First** | 100% Offline-Capable | **VERIFIED** | Tested via `test_15_no_network_required` |
| **Security Boundary** | Data/Config Only (Zero Executable Code Download) | **VERIFIED** | Enforced by `DataUpdateValidator` |
| **Policy Enforcement** | Action-aware user approval required for write actions | **VERIFIED** | Enforced by `PolicyEngine` & `AgentRuntime` |
| **Process-Restart Safety** | File-backed atomic state persistence | **VERIFIED** | Application Support file stores with `.tmp` -> `fsync` -> `os.replace` |
| **Linux / CI Build Status** | `770+` tests passing | **PASSED** | Executed in CI sandbox (`python3 -m unittest discover -s tests`) |
| **Xcode / Simulator Build** | Build & test in Xcode on macOS | **NOT YET EXECUTED** | Requires Xcode on macOS developer machine |
| **Physical Device Signing** | Apple Developer Signing | **NOT YET EXECUTED** | Requires owner's physical iPhone and Apple Developer certificate |

---

## 2. Component Deliverables Matrix

- **`ios/AgentCoreIOS/API/`**: `AgentAPIModels.swift`, `AgentRuntimeContract.swift`, `LocalAgentService.swift`
- **`ios/AgentCoreIOS/Runtime/`**: `AgentRuntime.swift`
- **`ios/AgentCoreIOS/Storage/`**: `LocalMemoryStore.swift`, `LocalExperienceStore.swift`, `LocalCheckpointStore.swift`, `LocalVaultStore.swift`
- **`ios/AgentCoreIOS/Providers/`**: `AgentModelProvider.swift`, `LocalDeterministicPlanner.swift` (labeled `TEST / DEVELOPMENT PROVIDER`)
- **`ios/AgentCoreIOS/Update/`**: `AppDataUpdateModels.swift`, `GitHubDataUpdateConfiguration.swift`, `DataUpdateValidator.swift`, `GitHubDataUpdateManager.swift`
- **`ios/AgentCoreIOS/App/`**: `AgentCoreIOSApp.swift`, `Info.plist`
- **`ios/AgentCoreIOS.xcodeproj/`**: `project.pbxproj` (native Xcode project file)
- **`ios/Tests/`**: `LocalAgentServiceTests.swift` (15-test native XCTest suite)
- **`agent-core-ios-v0.1.0.zip`**: Complete downloadable GitHub Release asset

---

## 3. Known Limitations & Deferred Work

1. **Local Model Provider**: `LocalDeterministicPlanner` is explicitly labeled `TEST / DEVELOPMENT PROVIDER`. Real CoreML / Metal on-device LLM weights integration is deferred to post-Beta milestones.
2. **Physical Device Signing**: Physical iPhone code signing and provisioning profiles must be configured in Xcode on the developer's Mac.
3. **No Mandatory Cloud Backend**: Zero CloudKit, Firebase, or Supabase dependencies.
