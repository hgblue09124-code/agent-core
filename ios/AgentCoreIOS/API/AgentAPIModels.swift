// ios/AgentCoreIOS/API/AgentAPIModels.swift
// Native iOS Local Agent API v0.1 Result & Spec Codable Models

import Foundation

/// Status enum representing operational outcomes deterministically.
public enum Status: String, Codable, Sendable {
    case success = "SUCCESS"
    case failed = "FAILED"
    case denied = "DENIED"
    case notExecuted = "NOT_EXECUTED"
}

/// Codable result model for Agent run and resume execution.
public struct AgentRunResult: Codable, Sendable, Identifiable {
    public var id: String { runId }
    public let runId: String
    public let status: Status
    public let goal: String
    public let output: String?
    public let createdAt: String
    public let updatedAt: String
    public let errorCode: String?
    public let errorMessage: String?
    public let planSteps: [String]
    public let authorized: Bool
    public let verificationVerdict: String

    public init(
        runId: String,
        status: Status,
        goal: String,
        output: String? = nil,
        createdAt: String = ISO8601DateFormatter().string(from: Date()),
        updatedAt: String = ISO8601DateFormatter().string(from: Date()),
        errorCode: String? = nil,
        errorMessage: String? = nil,
        planSteps: [String] = [],
        authorized: Bool = true,
        verificationVerdict: String = "PASS"
    ) {
        self.runId = runId
        self.status = status
        self.goal = goal
        self.output = output
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.errorCode = errorCode
        self.errorMessage = errorMessage
        self.planSteps = planSteps
        self.authorized = authorized
        self.verificationVerdict = verificationVerdict
    }
}

/// Codable memory item stored in local memory layer.
public struct MemoryItem: Codable, Sendable, Identifiable {
    public var id: String { memoryId }
    public let memoryId: String
    public let key: String
    public let value: String
    public let memoryType: String
    public let importance: Double
    public let createdAt: String
    public let updatedAt: String

    public init(
        memoryId: String,
        key: String,
        value: String,
        memoryType: String = "short_term",
        importance: Double = 0.5,
        createdAt: String = ISO8601DateFormatter().string(from: Date()),
        updatedAt: String = ISO8601DateFormatter().string(from: Date())
    ) {
        self.memoryId = memoryId
        self.key = key
        self.value = value
        self.memoryType = memoryType
        self.importance = importance
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

/// Result model for memory creation/update operations.
public struct MemoryResult: Codable, Sendable {
    public let status: Status
    public let item: MemoryItem?
    public let errorMessage: String?

    public init(status: Status, item: MemoryItem? = nil, errorMessage: String? = nil) {
        self.status = status
        self.item = item
        self.errorMessage = errorMessage
    }
}

/// Specification model for pluggable capability modules.
public struct Capability: Codable, Sendable, Identifiable {
    public var id: String { capabilityId }
    public let capabilityId: String
    public let name: String
    public let description: String
    public let version: String
    public let readOnly: Bool
    public let requiresUserApproval: Bool

    public init(
        capabilityId: String,
        name: String,
        description: String,
        version: String = "1.0.0",
        readOnly: Bool = true,
        requiresUserApproval: Bool = false
    ) {
        self.capabilityId = capabilityId
        self.name = name
        self.description = description
        self.version = version
        self.readOnly = readOnly
        self.requiresUserApproval = requiresUserApproval
    }
}

/// Result model for capability execution.
public struct CapabilityResult: Codable, Sendable {
    public let capabilityId: String
    public let status: Status
    public let output: String?
    public let errorMessage: String?

    public init(capabilityId: String, status: Status, output: String? = nil, errorMessage: String? = nil) {
        self.capabilityId = capabilityId
        self.status = status
        self.output = output
        self.errorMessage = errorMessage
    }
}

/// Codable experience record for agent learning traceability.
public struct Experience: Codable, Sendable, Identifiable {
    public var id: String { runId }
    public let runId: String
    public let goal: String
    public let outcome: String
    public let timestamp: String

    public init(
        runId: String,
        goal: String,
        outcome: String,
        timestamp: String = ISO8601DateFormatter().string(from: Date())
    ) {
        self.runId = runId
        self.goal = goal
        self.outcome = outcome
        self.timestamp = timestamp
    }
}

/// Health and diagnostic status model for native agent runtime.
public struct AgentHealth: Codable, Sendable {
    public let status: String
    public let isLocalOnly: Bool
    public let providerName: String
    public let providerStatus: String
    public let isVaultAvailable: Bool
    public let storagePath: String
    public let activeCapabilitiesCount: Int

    public init(
        status: String = "HEALTHY",
        isLocalOnly: Bool = true,
        providerName: String = "LocalDeterministicPlanner",
        providerStatus: String = "DETERMINISTIC_TEST",
        isVaultAvailable: Bool = true,
        storagePath: String = "Application Support/AgentCore/",
        activeCapabilitiesCount: Int = 2
    ) {
        self.status = status
        self.isLocalOnly = isLocalOnly
        self.providerName = providerName
        self.providerStatus = providerStatus
        self.isVaultAvailable = isVaultAvailable
        self.storagePath = storagePath
        self.activeCapabilitiesCount = activeCapabilitiesCount
    }
}
