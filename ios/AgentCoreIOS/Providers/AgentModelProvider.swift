// ios/AgentCoreIOS/Providers/AgentModelProvider.swift
// Model Provider Abstraction Contract for Native iOS Local Runtime

import Foundation

/// Status of the on-device AI model provider.
public enum ModelProviderStatus: String, Codable, Sendable {
    case realLocalModel = "REAL_LOCAL_MODEL"
    case deterministicTest = "DETERMINISTIC_TEST"
    case unavailable = "UNAVAILABLE"
}

/// Protocol contract for the Agent model provider.
public protocol AgentModelProviderProtocol: Sendable {
    var providerName: String { get }
    var providerStatus: ModelProviderStatus { get }
    func generatePlan(goal: String) async -> [String]
}
