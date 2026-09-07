// ios/AgentCoreIOS/Runtime/AgentRuntime.swift
// Native iOS Local Agent Runtime Kernel Adaptor

import Foundation

public final class AgentRuntime: @unchecked Sendable {
    private let memoryStore: LocalMemoryStore
    private let experienceStore: LocalExperienceStore
    private let checkpointStore: LocalCheckpointStore
    private let vaultStore: LocalVaultStore
    private let planner: AgentModelProviderProtocol
    private let languageModelProvider: LanguageModelProvider?
    private let urlSession: URLSession

    private var capabilities: [String: Capability] = [:]
    private var runEventsMap: [String: [AgentRunEvent]] = [:]
    private var pendingApprovals: [String: PermissionRequest] = [:]
    private var cancelledRuns: Set<String> = []
    private var activeRunIds: Set<String> = []
    private var isRunningTask: Bool = false
    private var isThinking: Bool = false
