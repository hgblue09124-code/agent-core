# Native iOS Local Agent API v0.1

Native Swift local agent service and runtime API for embedding Personal Agent locally on iOS / iPhone.

## Architecture

```
SwiftUI App (App/AgentCoreIOSApp.swift)
    ↓
LocalAgentService API (API/LocalAgentService.swift)
    ↓
AgentRuntime (Runtime/AgentRuntime.swift)
    ↓
Local Memory / Vault / Experience / Checkpoint Stores (Storage/)
    ↓
Local Model Provider (Providers/LocalDeterministicPlanner.swift)
```

---

## 1. Public API Contract (`LocalAgentServiceProtocol`)

The primary entrypoint for the native iOS application is `LocalAgentService` (`ios/AgentCoreIOS/API/LocalAgentService.swift`), implementing `LocalAgentServiceProtocol`:

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

## 2. Result Models & Status Semantics

All result models are `Codable` and `Sendable`.

### Status Enum
- **`SUCCESS`**: Operation completed and passed verification.
- **`FAILED`**: Execution error, network failure, or step verification failure.
- **`DENIED`**: PolicyEngine rejected operation due to missing user approval (`userApproved = false`) or read-only restriction.
- **`NOT_EXECUTED`**: Capability required live external credentials/network which were absent.

---

## 3. Policy & Security Boundaries

- **READ Operations**: Allowed without explicit user approval.
- **WRITE / MUTATING Operations**:
  - `userApproved == false` → **`DENIED`** (downstream actions strictly blocked).
  - `userApproved == true` → Authorized for execution.
- **PolicyEngine Authority**: Policy cannot be bypassed inside the iOS layer.

---

## 4. Local Persistence Guarantees

All local state persists in the iOS App Sandbox container:

```
Application Support/
    AgentCore/
        memories/       # LocalMemoryStore
        experiences/    # LocalExperienceStore
        runs/           # LocalCheckpointStore
        vault/          # LocalVaultStore
```

### Persistence Features
- **Atomic File Writes**: Atomic `.tmp` -> `fsync` -> `os.replace` file writes prevent state corruption.
- **Process Restart Safety**: State, experiences, and checkpoints survive app suspension, termination, and relaunch.
- **Zero Cloud Requirement**: 100% offline-first local storage.

---

## 5. Model Provider Abstraction

- **`LocalDeterministicPlanner`**: Explicitly labeled **`TEST / DEVELOPMENT PROVIDER`**. Never describes deterministic outputs as real AI reasoning.
- **`ModelProviderStatus`**:
  - `.realLocalModel`: Native on-device LLM runtime (e.g. CoreML, llama.cpp, Metal).
  - `.deterministicTest`: Development test planner.
  - `.unavailable`: On-device model runtime unavailable.

---

## 6. Xcode Setup Instructions

To build and run the native iOS app in Xcode:

1. Open Xcode on macOS.
2. Select **File > New > Project...** -> **iOS > App** -> Name: `AgentCoreIOS`.
3. Choose **Interface: SwiftUI** and **Language: Swift**.
4. Drag and drop the `ios/AgentCoreIOS/` folder into the Xcode project navigator.
5. Drag and drop `ios/Tests/` into the Xcode Test Target navigator.
6. Select Target `AgentCoreIOS` -> **Run** on iOS Simulator (iPhone 15 Pro / iPhone 16 Pro).
7. Run tests via **Product > Test** (`⌘U`).

---

## 7. Release Verification Gate

| Verification Target | Status | Notes |
|---------------------|--------|-------|
| **SIMULATOR VERIFIED** | **`NOT YET EXECUTED`** | Requires macOS/Xcode toolchain in CI runner. |
| **DEVICE VERIFIED** | **`NOT YET EXECUTED`** | Requires attached physical iPhone device. |
| **LINUX / PYTHON KERNEL CONTRACT VERIFIED** | **`PASSED`** | 740+ unit/integration tests passed in local CI sandbox. |
| **API CONTRACT MIRROR VERIFIED** | **`PASSED`** | Verified via `tests/test_ios_native_api_contract.py`. |

---

## 8. Limitations & Deferred Work

- **No Remote Cloud Dependencies**: Zero CloudKit, Firebase, or Supabase integrations.
- **No iCloud Synchronization**: Native iCloud sync deferred to future milestones.
- **Local Model Runtime Integration**: Real CoreML/llama.cpp model binding to be added when on-device LLM weights are deployed.
