// ios/AgentCoreIOS/API/AgentRuntimeContract.swift
// Native iOS Local Agent API Service Protocol Contract

import Foundation

/// Protocol contract for the Native Local Agent Service called directly by iOS SwiftUI UI.
public protocol LocalAgentServiceProtocol: Sendable {
    /// Execute a task goal through the local Agent orchestration loop.
    func run(goal: String, userApproved: Bool) async -> AgentRunResult

    /// Cancel an active or pending agent execution run.
    func cancelRun(runId: String) async -> AgentRunResult

    /// Resume an interrupted/non-terminal run from local disk checkpoint.
    func resume(runId: String) async -> AgentRunResult

    /// Remember a key-value personal fact in local memory.
    func remember(key: String, value: String) async -> MemoryResult

    /// Retrieve stored memory items matching a query.
    func retrieve(query: String) async -> [MemoryItem]

    /// Update an existing memory item, enforcing policy write approval checks.
    func updateMemory(key: String, value: String, userApproved: Bool) async -> MemoryResult

    /// Forget (remove) a stored personal memory item by key.
    func forget(key: String) async -> MemoryResult

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

    // MARK: - Additive UI Contract Methods

    /// Return current operational status (READY / THINKING / RUNNING / OFFLINE).
    func currentAgentStatus() async -> AgentStatus

    /// Execute a task with milestone lifecycle event progress callbacks and optional capability dispatch.
    func runStreaming(
        goal: String,
        userApproved: Bool,
        capabilityDispatch: (capabilityId: String, input: [String: String])?,
        onEvent: @escaping @Sendable (AgentRunEvent) -> Void
    ) async -> AgentRunResult

    /// Cancel an active or pending run by run ID. Returns false if run does not exist or is already terminal.
    func cancel(runId: String) async -> Bool

    /// Get pending approval request for a given run ID if policy denied execution.
    func pendingApproval(runId: String) async -> PermissionRequest?

    /// List filterable historical activity records.
    func listActivity(filter: ActivityFilter) async -> [ActivityRecord]

    /// Return summary metrics and category counts of personal vault.
    func vaultSummary() async -> VaultSummary

    /// List operational status of all capability connections (local vs remote).
    func listConnections() async -> [ConnectionStatus]
}
