// ios/AgentCoreIOS/API/LocalAgentService.swift
// Native iOS Local Agent API Service Implementation

import Foundation

/// Public native LocalAgentService implementing LocalAgentServiceProtocol.
/// Communicates directly with native AgentRuntime, preserving offline local-first security & policy boundaries.
public final class LocalAgentService: LocalAgentServiceProtocol, @unchecked Sendable {
    private let runtime: AgentRuntime

    public init(runtime: AgentRuntime? = nil) {
        self.runtime = runtime ?? AgentRuntime()
    }

    public func run(goal: String, userApproved: Bool = false) async -> AgentRunResult {
        return await runtime.run(goal: goal, userApproved: userApproved)
    }

    public func resume(runId: String) async -> AgentRunResult {
        return await runtime.resume(runId: runId)
    }

    public func remember(key: String, value: String) async -> MemoryResult {
        return await runtime.remember(key: key, value: value)
    }

    public func retrieve(query: String) async -> [MemoryItem] {
        return await runtime.retrieve(query: query)
    }

    public func updateMemory(key: String, value: String, userApproved: Bool = false) async -> MemoryResult {
        return await runtime.updateMemory(key: key, value: value, userApproved: userApproved)
    }

    public func listCapabilities() async -> [Capability] {
        return await runtime.listCapabilities()
    }

    public func executeCapability(capabilityId: String, input: [String: String], userApproved: Bool = false) async -> CapabilityResult {
        return await runtime.executeCapability(capabilityId: capabilityId, input: input, userApproved: userApproved)
    }

    public func getRun(runId: String) async -> AgentRunResult? {
        return await runtime.getRun(runId: runId)
    }

    public func getExperience() async -> [Experience] {
        return await runtime.getExperience()
    }

    public func health() async -> AgentHealth {
        return await runtime.health()
    }
}
