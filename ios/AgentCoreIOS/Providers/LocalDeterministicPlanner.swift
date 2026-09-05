// ios/AgentCoreIOS/Providers/LocalDeterministicPlanner.swift
// Local Deterministic Planner — Explicitly Labeled TEST / DEVELOPMENT PROVIDER

import Foundation

/// Deterministic test planner provider.
/// NOTE: Explicitly labeled as TEST / DEVELOPMENT PROVIDER.
/// Never describes deterministic step outputs as genuine AI reasoning.
public final class LocalDeterministicPlanner: AgentModelProviderProtocol, @unchecked Sendable {
    public let providerName: String = "LocalDeterministicPlanner (TEST / DEVELOPMENT PROVIDER)"
    public let providerStatus: ModelProviderStatus = .deterministicTest

    public init() {}

    public func generatePlan(goal: String) async -> [String] {
        return [
            "TASK-001: Observe goal requirements for '\(goal)'",
            "TASK-002: Retrieve personal vault and memory context",
            "TASK-003: Check policy authorization rules",
            "TASK-004: Execute deterministic task steps",
            "TASK-005: Verify result and record experience"
        ]
    }
}
