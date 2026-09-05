// ios/AgentCoreIOS/API/AgentRuntimeContract.swift
// Native iOS Local Agent API Service Protocol Contract

import Foundation

/// Protocol contract for the Native Local Agent Service called directly by iOS SwiftUI UI.
public protocol LocalAgentServiceProtocol: Sendable {
    /// Execute a task goal through the local Agent orchestration loop.
    func run(goal: String, userApproved: Bool) async -> AgentRunResult

    /// Resume an interrupted/non-terminal run from local disk checkpoint.
    func resume(runId: String) async -> AgentRunResult

    /// Remember a key-value personal fact in local memory.
    func remember(key: String, value: String) async -> MemoryResult

    /// Retrieve stored memory items matching a query.
    func retrieve(query: String) async -> [MemoryItem]

    /// Update an existing memory item, enforcing policy write approval checks.
    func updateMemory(key: String, value: String, userApproved: Bool) async -> MemoryResult

    /// List all registered local capabilities and specifications.
    func listCapabilities() async -> [Capability]

    /// Execute a capability action, enforcing PolicyEngine authorization checks.
    func executeCapability(capabilityId: String, input: [String: String], userApproved: Bool) async -> CapabilityResult

    /// Retrieve detailed run lifecycle state by run ID.
    func getRun(runId: String) async -> AgentRunResult?

    /// Retrieve historical experience records for offline learning traceability.
    func getExperience() async -> [Experience]

    /// Return diagnostic health status of the local native agent service.
    func health() async -> AgentHealth
}
