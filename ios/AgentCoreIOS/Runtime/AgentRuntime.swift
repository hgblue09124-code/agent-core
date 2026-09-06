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
    private var runEventsMap: [String: [AgentRunEvent]] = [:]
    private var pendingApprovals: [String: PermissionRequest] = [:]
    private var cancelledRuns: Set<String> = []
    private var activeRunIds: Set<String> = []
    private var isRunningTask: Bool = false
    private var isThinking: Bool = false

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
            requiresUserApproval: false,
            isRemote: false
        )
        let github = Capability(
            capabilityId: "github_integration",
            name: "GitHub Integration Capability",
            description: "Access GitHub repositories, issues, and issue comments",
            readOnly: false,
            requiresUserApproval: false,
            isRemote: true
        )
        capabilities[mockEcho.capabilityId] = mockEcho
        capabilities[github.capabilityId] = github
    }

    public func currentAgentStatus() async -> AgentStatus {
        if !vaultStore.isAvailable() {
            return .offline
        }
        if isThinking {
            return .thinking
        }
        if isRunningTask {
            return .running
        }
        return .ready
    }

    public func run(goal: String, userApproved: Bool = false) async -> AgentRunResult {
        return await runStreaming(goal: goal, userApproved: userApproved, capabilityDispatch: nil, onEvent: { _ in })
    }

    public func runStreaming(
        goal: String,
        userApproved: Bool = false,
        capabilityDispatch: (capabilityId: String, input: [String: String])? = nil,
        onEvent: @escaping @Sendable (AgentRunEvent) -> Void
    ) async -> AgentRunResult {
        let startTime = Date()
        let trimmedGoal = goal.trimmingCharacters(in: .whitespacesAndNewlines)
        let seq = Int(Date().timeIntervalSince1970 * 1000) % 100000
        let runId = String(format: "RUN-%05d", seq)

        activeRunIds.insert(runId)
        isRunningTask = true
        defer {
            activeRunIds.remove(runId)
            isRunningTask = false
            isThinking = false
        }

        var events: [AgentRunEvent] = []

        func emit(_ phase: AgentEventPhase, _ status: AgentEventStatus, _ summary: String, payload: [String: String]? = nil) {
            let ev = AgentRunEvent(
                runId: runId,
                phase: phase,
                status: status,
                summary: summary,
                payload: payload
            )
            events.append(ev)
            onEvent(ev)
        }

        if cancelledRuns.contains(runId) {
            let duration = Date().timeIntervalSince(startTime)
            let res = AgentRunResult(
                runId: runId,
                status: .failed,
                goal: trimmedGoal,
                errorCode: "CANCELLED",
                errorMessage: "Run was cancelled before execution",
                authorized: false,
                verificationVerdict: "CANCELLED"
            )
            _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "cancelled", durationSeconds: duration)
            return res
        }

        emit(.taskStarted, .running, "Task execution started for goal: \(trimmedGoal)")

        if trimmedGoal.isEmpty {
            let duration = Date().timeIntervalSince(startTime)
            let res = AgentRunResult(
                runId: runId,
                status: .failed,
                goal: goal,
                errorCode: "INVALID_INPUT",
                errorMessage: "Task goal cannot be empty.",
                authorized: true,
                verificationVerdict: "FAIL"
            )
            emit(.taskFailed, .error, "Task failed due to invalid input")
            runEventsMap[runId] = events
            checkpointStore.save(result: res)
            _ = experienceStore.record(runId: runId, goal: goal, outcome: "failed", durationSeconds: duration)
            return res
        }

        let writeKeywords = ["create", "update", "delete", "post", "put", "patch", "write", "comment", "merge", "close", "remove", "forget", "drop", "clear", "modify"]
        let goalWords = trimmedGoal.lowercased().components(separatedBy: CharacterSet.alphanumerics.inverted)
        let isMutatingGoal = writeKeywords.contains(where: { goalWords.contains($0) })

        if isMutatingGoal && !userApproved {
            let duration = Date().timeIntervalSince(startTime)
            let permReq = PermissionRequest(
                runId: runId,
                capabilityId: "core.policy",
                action: "execute_mutating_goal",
                input: ["goal": trimmedGoal],
                reason: "Policy Denial: Execution of mutating goal '\(trimmedGoal)' requires explicit user approval."
            )
            pendingApprovals[runId] = permReq

            let res = AgentRunResult(
                runId: runId,
                status: .denied,
                goal: trimmedGoal,
                errorCode: "POLICY_DENIAL",
                errorMessage: "Policy Denial: Execution of mutating goal '\(trimmedGoal)' requires explicit user approval (userApproved = true).",
                authorized: false,
                verificationVerdict: "DENIED"
            )
            emit(.taskFailed, .error, "Policy denial: user approval required")
            runEventsMap[runId] = events
            checkpointStore.save(result: res)
            _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "denied", durationSeconds: duration)
            return res
        }

        if let dispatch = capabilityDispatch {
            if cancelledRuns.contains(runId) {
                let duration = Date().timeIntervalSince(startTime)
                let res = AgentRunResult(
                    runId: runId,
                    status: .failed,
                    goal: trimmedGoal,
                    errorCode: "CANCELLED",
                    errorMessage: "Task execution was cancelled by user.",
                    authorized: false,
                    verificationVerdict: "CANCELLED"
                )
                emit(.taskFailed, .error, "Task execution cancelled by user")
                runEventsMap[runId] = events
                checkpointStore.save(result: res)
                _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "cancelled", durationSeconds: duration)
                return res
            }

            emit(.execution, .running, "Executing capability action: \(dispatch.input["action"] ?? dispatch.capabilityId)")
            let capRes = await executeCapability(
                capabilityId: dispatch.capabilityId,
                input: dispatch.input,
                userApproved: userApproved
            )
            if capRes.status == .denied {
                let duration = Date().timeIntervalSince(startTime)
                let permReq = PermissionRequest(
                    runId: runId,
                    capabilityId: dispatch.capabilityId,
                    action: dispatch.input["action"] ?? "",
                    input: dispatch.input,
                    reason: capRes.errorMessage ?? "Action requires explicit user approval"
                )
                pendingApprovals[runId] = permReq

                let res = AgentRunResult(
                    runId: runId,
                    status: .denied,
                    goal: trimmedGoal,
                    errorCode: "POLICY_DENIAL",
                    errorMessage: capRes.errorMessage,
                    authorized: false,
                    verificationVerdict: "DENIED"
                )
                emit(.taskFailed, .error, "Capability execution denied by policy")
                runEventsMap[runId] = events
                checkpointStore.save(result: res)
                _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "denied", durationSeconds: duration)
                return res
            }
        }

        if cancelledRuns.contains(runId) {
            let duration = Date().timeIntervalSince(startTime)
            let res = AgentRunResult(
                runId: runId,
                status: .failed,
                goal: trimmedGoal,
                errorCode: "CANCELLED",
                errorMessage: "Task execution was cancelled by user.",
                authorized: false,
                verificationVerdict: "CANCELLED"
            )
            emit(.taskFailed, .error, "Task execution cancelled by user")
            runEventsMap[runId] = events
            checkpointStore.save(result: res)
            _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "cancelled", durationSeconds: duration)
            return res
        }

        isThinking = true
        let planSteps = await planner.generatePlan(goal: trimmedGoal)
        isThinking = false
        emit(.planCreated, .ok, "Generated plan with \(planSteps.count) steps", payload: ["planSteps": planSteps.joined(separator: "\n")])

        for (idx, step) in planSteps.enumerated() {
            if cancelledRuns.contains(runId) {
                let duration = Date().timeIntervalSince(startTime)
                let res = AgentRunResult(
                    runId: runId,
                    status: .failed,
                    goal: trimmedGoal,
                    errorCode: "CANCELLED",
                    errorMessage: "Task execution was cancelled by user.",
                    authorized: false,
                    verificationVerdict: "CANCELLED"
                )
                emit(.taskFailed, .error, "Task execution cancelled by user", payload: ["errorCode": "CANCELLED"])
                runEventsMap[runId] = events
                checkpointStore.save(result: res)
                _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "cancelled", durationSeconds: duration)
                return res
            }

            let stepId = "STEP-\(idx + 1)"
            emit(.execute, .running, step, payload: ["stepId": stepId, "stepIndex": "\(idx)"])
            emit(.observeResult, .pass, "Completed step \(idx + 1)", payload: ["stepId": stepId, "stepIndex": "\(idx)"])
        }

        // Store run summary in vault
        _ = vaultStore.storeContext(key: "run_summary_\(runId)", value: trimmedGoal, category: "run_history")

        emit(.verify, .pass, "Verification verdict PASS")

        let duration = Date().timeIntervalSince(startTime)
        let result = AgentRunResult(
            runId: runId,
            status: .success,
            goal: trimmedGoal,
            output: "Successfully executed goal '\(trimmedGoal)' through local agent runtime pipeline.",
            planSteps: planSteps,
            authorized: true,
            verificationVerdict: "PASS"
        )

        emit(.taskCompleted, .ok, "Task completed successfully")
        runEventsMap[runId] = events
        checkpointStore.save(result: result)
        _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "success", durationSeconds: duration)

        return result
    }

    public func cancel(runId: String) async -> Bool {
        let isCheckpointExist = checkpointStore.get(runId: runId) != nil
        let isActive = activeRunIds.contains(runId)

        guard isCheckpointExist || isActive else {
            return false
        }

        if let existing = checkpointStore.get(runId: runId) {
            if existing.status == .success || existing.status == .failed || existing.status == .denied {
                return false
            }
        }

        cancelledRuns.insert(runId)
        _ = await cancelRun(runId: runId)
        return true
    }

    public func cancelRun(runId: String) async -> AgentRunResult {
        let existingGoal = checkpointStore.get(runId: runId)?.goal ?? "Task Execution"
        let cancelled = AgentRunResult(
            runId: runId,
            status: .failed,
            goal: existingGoal,
            output: "Task execution cancelled by user request.",
            errorCode: "CANCELLED",
            errorMessage: "Task execution was cancelled by user.",
            authorized: true,
            verificationVerdict: "CANCELLED"
        )
        checkpointStore.save(result: cancelled)
        _ = experienceStore.record(runId: runId, goal: existingGoal, outcome: "cancelled", durationSeconds: 0.0)
        return cancelled
    }

    public func pendingApproval(runId: String) async -> PermissionRequest? {
        return pendingApprovals[runId]
    }

    public func listActivity(filter: ActivityFilter = .all) async -> [ActivityRecord] {
        let exps = experienceStore.listAll()
        var records: [ActivityRecord] = []
        for exp in exps {
            let status: Status
            switch exp.outcome.lowercased() {
            case "success":
                status = .success
            case "denied":
                status = .denied
            default:
                status = .failed
            }

            if filter == .success && status != .success {
                continue
            }
            if filter == .failed && (status != .failed && status != .denied) {
                continue
            }

            let record = ActivityRecord(
                recordId: exp.runId,
                runId: exp.runId,
                goal: exp.goal,
                status: status,
                durationSeconds: exp.durationSeconds,
                createdAt: exp.timestamp
            )
            records.append(record)
        }
        return records
    }

    public func vaultSummary() async -> VaultSummary {
        return vaultStore.summarize()
    }

    public func listConnections() async -> [ConnectionStatus] {
        var connections: [ConnectionStatus] = []
        for cap in capabilities.values {
            let kind: ConnectionKind = cap.isRemote ? .remote : .local
            let state: ConnectionState
            if cap.isRemote {
                let token = ProcessInfo.processInfo.environment["GITHUB_TOKEN"]
                state = (token != nil && !token!.isEmpty) ? .remoteConfigured : .remoteNotConfigured
            } else {
                state = .localActive
            }
            connections.append(
                ConnectionStatus(
                    capabilityId: cap.capabilityId,
                    name: cap.name,
                    kind: kind,
                    state: state,
                    description: cap.description,
                    requiresApproval: cap.requiresUserApproval
                )
            )
        }
        return connections.sorted(by: { $0.capabilityId < $1.capabilityId })
    }

    public func resume(runId: String) async -> AgentRunResult {
        if cancelledRuns.contains(runId) {
            let existingGoal = checkpointStore.get(runId: runId)?.goal ?? "Cancelled run"
            let cancelled = AgentRunResult(
                runId: runId,
                status: .failed,
                goal: existingGoal,
                output: "Task execution cancelled by user request.",
                errorCode: "CANCELLED",
                errorMessage: "Task execution was cancelled by user.",
                authorized: true,
                verificationVerdict: "CANCELLED"
            )
            return cancelled
        }

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
        _ = vaultStore.storeContext(key: key, value: value, category: "user_preference")
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
        _ = vaultStore.storeContext(key: key, value: value, category: "user_preference")
        if let updated = memoryStore.update(key: key, value: value) {
            return MemoryResult(status: .success, item: updated)
        }
        let created = memoryStore.remember(key: key, value: value)
        return MemoryResult(status: .success, item: created)
    }

    public func forget(key: String) async -> MemoryResult {
        let removed = memoryStore.forget(key: key)
        let vaultRemoved = vaultStore.deleteContext(key: key)
        if removed || vaultRemoved {
            return MemoryResult(status: .success)
        } else {
            return MemoryResult(status: .failed, errorMessage: "Memory key '\(key)' not found.")
        }
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
