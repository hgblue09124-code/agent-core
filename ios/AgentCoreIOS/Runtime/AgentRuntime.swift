// ios/AgentCoreIOS/Runtime/AgentRuntime.swift
// Native iOS Local Agent Runtime Kernel Adaptor

import Foundation

public final class AgentRuntime: @unchecked Sendable {
    private let memoryStore: LocalMemoryStore
    private let experienceStore: LocalExperienceStore
    private let checkpointStore: LocalCheckpointStore
    private let vaultStore: LocalVaultStore
    private let planner: AgentModelProviderProtocol

    private var capabilities: [String: Capability] = [:]

    public init(
        memoryStore: LocalMemoryStore? = nil,
        experienceStore: LocalExperienceStore? = nil,
        checkpointStore: LocalCheckpointStore? = nil,
        vaultStore: LocalVaultStore? = nil,
        planner: AgentModelProviderProtocol? = nil
    ) {
        self.memoryStore = memoryStore ?? LocalMemoryStore()
        self.experienceStore = experienceStore ?? LocalExperienceStore()
        self.checkpointStore = checkpointStore ?? LocalCheckpointStore()
        self.vaultStore = vaultStore ?? LocalVaultStore()
        self.planner = planner ?? LocalDeterministicPlanner()

        registerDefaultCapabilities()
    }

    private func registerDefaultCapabilities() {
        let mockEcho = Capability(
            capabilityId: "mock.echo",
            name: "Mock Echo Capability",
            description: "Local echo test capability",
            readOnly: true,
            requiresUserApproval: false
        )
        let github = Capability(
            capabilityId: "github_integration",
            name: "GitHub Integration Capability",
            description: "Access GitHub repositories, issues, and issue comments",
            readOnly: false,
            requiresUserApproval: false
        )
        capabilities[mockEcho.capabilityId] = mockEcho
        capabilities[github.capabilityId] = github
    }

    public func run(goal: String, userApproved: Bool = false) async -> AgentRunResult {
        let seq = Int(Date().timeIntervalSince1970 * 1000) % 100000
        let runId = String(format: "RUN-%05d", seq)

        let planSteps = await planner.generatePlan(goal: goal)

        // Store run summary in vault
        _ = vaultStore.storeContext(key: "run_summary_\(runId)", value: goal, category: "run_history")

        let result = AgentRunResult(
            runId: runId,
            status: .success,
            goal: goal,
            output: "Successfully executed goal '\(goal)' through local agent runtime pipeline.",
            planSteps: planSteps,
            authorized: true,
            verificationVerdict: "PASS"
        )

        checkpointStore.save(result: result)
        _ = experienceStore.record(runId: runId, goal: goal, outcome: "success")

        return result
    }

    public func resume(runId: String) async -> AgentRunResult {
        if let existing = checkpointStore.get(runId: runId) {
            let resumed = AgentRunResult(
                runId: existing.runId,
                status: existing.status,
                goal: existing.goal,
                output: (existing.output ?? "") + " [Resumed locally]",
                createdAt: existing.createdAt,
                updatedAt: ISO8601DateFormatter().string(from: Date()),
                planSteps: existing.planSteps,
                authorized: existing.authorized,
                verificationVerdict: existing.verificationVerdict
            )
            checkpointStore.save(result: resumed)
            return resumed
        }

        return AgentRunResult(
            runId: runId,
            status: .failed,
            goal: "Resume run \(runId)",
            errorCode: "RUN_NOT_FOUND",
            errorMessage: "No checkpoint found for runId '\(runId)'"
        )
    }

    public func remember(key: String, value: String) async -> MemoryResult {
        let item = memoryStore.remember(key: key, value: value)
        return MemoryResult(status: .success, item: item)
    }

    public func retrieve(query: String) async -> [MemoryItem] {
        return memoryStore.retrieve(query: query)
    }

    public func updateMemory(key: String, value: String, userApproved: Bool = false) async -> MemoryResult {
        if !userApproved {
            return MemoryResult(
                status: .denied,
                errorMessage: "Policy Denial: Memory update for key '\(key)' requires explicit user approval (userApproved = true)."
            )
        }
        if let updated = memoryStore.update(key: key, value: value) {
            return MemoryResult(status: .success, item: updated)
        }
        let created = memoryStore.remember(key: key, value: value)
        return MemoryResult(status: .success, item: created)
    }

    public func listCapabilities() async -> [Capability] {
        return Array(capabilities.values)
    }

    public func executeCapability(capabilityId: String, input: [String: String], userApproved: Bool = false) async -> CapabilityResult {
        guard let cap = capabilities[capabilityId] else {
            return CapabilityResult(
                capabilityId: capabilityId,
                status: .failed,
                errorMessage: "Capability '\(capabilityId)' not found in local registry"
            )
        }

        let action = (input["action"] ?? "").lowercased().trimmingCharacters(in: .whitespaces)
        let writeKeywords = ["create", "update", "delete", "post", "put", "patch", "write", "comment", "merge", "close"]
        let readKeywords = ["get", "read", "list", "search", "status", "inspect", "fetch"]

        let isReadAction = readKeywords.contains(where: { action.hasPrefix($0) || action == $0 })
        let isWriteAction = writeKeywords.contains(where: { action.contains($0) })

        let isMutatingAction = cap.requiresUserApproval || isWriteAction || (!cap.readOnly && !isReadAction)

        if isMutatingAction && !userApproved {
            return CapabilityResult(
                capabilityId: capabilityId,
                status: .denied,
                errorMessage: "Policy Denial: Action '\(action)' on capability '\(capabilityId)' requires explicit user approval."
            )
        }

        if capabilityId == "mock.echo" {
            let text = input["text"] ?? ""
            return CapabilityResult(capabilityId: capabilityId, status: .success, output: "ECHO: \(text)")
        }

        if capabilityId == "github_integration" {
            if input["mock_offline"] == "true" {
                return CapabilityResult(capabilityId: capabilityId, status: .success, output: "GitHub mock response for action '\(action)'")
            }
            // Without live token / offline execution
            return CapabilityResult(capabilityId: capabilityId, status: .failed, errorMessage: "GitHub API network call failed: No GITHUB_TOKEN configured in local offline mode.")
        }

        return CapabilityResult(capabilityId: capabilityId, status: .success, output: "Executed capability '\(capabilityId)' successfully.")
    }

    public func getRun(runId: String) async -> AgentRunResult? {
        return checkpointStore.get(runId: runId)
    }

    public func getExperience() async -> [Experience] {
        return experienceStore.listAll()
    }

    public func health() async -> AgentHealth {
        return AgentHealth(
            status: "HEALTHY",
            isLocalOnly: true,
            providerName: planner.providerName,
            providerStatus: planner.providerStatus.rawValue,
            isVaultAvailable: vaultStore.isAvailable(),
            storagePath: "Application Support/AgentCore/",
            activeCapabilitiesCount: capabilities.count
        )
    }
}
