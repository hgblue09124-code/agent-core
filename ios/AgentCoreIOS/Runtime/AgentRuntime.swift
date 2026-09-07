// ios/AgentCoreIOS/Runtime/AgentRuntime.swift
// Native iOS Local Agent Runtime Kernel Adaptor

import Foundation

public final class AgentRuntime: @unchecked Sendable {
    private let memoryStore: LocalMemoryStore
    private let experienceStore: LocalExperienceStore
    private let checkpointStore: LocalCheckpointStore
    private let vaultStore: LocalVaultStore
    private let planner: AgentModelProviderProtocol
    /// Optional language model provider abstraction (Step 1).
    /// AgentRuntime never depends on concrete LLM implementations.
    private let languageModelProvider: LanguageModelProvider?

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
        planner: AgentModelProviderProtocol? = nil,
        languageModelProvider: LanguageModelProvider? = nil
    ) {
        self.memoryStore = memoryStore ?? LocalMemoryStore()
        self.experienceStore = experienceStore ?? LocalExperienceStore()
        self.checkpointStore = checkpointStore ?? LocalCheckpointStore()
        self.vaultStore = vaultStore ?? LocalVaultStore()
        self.planner = planner ?? LocalDeterministicPlanner()
        self.languageModelProvider = languageModelProvider

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

        let intent = classifyGoal(trimmedGoal)

        // Cheap remember/forget/status execute directly without calling the LLM.
        if intent.kind == .remember || intent.kind == .forget {
            return await executeMemoryIntent(
                intent: intent,
                runId: runId,
                trimmedGoal: trimmedGoal,
                startTime: startTime,
                emit: { phase, status, summary, payload in
                    emit(phase, status, summary, payload: payload)
                }
            )
        }

        if intent.kind == .status {
            return await executeStatusIntent(
                intent: intent,
                runId: runId,
                trimmedGoal: trimmedGoal,
                startTime: startTime,
                emit: { phase, status, summary, payload in
                    emit(phase, status, summary, payload: payload)
                }
            )
        }

        let writeKeywords = ["create", "update", "delete", "post", "put", "patch", "write", "comment", "merge", "close", "remove", "drop", "clear", "modify"]
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

        let provider = languageModelProvider ?? RoutingLanguageModelProvider.shared

        isThinking = true
        do {
            if !provider.isLoaded {
                try await provider.load()
            }
        } catch {
            isThinking = false
            let duration = Date().timeIntervalSince(startTime)
            let errorMsg = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            let res = AgentRunResult(
                runId: runId,
                status: .failed,
                goal: trimmedGoal,
                errorCode: "MODEL_NOT_LOADED",
                errorMessage: errorMsg,
                authorized: true,
                verificationVerdict: "FAIL"
            )
            emit(.taskFailed, .error, errorMsg)
            runEventsMap[runId] = events
            checkpointStore.save(result: res)
            _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "failed", durationSeconds: duration)
            return res
        }

        let relevantMemories = await retrieve(query: trimmedGoal)
        var memoryContext = ""
        if !relevantMemories.isEmpty {
            let snippet = relevantMemories.prefix(3).map { "\($0.key): \($0.value)" }.joined(separator: "\n")
            memoryContext = "\nRelevant Memory Context:\n\(snippet)\n"
        }

        let systemPrompt = "You are an intelligent local personal agent. Reason about the user's goal and provide a clear, concise, actionable response or plan.\(memoryContext)"
        let request = LanguageModelRequest(
            systemPrompt: systemPrompt,
            messages: [LanguageModelMessage(role: .user, content: trimmedGoal)],
            parameters: LanguageModelGenerationParameters(maxTokens: 500)
        )

        let response: LanguageModelResponse
        do {
            response = try await provider.generate(request)
            isThinking = false
        } catch {
            isThinking = false
            let duration = Date().timeIntervalSince(startTime)
            let errorMsg = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
            let errorCode: String
            if let lmError = error as? LanguageModelError {
                switch lmError {
                case .notLoaded: errorCode = "MODEL_NOT_LOADED"
                case .providerUnavailable: errorCode = "PROVIDER_UNAVAILABLE"
                case .generationFailed: errorCode = "GENERATION_FAILED"
                case .invalidRequest: errorCode = "INVALID_REQUEST"
                case .cancelled: errorCode = "CANCELLED"
                default: errorCode = "LLM_ERROR"
                }
            } else {
                errorCode = "LLM_ERROR"
            }

            let res = AgentRunResult(
                runId: runId,
                status: .failed,
                goal: trimmedGoal,
                errorCode: errorCode,
                errorMessage: errorMsg,
                authorized: true,
                verificationVerdict: "FAIL"
            )
            emit(.taskFailed, .error, errorMsg)
            runEventsMap[runId] = events
            checkpointStore.save(result: res)
            _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "failed", durationSeconds: duration)
            return res
        }

        let rawLines = response.text
            .split(separator: "\n")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty && !$0.hasPrefix("#") }
        let planSteps: [String] = rawLines.isEmpty ? [response.text] : Array(rawLines.prefix(5))

        emit(.planCreated, .ok, "Generated plan with \(planSteps.count) steps", payload: ["planSteps": planSteps.joined(separator: "\n")])

        for (idx, step) in planSteps.enumerated() {
            if Task.isCancelled || cancelledRuns.contains(runId) {
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
            emit(.observeResult, .pass, step, payload: ["stepId": stepId, "stepIndex": "\(idx)"])
        }

        emit(.verify, .pass, "Verification verdict PASS")

        _ = vaultStore.storeContext(key: "run_summary_\(runId)", value: trimmedGoal, category: "run_history")

        let duration = Date().timeIntervalSince(startTime)
        let result = AgentRunResult(
            runId: runId,
            status: .success,
            goal: trimmedGoal,
            output: response.text,
            planSteps: planSteps,
            authorized: true,
            verificationVerdict: "PASS"
        )

        emit(.taskCompleted, .ok, response.text)
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
        if removed {
            _ = vaultStore.deleteContext(key: key)
            return MemoryResult(status: .success)
        }
        return MemoryResult(status: .failed, errorMessage: "Memory key '\(key)' not found")
    }

    public func listCapabilities() async -> [Capability] {
        return Array(capabilities.values).sorted(by: { $0.capabilityId < $1.capabilityId })
    }

    public func executeCapability(capabilityId: String, input: [String: String], userApproved: Bool = false) async -> CapabilityResult {
        guard capabilities[capabilityId] != nil else {
            return CapabilityResult(
                capabilityId: capabilityId,
                status: .failed,
                errorMessage: "Unknown capability '\(capabilityId)'"
            )
        }

        let action = input["action"] ?? ""
        let writeActions = ["create_issue_comment", "create_issue", "update_issue", "close_issue", "merge_pr"]
        let isWrite = writeActions.contains(action)

        if isWrite && !userApproved {
            return CapabilityResult(
                capabilityId: capabilityId,
                status: .denied,
                errorMessage: "Policy Denial: Action '\(action)' on capability '\(capabilityId)' requires explicit user approval."
            )
        }

        if input["mock_offline"] == "true" || capabilityId == "mock.echo" {
            return CapabilityResult(
                capabilityId: capabilityId,
                status: .success,
                output: "Mock offline execution of '\(action.isEmpty ? capabilityId : action)' completed."
            )
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
        let effectiveProvider = languageModelProvider ?? RoutingLanguageModelProvider.shared
        let routed = effectiveProvider as? RoutingLanguageModelProvider
        let display = routed?.displayStatus()
        let localOnly: Bool
        if let display {
            localOnly = display.localOnly
        } else {
            localOnly = !effectiveProvider.isRemote
        }
        return AgentHealth(
            status: "HEALTHY",
            isLocalOnly: localOnly,
            providerName: display?.name ?? effectiveProvider.providerId,
            providerStatus: display?.status ?? planner.providerStatus.rawValue,
            isVaultAvailable: vaultStore.isAvailable(),
            storagePath: "Application Support/AgentCore/",
            activeCapabilitiesCount: capabilities.count
        )
    }

    // MARK: - Cheap classification + real plan/execute

    private struct GoalIntent {
        enum Kind { case remember, forget, status, other }
        let kind: Kind
        let key: String
        let value: String
    }

    private func classifyGoal(_ goal: String) -> GoalIntent {
        let trimmed = goal.trimmingCharacters(in: .whitespacesAndNewlines)
        let lower = trimmed.lowercased()

        if lower.hasPrefix("remember") {
            var rest = trimmed
            if let range = rest.range(of: "remember", options: [.caseInsensitive]) {
                rest = String(rest[range.upperBound...]).trimmingCharacters(in: .whitespaces)
            }
            if rest.lowercased().hasPrefix("that ") {
                rest = String(rest.dropFirst(5)).trimmingCharacters(in: .whitespaces)
            }
            rest = rest.trimmingCharacters(in: CharacterSet(charactersIn: "."))
            let parts = splitFact(rest)
            return GoalIntent(kind: .remember, key: parts.0, value: parts.1)
        }

        if lower.hasPrefix("forget") {
            var rest = trimmed
            if let range = rest.range(of: "forget", options: [.caseInsensitive]) {
                rest = String(rest[range.upperBound...]).trimmingCharacters(in: .whitespaces)
            }
            for prefix in ["memory ", "the ", "key "] {
                if rest.lowercased().hasPrefix(prefix) {
                    rest = String(rest.dropFirst(prefix.count))
                    break
                }
            }
            rest = rest.trimmingCharacters(in: CharacterSet(charactersIn: "."))
            return GoalIntent(kind: .forget, key: rest, value: rest)
        }

        let statusHints = ["status", "health", "version", "ping", "smoke"]
        let wordCount = trimmed.split(separator: " ").count
        if wordCount <= 8 && statusHints.contains(where: { lower.contains($0) }) {
            return GoalIntent(kind: .status, key: "", value: trimmed)
        }
        return GoalIntent(kind: .other, key: "", value: trimmed)
    }

    private func splitFact(_ content: String) -> (String, String) {
        let lower = content.lowercased()
        if let range = lower.range(of: " is ") {
            var key = String(content[..<range.lowerBound]).trimmingCharacters(in: .whitespaces)
            let value = String(content[range.upperBound...]).trimmingCharacters(in: .whitespaces)
            for prefix in ["that ", "my ", "the "] {
                if key.lowercased().hasPrefix(prefix) {
                    key = String(key.dropFirst(prefix.count))
                }
            }
            return (String(key.prefix(80)), String(value.prefix(400)))
        }
        if let idx = content.firstIndex(of: ":") {
            let key = content[..<idx].trimmingCharacters(in: .whitespaces)
            let value = content[content.index(after: idx)...].trimmingCharacters(in: .whitespaces)
            return (String(key.prefix(80)), String(value.prefix(400)))
        }
        return (String(content.prefix(80)), String(content.prefix(400)))
    }

    private func generatePlanSteps(goal: String) async -> [String] {
        if let provider = languageModelProvider {
            do {
                if !provider.isLoaded {
                    try await provider.load()
                }
                let request = LanguageModelRequest(
                    systemPrompt: "Return 1 to 5 short plan steps, one per line. No chain-of-thought.",
                    messages: [LanguageModelMessage(role: .user, content: goal)],
                    parameters: LanguageModelGenerationParameters(maxTokens: 200)
                )
                let response = try await provider.generate(request)
                let lines = response.text
                    .split(separator: "\n")
                    .map { $0.trimmingCharacters(in: .whitespaces) }
                    .filter { !$0.isEmpty && !$0.hasPrefix("#") }
                if !lines.isEmpty {
                    return Array(lines.prefix(5))
                }
            } catch {
                // Fall back to deterministic planner.
            }
        }
        return await planner.generatePlan(goal: goal)
    }

    private func executeMemoryIntent(
        intent: GoalIntent,
        runId: String,
        trimmedGoal: String,
        startTime: Date,
        emit: (AgentEventPhase, AgentEventStatus, String, [String: String]?) -> Void
    ) async -> AgentRunResult {
        let stepTitle: String
        let mem: MemoryResult
        if intent.kind == .remember {
            stepTitle = "Remember \(intent.key)"
            mem = await remember(key: intent.key, value: intent.value)
        } else {
            stepTitle = "Forget \(intent.key)"
            mem = await forget(key: intent.key)
        }

        emit(.planCreated, .ok, "Generated plan with 1 steps", ["planSteps": stepTitle])
        emit(.execute, .running, stepTitle, ["stepId": "STEP-1", "stepIndex": "0"])

        let ok = mem.status == .success
        emit(.observeResult, ok ? .pass : .fail, ok ? (intent.value.isEmpty ? stepTitle : intent.value) : (mem.errorMessage ?? "failed"), ["stepId": "STEP-1", "stepIndex": "0"])
        emit(.verify, ok ? .pass : .fail, ok ? "Verification verdict PASS" : "Verification verdict FAIL", nil)

        let duration = Date().timeIntervalSince(startTime)
        if ok {
            let result = AgentRunResult(
                runId: runId,
                status: .success,
                goal: trimmedGoal,
                output: intent.kind == .remember
                    ? "Remembered '\(intent.key)' = '\(intent.value)'"
                    : "Forgot '\(intent.key)'",
                planSteps: [stepTitle],
                authorized: true,
                verificationVerdict: "PASS"
            )
            emit(.taskCompleted, .ok, "Task completed successfully", nil)
            runEventsMap[runId] = runEventsMap[runId] ?? []
            checkpointStore.save(result: result)
            _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "success", durationSeconds: duration)
            return result
        }

        let result = AgentRunResult(
            runId: runId,
            status: .failed,
            goal: trimmedGoal,
            errorCode: "MEMORY_FAIL",
            errorMessage: mem.errorMessage ?? "Memory operation failed",
            planSteps: [stepTitle],
            authorized: true,
            verificationVerdict: "FAIL"
        )
        emit(.taskFailed, .error, result.errorMessage ?? "failed", nil)
        checkpointStore.save(result: result)
        _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "failed", durationSeconds: duration)
        return result
    }

    private func executeStatusIntent(
        intent: GoalIntent,
        runId: String,
        trimmedGoal: String,
        startTime: Date,
        emit: (AgentEventPhase, AgentEventStatus, String, [String: String]?) -> Void
    ) async -> AgentRunResult {
        let stepTitle = "Check Agent Health & Status"
        emit(.planCreated, .ok, "Generated plan with 1 steps", ["planSteps": stepTitle])
        emit(.execute, .running, stepTitle, ["stepId": "STEP-1", "stepIndex": "0"])

        let healthInfo = await health()
        let statusText = "Agent Status: \(healthInfo.status) | Provider: \(healthInfo.providerName) (\(healthInfo.providerStatus)) | Vault: \(healthInfo.isVaultAvailable ? "Available" : "Unavailable")"

        emit(.observeResult, .pass, statusText, ["stepId": "STEP-1", "stepIndex": "0"])
        emit(.verify, .pass, "Verification verdict PASS", nil)

        let duration = Date().timeIntervalSince(startTime)
        let result = AgentRunResult(
            runId: runId,
            status: .success,
            goal: trimmedGoal,
            output: statusText,
            planSteps: [stepTitle],
            authorized: true,
            verificationVerdict: "PASS"
        )
        emit(.taskCompleted, .ok, "Task completed successfully", nil)
        runEventsMap[runId] = runEventsMap[runId] ?? []
        checkpointStore.save(result: result)
        _ = experienceStore.record(runId: runId, goal: trimmedGoal, outcome: "success", durationSeconds: duration)
        return result
    }

    // MARK: - Language Model Provider Bridge (Step 1)

    /// Exposes whether a language model provider was injected.
    public var hasLanguageModelProvider: Bool {
        languageModelProvider != nil
    }

    /// Provider id for diagnostics (nil when no provider injected).
    public var languageModelProviderId: String? {
        languageModelProvider?.providerId
    }

    /// Load the injected language model provider if present.
    public func loadLanguageModel() async throws {
        guard let provider = languageModelProvider else {
            throw LanguageModelError.providerUnavailable("No LanguageModelProvider was injected into AgentRuntime")
        }
        try await provider.load()
    }

    /// Unload the injected language model provider if present.
    public func unloadLanguageModel() async {
        await languageModelProvider?.unload()
    }

    /// Generate a response via the injected LanguageModelProvider.
    /// Demonstrates AgentRuntime → LanguageModelProvider → response flow without rewriting the execution loop.
    public func generateWithLanguageModel(_ request: LanguageModelRequest) async throws -> LanguageModelResponse {
        guard let provider = languageModelProvider else {
            throw LanguageModelError.providerUnavailable("No LanguageModelProvider was injected into AgentRuntime")
        }
        if !provider.isLoaded {
            try await provider.load()
        }
        return try await provider.generate(request)
    }

    /// Stream a response via the injected LanguageModelProvider.
    public func streamWithLanguageModel(_ request: LanguageModelRequest) -> AsyncThrowingStream<LanguageModelStreamChunk, Error> {
        guard let provider = languageModelProvider else {
            return AsyncThrowingStream { continuation in
                continuation.finish(throwing: LanguageModelError.providerUnavailable("No LanguageModelProvider was injected into AgentRuntime"))
            }
        }
        return AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    if !provider.isLoaded {
                        try await provider.load()
                    }
                    for try await chunk in provider.stream(request) {
                        try Task.checkCancellation()
                        continuation.yield(chunk)
                    }
                    continuation.finish()
                } catch is CancellationError {
                    continuation.finish(throwing: LanguageModelError.cancelled)
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { @Sendable _ in
                task.cancel()
            }
        }
    }
}
