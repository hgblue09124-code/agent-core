# Agent Core — Personal Agent Beta v0.1

Personal Agent development substrate and composition authority.

## Personal Agent Beta v0.1 Architecture & System Composition

Personal Agent Beta v0.1 represents the composition point for three distinct architectural layers:

```
                  ┌─────────────────────────────────────────┐
                  │               USER REQUEST              │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │        AGENT-CORE (Authority/Kernel)    │
                  │ Identity | Cognition | Policy | Learning│
                  │ Orchestration | Experience | Continuity │
                  └───────┬─────────────────────────┬───────┘
                          │                         │
            ┌─────────────┴───────────┐ ┌───────────┴─────────────┐
            │  AGENT-PERSONAL-VAULT   │ │    AGENT-CAPABILITIES    │
            │ (Storage & Personal Data│ │(Pluggable Module Framework│
            │  via PersonalVaultAdapter)│ │ via GitHub/BridgeAdapters)│
            └─────────────────────────┘ └─────────────────────────┘
```

### Architectural Ownership & Layer Delineation

1. **Agent-Core (Authority & Cognition Substrate)**:
   - Responsible for agent identity, cognition, policy validation, kernel orchestration, experience recording, strategy learning, and state continuity across process restarts.
   - Core maintains absolute constitutional precedence:
     `Kernel / Security / Contracts > Verification > Task Requirements > Learned Strategies > Philosophy`
   - Does NOT embed capability-specific business logic or personal storage implementations inside the Core.

2. **agent-personal-vault (Persistent Personal Data & Storage Layer)**:
   - Integrated into Core via `PersonalVaultAdapter` (`core/vault/adapter.py`).
   - Responsible for persistent personal context, user preferences, and private personal storage.
   - Falls back gracefully to local storage buffer if external Vault package is absent, ensuring Core operational autonomy.

3. **agent-capabilities (Pluggable Capability Framework & Adapters)**:
   - Integrated into Core via `CapabilityRegistry` (`core/capabilities/adapter.py`) and `ExternalCapabilityBridge` (`core/capabilities/bridge.py`).
   - Responsible for replaceable external domain execution (e.g. GitHub API interaction, shell/tool execution).
   - Core provides `GitHubCapabilityAdapter` (`core/capabilities/github.py`) as the primary real Beta capability target.
   - Capability execution must pass through Policy Engine validation (`authorize_capability`) checking constraints (`read_only`, `requires_user_approval`, `allowed_domains`).
   - Capability execution errors return structured `CapabilityResult` statuses without compromising Core integrity.

## Beta v0.1 Acceptance Flow

```
User Request
  ↳ Observe
  ↳ Retrieve Personal Context (PersonalVaultAdapter)
  ↳ Reason
  ↳ Plan
  ↳ Policy / Permission Check (authorize_capability)
  ↳ Capability Dispatch
  ↳ Execute
  ↳ Verify
  ↳ Record Experience
  ↳ Extract Lesson
  ↳ Update Memory & Vault
  ↳ Continue / Resume (agent.resume(run_id))
```

## Implemented Subsystems

- **Core Architecture & Kernel Loop**: Bounded orchestration loop (`Observe → Retrieve → Reason → Plan → Policy → Capability Dispatch → Execute → Verify → Experience → Lesson → Memory → Resume`).
- **Personal Vault Integration**: Narrow storage adapter interface (`core/vault/adapter.py`) bridging Core to personal data storage.
- **Pluggable Capability Registry & Bridge**: External capability bridge (`core/capabilities/bridge.py`) and GitHub capability target (`core/capabilities/github.py`).
- **Policy Engine Permissions**: Explicit capability constraint checks (`read_only`, `requires_user_approval`, `allowed_domains`) enforcing constitutional boundaries.
- **Continuity & Resumption**: Checkpoint persistence (`core/runtime/checkpoint.py`) supporting run state restoration (`agent.resume(run_id)`).
- **First-Class Strategy Subsystem**: Strategy lifecycle management (`CANDIDATE`, `VALIDATED`, `SUPPORTED`, `WEAKENED`, `RETIRED`, `SUPERSEDED`) with confidence scoring.
- **Native iOS Local Agent API & Unsigned IPA Release Workflow**: Embedded Swift local agent API (`ios/AgentCoreIOS/`), Xcode project (`ios/AgentCoreIOS.xcodeproj`), offline-first GitHub Data Update manager, automated unsigned IPA build pipeline, and GitHub Release asset packaging (`AgentCore-iOS-v0.1.0-unsigned.ipa`).

## Native iOS Local Agent API & Unsigned IPA Build

Native Swift local agent service, runtime API, and offline-first data sync engine located in `ios/`:
- **Local API Contract**: `LocalAgentServiceProtocol` & `AgentRuntime` (`ios/AgentCoreIOS/API/` & `ios/AgentCoreIOS/Runtime/`).
- **Data Update Manager**: Offline-first, manifest-driven data and configuration sync (`ios/AgentCoreIOS/Update/`).
- **Unsigned IPA Build & Release Asset**: `AgentCore-iOS-v0.1.0-unsigned.ipa` automatically compiled without Apple signing secrets, validated, uploaded as GitHub Actions artifact, and attached to GitHub Release `v0.1.0`.
- **Re-Signing Notice**: Intentionally unsigned; requires local re-signing via AltStore, SideStore, or Sideloadly prior to device installation.

For full iOS setup, building, local re-signing, and testing instructions, see [`ios/README.md`](ios/README.md).

## Developer Preview Status

> **Note**: Personal Agent Beta v0.1 is a **Developer Preview & Reference Architecture**. It is not claimed to be production-ready.

### Intentionally Deferred Features
- Vector database / embedding-based semantic retrieval.
- Autonomous 24/7 web browser agents or unrestricted internet execution.
- Multi-agent swarm architectures.
- Fine-tuning or complex cloud infrastructure.
- Native iCloud synchronization.

## Principles

- Build from small verified primitives.
- Core remains authority; Vault remains persistence; capabilities remain replaceable modules.
- Every capability execution passes through policy and permission checks.
- Successful experiences become reusable learned strategies.
- Capability failures must never compromise Core integrity.

## CLI Usage

```bash
# Run a task
agent-core run "Inspect system architecture"

# Run Cửu Giới benchmark suite (external target)
agent-core benchmark

# Inspect run lifecycle
agent-core inspect KRUN-12345

# View run history
agent-core history
```
